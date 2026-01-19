# Filter Operations

The `filter()` method supports various operators using the `column__operator=value` syntax.

## Line-Level Filters

Use `line__` prefix for filtering entire lines (text files, logs):

| Operator | Description | Example | Shell |
|----------|-------------|---------|-------|
| `line__contains` | Substring match | `filter(line__contains="ERROR")` | `grep -F 'ERROR'` |
| `line__regex` | Regex match | `filter(line__regex="ERROR\|WARN")` | `grep -E 'ERROR\|WARN'` |
| `line__startswith` | Prefix match | `filter(line__startswith="2024")` | `grep '^2024'` |
| `line__endswith` | Suffix match | `filter(line__endswith=".json")` | `grep '\.json$'` |

### Examples

```python
from shellspark import Pipeline

# Find lines containing "ERROR"
Pipeline("app.log").filter(line__contains="ERROR")

# Find lines matching a regex pattern
Pipeline("app.log").filter(line__regex=r"status=\d{3}")

# Find lines starting with a date
Pipeline("app.log").filter(line__startswith="2024-01-")

# Find lines ending with specific text
Pipeline("app.log").filter(line__endswith="completed")
```

## Column-Level Filters

After calling `parse()`, use column names with comparison operators:

| Operator | Description | Example |
|----------|-------------|---------|
| `col__eq` | Equal | `filter(status__eq="active")` |
| `col__ne` | Not equal | `filter(status__ne="deleted")` |
| `col__lt` | Less than | `filter(age__lt=30)` |
| `col__le` | Less than or equal | `filter(age__le=30)` |
| `col__lte` | Less than or equal (alias) | `filter(age__lte=30)` |
| `col__gt` | Greater than | `filter(price__gt=100)` |
| `col__ge` | Greater than or equal | `filter(price__ge=100)` |
| `col__gte` | Greater than or equal (alias) | `filter(price__gte=100)` |

### Examples

```python
from shellspark import Pipeline

# CSV filtering
Pipeline("data.csv").parse("csv").filter(status__eq="active")
Pipeline("data.csv").parse("csv").filter(age__gte=21)
Pipeline("data.csv").parse("csv").filter(price__lt=100)

# JSON filtering (requires jq)
Pipeline("data.json").parse("json").filter(level__eq="error")
Pipeline("data.json").parse("json").filter(status__gte=400)
```

## Chaining Filters

Multiple filters can be chained (AND logic):

```python
# Both conditions must be true
Pipeline("data.csv").parse("csv") \
    .filter(status__eq="active") \
    .filter(age__gte=18)
```

## Filter Optimization

The optimizer automatically pushes filters closer to the data source for better performance:

```python
# You write:
Pipeline("data.csv").parse("csv").select("name", "age").filter(age__gt=21)

# Optimizer rewrites to filter first, then select:
# awk -F',' 'NR>1 && $2 > 21 {print $1, $2}' data.csv
```

## Generated Shell Commands

| Filter Type | Generated Command |
|-------------|------------------|
| `line__contains` (simple) | `grep -F 'value' file` |
| `line__regex` | `grep -E 'pattern' file` |
| `col__eq` (string) | `awk '$N == "value"'` |
| `col__eq` (number) | `awk '$N == 42'` |
| `col__gt` (number) | `awk '$N > 42'` |
| JSON filter | `jq 'select(.col == "value")'` |
