# Performance

ShellSpark is designed for speed. Here are tips to get the best performance.

## Tool Selection

ShellSpark automatically selects the fastest available tools:

| Tool Type | Preference Order | Speed Gain |
|-----------|-----------------|------------|
| AWK | mawk > gawk > awk | mawk is 5-10x faster than gawk |
| Grep | rg > GNU grep > BSD grep | ripgrep is 2-5x faster |

### Installing Faster Tools

```bash
# macOS
brew install mawk ripgrep

# Ubuntu/Debian
sudo apt-get install mawk ripgrep

# Fedora/RHEL
sudo dnf install mawk ripgrep
```

Verify your tools:
```python
from shellspark.tools import detect_awk, detect_grep
print(f"AWK: {detect_awk().name}")  # Should show 'mawk'
print(f"Grep: {detect_grep().name}")  # Should show 'rg'
```

## Command Caching

Generated shell commands are cached to avoid redundant compilation:

```python
from shellspark import Pipeline, clear_command_cache

p = Pipeline("data.csv").parse("csv").filter(x__gt=5)

# First call compiles the pipeline
cmd1 = p.to_shell()

# Second call returns cached result (1800x faster)
cmd2 = p.to_shell()

# Clear cache if needed (after tool changes)
clear_command_cache()
```

Cache key includes:
- AST hash (pipeline structure)
- Tool paths (awk, grep executables)

## Parallel Processing

For multi-file patterns, use `.parallel()`:

```python
# Process multiple log files in parallel
result = (
    Pipeline("logs/*.log")
    .filter(line__contains="ERROR")
    .parallel(workers=8)
    .run()
)

# Generated command uses find | xargs -P
# find logs -name '*.log' -print0 | xargs -0 -P8 grep -F 'ERROR'
```

### Parallel Limitations

These operations cannot be parallelized (require global state):
- `sort()` - needs all data
- `distinct()` - needs all data
- `group_by().agg()` - needs all data
- `limit()` - needs all data

### Worker Count

Default is CPU count. Override with `workers` parameter:

```python
# Auto-detect (CPU count)
Pipeline("logs/*.log").filter(...).parallel()

# Explicit worker count
Pipeline("logs/*.log").filter(...).parallel(workers=4)
```

## Large Dataset Tips

### Streaming Results

For very large outputs, use `.stream()` instead of `.run()`:

```python
# Process line-by-line instead of loading all into memory
for line in Pipeline("huge.log").filter(line__contains="ERROR").stream():
    process(line)
```

### Large Sorts

GNU sort handles large datasets efficiently with these flags (used automatically):

```bash
sort -T /tmp --parallel=$(nproc) -S 80% -k1,1
```

- `-T /tmp`: Temp directory for spill files
- `--parallel`: Parallel merge sort
- `-S 80%`: Use up to 80% of RAM

### Filter Early

Push filters as early as possible to reduce data volume:

```python
# Good: filter first, reduces data for sort
Pipeline("data.csv").parse("csv").filter(year__eq=2024).sort("date")

# Less efficient: sort everything, then filter
Pipeline("data.csv").parse("csv").sort("date").filter(year__eq=2024)
```

The optimizer does this automatically, but explicit ordering makes intent clear.

## Benchmarks

ShellSpark performance on a 1GB JSON log file (M1 MacBook):

| Operation | ShellSpark | Pure Python |
|-----------|-----------|-------------|
| Filter (line contains) | 2.1s | 8.5s |
| Filter + count | 2.3s | 9.2s |
| Group by + sum | 4.8s | 15.3s |
| Sort | 3.2s | 12.1s |

*Results vary by hardware and data characteristics.*

### Why Shell is Fast

1. **Pipes are parallel** - each `|` stage runs concurrently
2. **Streaming** - near-zero memory, only counters in RAM
3. **C implementations** - mawk, ripgrep are highly optimized
4. **No serialization** - plain text, no encoding overhead

## Profiling

Compare execution strategies:

```python
import time

p = Pipeline("data.csv").parse("csv").filter(x__gt=5)

# Time shell command
start = time.time()
cmd = p.to_shell()
compile_time = time.time() - start

start = time.time()
result = p.run()
exec_time = time.time() - start

print(f"Compile: {compile_time*1000:.2f}ms")
print(f"Execute: {exec_time*1000:.2f}ms")
```

## Memory Usage

ShellSpark pipelines use minimal Python memory:
- Commands execute in subprocesses
- Results stream through pipes
- Only final output loaded into Python

For structured output (`group_by().agg()`), results are parsed into dictionaries. For very large aggregation results, consider using `.run_raw()` and parsing manually.
