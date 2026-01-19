# Troubleshooting

## Common Errors

### Tool Not Found

**Error:** `RuntimeError: No awk implementation found`

**Solution:** Install an awk implementation:
```bash
# macOS (awk is pre-installed, but you can add mawk for speed)
brew install mawk

# Ubuntu/Debian
sudo apt-get install mawk

# Fedora/RHEL
sudo dnf install mawk
```

**Error:** `jq not available for JSON processing`

**Solution:** Install jq:
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# Fedora/RHEL
sudo dnf install jq
```

### Column Name Errors

**Error:** `ValueError: Invalid filter key 'status'. Expected format: 'column__op'`

**Solution:** Use the double-underscore syntax with an operator:
```python
# Wrong
Pipeline("data.csv").parse("csv").filter(status="active")

# Correct
Pipeline("data.csv").parse("csv").filter(status__eq="active")
```

### Aggregation Without group_by

**Error:** `ValueError: agg() must be called after group_by()`

**Solution:** Call `group_by()` before `agg()`:
```python
# Wrong
Pipeline("data.csv").parse("csv").agg(total=sum_("amount"))

# Correct
Pipeline("data.csv").parse("csv").group_by("category").agg(total=sum_("amount"))
```

### Parallelization Restrictions

**Error:** `ValueError: Cannot parallelize pipeline with sort()`

**Solution:** Operations requiring global state cannot be parallelized:
- `sort()` - needs all data to sort
- `distinct()` - needs all data for deduplication
- `group_by().agg()` - needs all data for aggregation
- `limit()` - needs all data to select top N

```python
# Wrong - sort cannot be parallelized
Pipeline("logs/*.log").filter(line__contains="ERROR").sort("timestamp").parallel()

# Correct - filter can be parallelized, sort after
# (sort would need to happen in a separate step)
Pipeline("logs/*.log").filter(line__contains="ERROR").parallel()
```

### Empty Results

Pipelines return empty lists when no matches are found (not an error):

```python
result = Pipeline("data.csv").parse("csv").filter(status__eq="nonexistent").run()
# result = []  (not an exception)
```

To check for empty results:
```python
result = Pipeline("data.csv").parse("csv").filter(status__eq="rare").run()
if not result:
    print("No matches found")
```

## Debugging

### View Generated Command

Use `to_shell()` to see the generated command without executing:

```python
cmd = (
    Pipeline("data.csv")
    .parse("csv")
    .filter(status__eq="active")
    .select("name", "amount")
    .to_shell()
)
print(cmd)
# awk -F',' 'NR>1 && $2 == "active" {print $1, $3}' data.csv
```

### Check Tool Configuration

```python
from shellspark.tools import detect_awk, detect_grep, detect_jq, detect_sort

print(f"AWK: {detect_awk()}")
print(f"Grep: {detect_grep()}")
print(f"Sort: {detect_sort()}")
print(f"jq: {detect_jq()}")
```

### Get Full Execution Result

Use `run_result()` to get stdout, stderr, and return code:

```python
result = Pipeline("data.csv").parse("csv").filter(x__gt=5).run_result()
print(f"Return code: {result.return_code}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")
print(f"Command: {result.command}")
```

### Clear Caches

If you change environment variables or tool installations mid-session:

```python
from shellspark import clear_command_cache
from shellspark.tools import clear_tool_cache

# Clear compiled command cache
clear_command_cache()

# Clear tool detection cache
clear_tool_cache()
```

## Platform-Specific Issues

### macOS vs Linux

ShellSpark automatically handles platform differences:
- CPU detection: `sysctl -n hw.ncpu` (macOS) vs `nproc` (Linux)
- GNU vs BSD tool flags: Detected at runtime

### Sort Parallelization

GNU sort supports `--parallel` but BSD sort does not. ShellSpark detects this:

```python
from shellspark.tools import sort_supports_parallel
print(f"Parallel sort available: {sort_supports_parallel()}")
```

## Getting Help

- Check generated commands with `.to_shell()`
- Inspect the AST with `.ast` property
- File issues at the GitHub repository
