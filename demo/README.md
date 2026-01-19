# ShellSpark Demos

Examples demonstrating ShellSpark's data transformation capabilities. ShellSpark compiles Python data pipelines into optimized Unix shell commands using `awk`, `grep`, `sort`, `jq`, and related tools.

## Performance

Tested on MacBook Air M3. Timing split into Python compilation (AST building, optimization, shell generation) and shell execution:

| Demo | Data Size | Python | Shell | Total |
|------|-----------|--------|-------|-------|
| CSV Aggregation | 20 rows | 17ms | 11ms | 28ms |
| Text Filter (contains) | 20 lines | 7ms | 11ms | 18ms |
| Text Filter (regex) | 20 lines | 4ms | 8ms | 12ms |
| JSON Select | 10 records | 5ms | 6ms | 11ms |
| JSON Filter + Select | 100K records | 5ms | 279ms | 284ms |

**Key insight:** Python compilation overhead is ~5-17ms regardless of data size. Shell execution scales with data.

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
- Python compilation: 17ms
- Shell execution: 11ms

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

**Timing:** Python 7ms, Shell 11ms

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

**Timing:** Python 4ms, Shell 8ms

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

**Timing:** Python 5ms, Shell 6ms

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

**Timing:** Python 5ms, Shell 279ms (100K records, ~18MB)

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

## Caching Generated Commands

The shell command can be retrieved separately with `.to_shell()` and cached:

```python
pipeline = (
    Pipeline("demo/data/sales.csv")
    .parse("csv", header=True)
    .group_by("region")
    .agg(total=("quantity", "sum"))
)

# Get command (5ms) - can cache this string
cmd = pipeline.to_shell()

# Execute later (11ms)
result = pipeline.run()
```

Tool detection (mawk/gawk/jq paths) is automatically cached via `lru_cache`.

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
