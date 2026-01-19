"""ShellSpark - Compile declarative data transformations into Unix shell pipelines."""

from shellspark.pipeline import Pipeline
from shellspark.ast import (
    Source,
    Filter,
    Select,
    GroupBy,
    Aggregation,
    Sort,
    SortOrder,
    Limit,
    Distinct,
    Parse,
    Parallel,
)
from shellspark.aggregations import (
    count_,
    sum_,
    avg_,
    min_,
    max_,
    first_,
    last_,
)
from shellspark.optimizer import QueryOptimizer
from shellspark.codegen.jq import JQGenerator

__version__ = "0.1.0"
__all__ = [
    "Pipeline",
    "Source",
    "Filter",
    "Select",
    "GroupBy",
    "Aggregation",
    "Sort",
    "SortOrder",
    "Limit",
    "Distinct",
    "Parse",
    "Parallel",
    # Aggregation helpers
    "count_",
    "sum_",
    "avg_",
    "min_",
    "max_",
    "first_",
    "last_",
    # Optimizer
    "QueryOptimizer",
    # Code generators
    "JQGenerator",
]
