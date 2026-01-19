# ShellSpark Demos

Examples demonstrating ShellSpark's data transformation capabilities. ShellSpark compiles Python data pipelines into optimized Unix shell commands using `awk`, `grep`, `sort`, `jq`, and related tools.

## Performance

Tested on MacBook Air M3, Python 3.12. Timing split into Python compilation and shell execution:

| Demo | Data | Compile (miss) | Compile (hit) | Shell | Speedup | AST Mem | Result Mem |
|------|------|----------------|---------------|-------|---------|---------|------------|
| CSV Aggregation | 20 rows | 11.4ms | 0.014ms | 10.9ms | 786x | 6.2KB | 84.1KB |
| Text Filter (contains) | 20 lines | 10.7ms | 0.018ms | 6.0ms | 604x | 3.3KB | 83.9KB |
| Text Filter (regex) | 20 lines | 10.0ms | 0.029ms | 6.8ms | 345x | 3.4KB | 83.7KB |
| JSON Select | 10 records | 13.5ms | 0.009ms | 6.1ms | 1521x | 4.9KB | 83.5KB |
| JSON Filter+Select | 100K rows | 12.7ms | 0.018ms | 270.9ms | 696x | 4.6KB | 3814KB |

**Key insights:**
- Compilation overhead is ~10-14ms on first call (cache miss)
- Cached compilation returns in ~0.01-0.03ms (300-1500x faster)
- Shell execution scales with data size; compilation does not
- AST memory is minimal (~3-6KB); result memory scales with output size

## Quick Start

```bash
# 1. Install prerequisites
# Ubuntu/Debian
sudo apt install mawk jq

# macOS
brew install mawk jq

# 2. Download sample data files
cd demo
./setup.sh

# 3. Run a demo
python csv_aggregation.py
```

## Examples

### 1. CSV Aggregation (`csv_aggregation.py`)

CSV parsing with revenue calculations by region.

```python
result = (
    Pipeline("demo/data/sales.csv")
    .parse("csv", header=True)
    .filter(quantity__gt=0)
    .group_by("region")
    .agg(
        total_orders=("*", "count"),
        total_quantity=("quantity", "sum"),
        total_revenue=("price * quantity", "sum")
    )
    .sort("total_revenue", desc=True)
    .run()
)
```

**Compiles to:**
```bash
gawk -F, 'NR==1{for(i=1;i<=NF;i++)h[$i]=i; next} \
  $h["quantity"]>0{ \
    key=$h["region"]; \
    _count_total_orders[key]++; \
    _sum_total_quantity[key]+=$h["quantity"]; \
    _sum_total_revenue[key]+=$h["price * quantity"]; \
    _keys[key]=1 \
  } \
  END{for(k in _keys){print k","_count_total_orders[k]","_sum_total_quantity[k]","_sum_total_revenue[k]}}' \
  demo/data/sales.csv \
| sort -t, -k4,4r
```

**Timing (MacBook Air M3):**
- Compile: 11.4ms (cached: 0.014ms, 786x faster)
- Shell: 10.9ms
- Memory: 6.2KB (AST) / 84KB (result)

---

### 2. Text Filtering (`text_filter.py`)

Simple grep-style log filtering.

```python
# Find all ERROR entries
errors = (
    Pipeline("demo/data/app.log")
    .filter(line__contains="ERROR")
    .run()
)
```

**Compiles to:**
```bash
rg -F --no-filename ERROR demo/data/app.log
```

**Timing:** Compile 10.7ms (cached: 0.018ms), Shell 6.0ms, Memory 3.3KB/84KB

```python
# Find ERROR or WARN entries using regex
issues = (
    Pipeline("demo/data/app.log")
    .filter(line__regex="(ERROR|WARN)")
    .run()
)
```

**Compiles to:**
```bash
rg --no-filename '(ERROR|WARN)' demo/data/app.log
```

**Timing:** Compile 10.0ms (cached: 0.029ms), Shell 6.8ms, Memory 3.4KB/84KB

---

### 3. JSON Demo (`json_demo.py`)

JSON field extraction.

```python
result = (
    Pipeline("demo/data/users.json")
    .parse("json")
    .select("name", "email")
    .run()
)
```

**Compiles to:**
```bash
jq -c '{name, email}' demo/data/users.json
```

**Timing:** Compile 13.5ms (cached: 0.009ms), Shell 6.1ms, Memory 4.9KB/84KB

---

### 4. JSON Filter + Select (Large Dataset)

Processing 100K web server log records.

```python
result = (
    Pipeline("demo/data/logs.json")
    .parse("json")
    .filter(status__gte=400)
    .select("path", "status", "response_time")
    .run()
)
```

**Compiles to:**
```bash
jq -c 'select(.status >= 400) | {path, status, response_time}' demo/data/logs.json
```

**Timing:** Compile 12.7ms (cached: 0.018ms), Shell 271ms, Memory 4.6KB/3.8MB (100K records)

---

### 5. Word Count (`word_count.py`)

Classic word frequency analysis. Shows planned API (requires `flatmap` feature not yet implemented).

```python
# Planned API:
result = (
    Pipeline("demo/data/book.txt")
    .flatmap(split=r"\s+")
    .filter(line__regex=r"^[a-zA-Z]+$")
    .group_by("word")
    .agg(count=("*", "count"))
    .sort("count", desc=True)
    .limit(20)
    .run()
)
```

**Would compile to:**
```bash
cat demo/data/book.txt | tr ' ' '\n' | grep -E '^[a-zA-Z]+$' | \
  sort | uniq -c | sort -rn | head -20
```

---

## Command Caching

ShellSpark automatically caches compiled shell commands. Repeated calls to `.to_shell()` or `.run()` skip compilation:

```python
from shellspark import Pipeline, clear_command_cache

pipeline = (
    Pipeline("demo/data/sales.csv")
    .parse("csv", header=True)
    .group_by("region")
    .agg(total=("quantity", "sum"))
)

# First call: ~12ms (cache miss - full compilation)
cmd = pipeline.to_shell()

# Second call: ~0.01ms (cache hit - 1000x faster)
cmd = pipeline.to_shell()

# Clear cache if needed
clear_command_cache()
```

Cache key includes AST hash + tool paths, so different pipelines and tool configurations get separate cache entries. Tool detection (mawk/gawk/jq paths) is also cached via `lru_cache`.

## Data Files

After running `./setup.sh`, the `data/` directory contains:

| File | Description | Source |
|------|-------------|--------|
| `book.txt` | Pride and Prejudice (772KB) | [Project Gutenberg](https://www.gutenberg.org/cache/epub/1342/pg1342.txt) |
| `users.json` | 10 user records (NDJSON) | [JSONPlaceholder](https://jsonplaceholder.typicode.com/users) |
| `sales.csv` | 20 sales records | Generated |
| `app.log` | 20 log entries | Generated |
| `logs.json` | 100K web server logs (~18MB) | generate_logs.py |

## Prerequisites

ShellSpark requires these Unix tools:

```bash
# Verify installation
mawk -W version  # Fast AWK implementation (or gawk)
jq --version     # JSON processor

# Optional but recommended
rg --version     # ripgrep (faster grep)
```

## Benchmarking

Run the full benchmark with 5 million records:

```bash
./benchmark.sh
```

This generates ~1GB of JSON logs and measures ShellSpark's performance.
