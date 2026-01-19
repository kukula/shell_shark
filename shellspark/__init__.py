"""ShellSpark - Compile declarative data transformations into Unix shell pipelines."""

from shellspark.pipeline import Pipeline
from shellspark.ast import (
    Source,
    Filter,
    Select,
    GroupBy,
    Aggregation,
    Sort,
    Limit,
    Distinct,
    Parse,
)

__version__ = "0.1.0"
__all__ = [
    "Pipeline",
    "Source",
    "Filter",
    "Select",
    "GroupBy",
    "Aggregation",
    "Sort",
    "Limit",
    "Distinct",
    "Parse",
]
