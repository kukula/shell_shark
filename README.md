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

### CLI (future)

```bash
# SQL-ish syntax
shellspark "FROM 'access.log' | PARSE apache | WHERE status >= 400 | COUNT() BY path"

# Or from a file
shellspark run query.spark
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

## Project Structure

```
shellspark/
├── shellspark/
│   ├── __init__.py
│   ├── pipeline.py        # Main Pipeline class, builder pattern
│   ├── ast.py             # Operation nodes (Filter, Select, GroupBy, etc.)
│   ├── optimizer.py       # Query plan optimization
│   ├── codegen/
│   │   ├── __init__.py
│   │   ├── base.py        # Abstract code generator
│   │   ├── awk.py         # AWK code generation
│   │   ├── grep.py        # grep/ripgrep generation
│   │   ├── jq.py          # jq for JSON
│   │   └── sort.py        # sort, uniq, head, tail
│   ├── tools.py           # Tool detection (is mawk installed?)
│   ├── executor.py        # Run pipelines, stream results
│   └── formats/
│       ├── __init__.py
│       ├── csv.py
│       ├── json.py
│       └── text.py
├── tests/
├── examples/
│   ├── chess_analysis.py  # Reproduce the 235x benchmark
│   ├── log_analysis.py
│   └── csv_etl.py
├── pyproject.toml
└── README.md
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

1. **Field delimiters in data** — CSV with quoted fields needs proper parsing (use `mlr` or Python csv module as fallback)
2. **Header detection** — Option to skip first line or use headers as field names
3. **Empty results** — Don't fail, return empty
4. **Special characters** — Proper escaping via `shlex.quote()`
5. **Binary files** — Detect and skip or error

## Future Ideas

- **Explain mode**: Show query plan and estimated cost
- **Dry-run**: Print shell command without executing
- **Jupyter integration**: Rich output, progress bars
- **Streaming results**: Yield rows as they come
- **Result caching**: Cache execution results based on file mtimes
- **Remote execution**: SSH pipeline to process files on remote servers
- **Custom tools**: Plugin system for domain-specific parsers

## Prior Art & Inspiration

- [Adam Drake's article](https://adamdrake.com/command-line-tools-can-be-235x-faster-than-your-hadoop-cluster.html) — The original inspiration
- [Miller (mlr)](https://miller.readthedocs.io/) — Like awk/sed/cut for CSV/JSON
- [xsv](https://github.com/BurntSushi/xsv) — Fast CSV toolkit in Rust
- [q](http://harelba.github.io/q/) — Run SQL on CSV files
- [textql](https://github.com/dinedal/textql) — SQL against CSV
- [pandas](https://pandas.pydata.org/) — API inspiration (but in-memory)
- [Spark](https://spark.apache.org/) — API inspiration (but distributed)
- [DuckDB](https://duckdb.org/) — Fast analytical queries (different approach, embedded DB)

## License

MIT
