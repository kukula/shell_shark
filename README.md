# ShellSpark

A Python framework that compiles declarative data transformations into Unix shell pipelines.

Write queries like Spark. Execute them at 270MB/sec with `awk`, `grep`, `sort`, and friends.

## Motivation

Inspired by Adam Drake's classic article [Command-line Tools can be 235x Faster than your Hadoop Cluster](https://adamdrake.com/command-line-tools-can-be-235x-faster-than-your-hadoop-cluster.html), which demonstrated that a simple `find | xargs | mawk` pipeline could process 3.46GB of chess data in 12 seconds—while a 7-node Hadoop cluster took 26 minutes for half the data.

**Why does this happen?**

1. **Shell pipes are parallel by default** — each `|` runs concurrently, no framework overhead
2. **Streaming means near-zero memory** — only counters/accumulators live in RAM
3. **Decades of optimization** — `mawk`, `ripgrep`, `sort` are insanely fast
4. **No serialization overhead** — plain text, no Avro/Parquet encoding/decoding

**The problem:** Writing correct, optimized shell pipelines is painful. Escaping, parallelization with `xargs`, choosing the right tool (`mawk` vs `gawk` vs `grep`)—it's expert knowledge.

**ShellSpark's goal:** Let you write familiar, declarative transformations and compile them to optimized shell pipelines.

## Features

- **Familiar API** — Spark-like builder pattern with `filter()`, `select()`, `group_by()`, `agg()`, `sort()`
- **Multiple formats** — CSV (with headers), JSON (NDJSON), and plain text
- **Smart tool selection** — Automatically uses mawk over gawk (5-10x faster), ripgrep over grep (2-5x faster)
- **Command caching** — Compiled pipelines cached for 600-1500x faster repeated execution
- **Parallel processing** — Multi-file patterns with `find | xargs -P` and safe null-delimited paths
- **Streaming execution** — Process files larger than RAM with `.stream()`
- **Transparent compilation** — Inspect generated shell with `.to_shell()` for debugging or learning
- **Django-style filters** — Intuitive operators: `__eq`, `__gt`, `__contains`, `__regex`
- **Aggregations** — `count`, `sum`, `min`, `max`, `avg` with expressions like `price * quantity`
- **Minimal dependencies** — Pure Python, uses common Unix tools (awk, grep, sort, jq)

## Usage

### Python DSL

```python
from shellspark import Pipeline

# Analyze web logs
result = (
    Pipeline("logs/*.json")
    .parse("json")
    .filter(status__gte=400)
    .select("timestamp", "method", "path", "status")
    .group_by("path")
    .agg(
        count=("*", "count"),
        avg_status=("status", "mean")
    )
    .sort("count", desc=True)
    .limit(20)
    .run()
)

# See what it compiled to
Pipeline("logs/*.json").filter(status__gte=400).to_shell()
# => find logs -name '*.json' -print0 | xargs -0 -P8 jq -c 'select(.status >= 400)'
```

## Operation Mapping

| ShellSpark | Shell Implementation |
|------------|---------------------|
| `filter(col == val)` | `grep -F "val"` or `awk '$N == "val"'` |
| `filter(col ~ regex)` | `grep -E "regex"` or `rg "regex"` |
| `select(cols...)` | `awk '{print $1, $3}'` or `cut -f1,3` |
| `map(expr)` | `awk '{print expr}'` |
| `group_by().agg()` | `awk '{agg[$key]+=...} END{...}'` or `sort \| datamash` |
| `distinct()` | `sort -u` |
| `count()` | `wc -l` |
| `sort(col)` | `sort -k1` / `sort -k1 -n` / `sort -k1 -rn` |
| `limit(n)` | `head -n` |
| `union(other)` | `cat` |
| `join(other, on)` | `join -1 N -2 M` (requires sorted input) |
| `sample(n)` | `shuf -n N` |

### Format-Specific Parsing

| Format | Tool |
|--------|------|
| CSV | `awk -F','` or `mlr` (Miller) |
| TSV | `awk -F'\t'` or `cut` |
| JSON | `jq` |
| JSONL | `jq -c` |
| Apache/Nginx logs | Custom `awk` patterns |
| Fixed-width | `awk` with `substr()` |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Python DSL                                         │
│  Pipeline("*.csv").filter(...).group_by(...).agg()  │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│  Query Plan (AST)                                   │
│  [Source] -> [Filter] -> [GroupBy] -> [Agg] -> [Sink]│
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│  Optimizer                                          │
│  - Push filters upstream (before expensive ops)     │
│  - Merge adjacent awk stages                        │
│  - Choose grep vs awk based on pattern complexity   │
│  - Insert parallelization (xargs -P)                │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│  Code Generator                                     │
│  - Emit shell pipeline string                       │
│  - Handle escaping (shlex)                          │
│  - Tool selection (mawk > gawk > awk)               │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│  Executor                                           │
│  - subprocess.Popen with shell=False                │
│  - Stream stdout back to Python                     │
│  - Optional: parse results into dicts/dataframes    │
└─────────────────────────────────────────────────────┘
```

## Implementation Notes

### Parallelization Strategy

Use `xargs -P` for embarrassingly parallel operations (filter, map, parse). The pattern:

```bash
find . -name '*.csv' -print0 | xargs -0 -n4 -P$(nproc) mawk -F',' '...'
```

- `-print0` / `-0`: Handle filenames with spaces
- `-n4`: Process 4 files per worker (tune based on file sizes)
- `-P$(nproc)`: One worker per CPU core

**When NOT to parallelize:**
- Operations requiring global state (sort, distinct, joins)
- Final aggregation step (needs single reducer)

### AWK Code Generation

Most operations compile to a single `awk` program:

```python
# This pipeline:
Pipeline("data.csv").filter(status="active").select("id", "amount").group_by("category").agg(total=("amount", "sum"))

# Becomes:
awk -F',' 'NR>1 && $3=="active" { totals[$2] += $4 } END { for(k in totals) print k, totals[k] }' data.csv
```

Key patterns:
- `NR>1` to skip headers
- Field references: `$1`, `$2`, etc.
- Associative arrays for group_by
- `END { }` block for final output

### Tool Selection

Detect available tools at runtime and prefer faster alternatives:

```python
TOOL_PREFERENCE = {
    "awk": ["mawk", "gawk", "awk"],      # mawk is fastest
    "grep": ["rg", "grep"],               # ripgrep if available
    "json": ["jq"],                       # no real alternative
    "sort": ["sort"],                     # GNU sort with --parallel
}
```

### Command Caching

Generated shell commands are cached to avoid redundant compilation:

```python
from shellspark import Pipeline, clear_command_cache

p = Pipeline("data.csv").parse("csv").filter(x__gt=5)

# First call compiles the pipeline (~11ms)
cmd1 = p.to_shell()

# Second call returns cached result (~0.006ms, 1835x faster)
cmd2 = p.to_shell()

# Clear cache if needed (e.g., after tool configuration changes)
clear_command_cache()
```

Cache key includes AST hash + tool paths, so different tool configurations produce separate cache entries.

### Handling Large Sorts

For sorts that exceed memory:

```bash
sort -T /tmp --parallel=$(nproc) -S 80% -k1,1
```

- `-T /tmp`: Use temp directory for spill
- `--parallel`: Parallel merge sort
- `-S 80%`: Use up to 80% of RAM

### Edge Cases to Handle

1. Check on Linux
2. **Field delimiters in data** — CSV with quoted fields needs proper parsing (use `mlr` or Python csv module as fallback)
3. **Header detection** — Option to skip first line or use headers as field names
4. **Empty results** — Don't fail, return empty
5. **Special characters** — Proper escaping via `shlex.quote()`
6. **Binary files** — Detect and skip or error

## Prior Art & Inspiration

- [Adam Drake's article](https://adamdrake.com/command-line-tools-can-be-235x-faster-than-your-hadoop-cluster.html) — The original inspiration
- [Miller (mlr)](https://miller.readthedocs.io/) — Like awk/sed/cut for CSV/JSON
- [xsv](https://github.com/BurntSushi/xsv) — Fast CSV toolkit in Rust
- [q](http://harelba.github.io/q/) — Run SQL on CSV files
- [textql](https://github.com/dinedal/textql) — SQL against CSV
- [Spark](https://spark.apache.org/) — API inspiration (but distributed)

## License

MIT
