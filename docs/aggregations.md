# Aggregations

ShellSpark supports grouping and aggregation operations that compile to efficient AWK code using associative arrays.

## Basic Usage

```python
from shellspark import Pipeline, sum_, avg_, count_

result = (
    Pipeline("sales.csv")
    .parse("csv")
    .group_by("region")
    .agg(
        total=sum_("amount"),
        average=avg_("amount"),
        orders=count_()
    )
    .run()
)
# Returns: [{"region": "West", "total": 5000, "average": 119.05, "orders": 42}, ...]
```

## Aggregation Functions

Import from `shellspark`:

```python
from shellspark import count_, sum_, avg_, min_, max_, first_, last_, countdistinct_, mean_
```

| Function | Description | Example |
|----------|-------------|---------|
| `count_()` | Count all rows | `count_()` |
| `count_(col)` | Count non-null values | `count_("id")` |
| `sum_(col)` | Sum of values | `sum_("amount")` |
| `avg_(col)` | Average of values | `avg_("price")` |
| `mean_(col)` | Alias for `avg_()` | `mean_("score")` |
| `min_(col)` | Minimum value | `min_("age")` |
| `max_(col)` | Maximum value | `max_("salary")` |
| `first_(col)` | First value in group | `first_("name")` |
| `last_(col)` | Last value in group | `last_("timestamp")` |
| `countdistinct_(col)` | Count unique values | `countdistinct_("ip")` |

## Tuple Syntax

As an alternative to helper functions, use tuple syntax `(column, function)`:

```python
result = (
    Pipeline("data.csv")
    .parse("csv")
    .group_by("category")
    .agg(
        total=("amount", "sum"),
        average=("amount", "avg"),
        unique_users=("user_id", "countdistinct"),
        orders=("*", "count")  # "*" for count all
    )
    .run()
)
```

Supported function names: `count`, `sum`, `avg`, `mean`, `min`, `max`, `first`, `last`, `countdistinct`

## Multi-Column Grouping

Group by multiple columns:

```python
result = (
    Pipeline("sales.csv")
    .parse("csv")
    .group_by("region", "product")
    .agg(
        total=sum_("amount"),
        orders=count_()
    )
    .run()
)
# Returns: [{"region": "West", "product": "Widget", "total": 1500, "orders": 15}, ...]
```

## Output Format

When using `group_by().agg()`, the `run()` method returns a list of dictionaries:

- Keys are group columns followed by aggregation aliases
- Numeric values are automatically parsed as int or float
- Order: group keys first, then aggregations in definition order

```python
result = (
    Pipeline("data.csv")
    .parse("csv")
    .group_by("dept")
    .agg(cnt=count_(), total=sum_("salary"))
    .run()
)

# Each row is a dict:
# {"dept": "Engineering", "cnt": 50, "total": 450000}
```

## Generated AWK Code

Aggregations compile to AWK with associative arrays:

```python
Pipeline("data.csv").parse("csv").group_by("dept").agg(total=sum_("salary"), cnt=count_())
```

Generates:

```bash
awk -F',' 'NR>1 { sum[$1]+=$3; cnt[$1]++ } END { for(k in sum) print k, sum[k], cnt[k] }' data.csv
```

## Combining with Other Operations

```python
# Filter, group, aggregate, sort, limit
result = (
    Pipeline("logs.csv")
    .parse("csv")
    .filter(status__gte=400)
    .group_by("path")
    .agg(errors=count_(), avg_status=avg_("status"))
    .sort("errors", desc=True)
    .limit(10)
    .run()
)
```
