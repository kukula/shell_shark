# Getting Started

## Prerequisites

**Python:** 3.10 or higher

**Required shell tools:**
- `awk` (any implementation: mawk, gawk, or BSD awk)
- `grep` (GNU grep or BSD grep)
- `sort`, `head`, `tail`, `uniq` (standard Unix tools)

**Optional tools:**
- `mawk` - Faster awk implementation (preferred over gawk)
- `rg` (ripgrep) - Faster grep alternative
- `jq` - Required for JSON processing

## Installation

```bash
# From PyPI (when published)
pip install shellspark

# From source
git clone https://github.com/youruser/shellspark
cd shellspark
pip install -e .
```

## Verify Tools

Check which tools ShellSpark will use:

```python
from shellspark.tools import detect_awk, detect_grep, detect_jq

print(f"AWK: {detect_awk()}")
print(f"Grep: {detect_grep()}")
print(f"jq: {detect_jq()}")
```

## First Pipeline

### Filtering Text Files

```python
from shellspark import Pipeline

# Find ERROR lines in a log file
errors = Pipeline("app.log").filter(line__contains="ERROR").run()
print(f"Found {len(errors)} errors")

# See the generated shell command
cmd = Pipeline("app.log").filter(line__contains="ERROR").to_shell()
print(cmd)  # grep -F 'ERROR' app.log
```

### Working with CSV

```python
from shellspark import Pipeline, sum_, count_

# Parse CSV and filter by column
result = (
    Pipeline("sales.csv")
    .parse("csv")
    .filter(region__eq="West")
    .select("product", "amount")
    .run()
)

# Group and aggregate
totals = (
    Pipeline("sales.csv")
    .parse("csv")
    .group_by("region")
    .agg(
        total=sum_("amount"),
        orders=count_()
    )
    .run()
)
# Returns: [{"region": "West", "total": 5000, "orders": 42}, ...]
```

### Working with JSON

```python
from shellspark import Pipeline

# Filter JSON records (requires jq)
errors = (
    Pipeline("events.json")
    .parse("json")
    .filter(level__eq="error")
    .select("timestamp", "message")
    .run()
)
```

## Environment Variables

Override tool selection with environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `SHELLSPARK_AWK` | Force specific awk | `export SHELLSPARK_AWK=gawk` |
| `SHELLSPARK_GREP` | Force specific grep | `export SHELLSPARK_GREP=grep` |
| `SHELLSPARK_SORT` | Force specific sort | `export SHELLSPARK_SORT=/usr/local/bin/gsort` |
| `SHELLSPARK_JQ` | Force specific jq | `export SHELLSPARK_JQ=/opt/bin/jq` |

## Next Steps

- [Filter Operations](filter-operations.md) - All filter operators
- [Aggregations](aggregations.md) - Grouping and aggregation functions
- [Performance](performance.md) - Optimization tips
