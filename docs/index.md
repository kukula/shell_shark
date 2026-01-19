# ShellSpark Documentation

ShellSpark is a Python framework that compiles declarative data transformations into Unix shell pipelines. Write queries like Spark, execute them at 270MB/sec with `awk`, `grep`, `sort`, and friends.

## Quick Links

- [Getting Started](getting-started.md) - Installation and first pipeline
- [Filter Operations](filter-operations.md) - Complete filter operator reference
- [Aggregations](aggregations.md) - `group_by()` and `agg()` reference
- [Performance](performance.md) - Optimization tips and benchmarks
- [Troubleshooting](troubleshooting.md) - Common errors and solutions

## Overview

ShellSpark provides a familiar, Spark-like API that compiles to optimized shell commands:

```python
from shellspark import Pipeline

# This Python code:
result = (
    Pipeline("logs/*.json")
    .parse("json")
    .filter(status__gte=400)
    .group_by("path")
    .agg(count=("*", "count"))
    .run()
)

# Compiles to shell commands using jq, awk, grep, sort
```

## Architecture

See the main [README](../README.md) for detailed architecture documentation, including:

- Pipeline flow (DSL -> AST -> Optimizer -> CodeGen -> Executor)
- Project structure
- Tool selection strategy
- Parallelization patterns
