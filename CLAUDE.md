# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ShellSpark is a Python framework that compiles declarative data transformations into Unix shell pipelines. The goal is to provide a Spark-like API that generates optimized shell commands using `awk`, `grep`, `sort`, `jq`, and related tools.

## Architecture

The pipeline flow:
1. **Python DSL** (`Pipeline` class with builder pattern) →
2. **Query Plan (AST)** (operation nodes like Filter, Select, GroupBy) →
3. **Optimizer** (push filters upstream, merge awk stages, choose tools) →
4. **Code Generator** (emit shell pipeline with proper escaping) →
5. **Executor** (run via subprocess, stream results)

## Key Design Decisions

- **Tool preference order**: mawk > gawk > awk; ripgrep (rg) > grep
- **Parallelization**: Use `xargs -P` with `-print0`/`-0` for safe filename handling
- **Do NOT parallelize**: Operations requiring global state (sort, distinct, joins, final aggregation)
- **AWK patterns**: Use `NR>1` to skip headers, associative arrays for group_by, `END {}` for final output
- **Large sorts**: Use `sort -T /tmp --parallel=$(nproc) -S 80%` for memory-safe sorting
- **Escaping**: Always use `shlex.quote()` for shell safety

## Planned Project Structure

```
shellspark/
├── pipeline.py        # Main Pipeline class, builder pattern
├── ast.py             # Operation nodes (Filter, Select, GroupBy, etc.)
├── optimizer.py       # Query plan optimization
├── codegen/           # Code generators for awk, grep, jq, sort
├── tools.py           # Runtime tool detection
├── executor.py        # Run pipelines, stream results
└── formats/           # Format handlers (csv, json, text)
```

## Operation to Shell Mapping

| Operation | Shell Tool |
|-----------|-----------|
| `filter(col == val)` | `grep -F` or `awk` |
| `filter(col ~ regex)` | `grep -E` or `rg` |
| `select(cols...)` | `awk '{print}'` or `cut` |
| `group_by().agg()` | `awk` with associative arrays or `sort \| datamash` |
| `distinct()` | `sort -u` |
| `sort(col)` | `sort -k` |
| `limit(n)` | `head -n` |
| `join(other, on)` | `join` (requires sorted input) |
| JSON parsing | `jq` |
| CSV parsing | `awk -F','` or `mlr` (Miller) |
