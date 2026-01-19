"""AST nodes for ShellSpark query plans."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, Union


class AggFunc(Enum):
    """Supported aggregation functions.

    Attributes:
        COUNT: Count rows or non-null values.
        SUM: Sum of numeric values.
        AVG: Average (mean) of numeric values.
        MIN: Minimum value.
        MAX: Maximum value.
        FIRST: First value in group.
        LAST: Last value in group.
        COUNTDISTINCT: Count of unique values.
    """

    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()
    FIRST = auto()
    LAST = auto()
    COUNTDISTINCT = auto()


class SortOrder(Enum):
    """Sort order for sort operations.

    Attributes:
        ASC: Ascending order (smallest to largest).
        DESC: Descending order (largest to smallest).
    """

    ASC = auto()
    DESC = auto()


class FilterOp(Enum):
    """Filter comparison operators.

    Attributes:
        EQ: Equality (==).
        NE: Not equal (!=).
        LT: Less than (<).
        LE: Less than or equal (<=).
        GT: Greater than (>).
        GE: Greater than or equal (>=).
        CONTAINS: Substring match.
        REGEX: Regular expression match.
        STARTSWITH: String prefix match.
        ENDSWITH: String suffix match.
    """

    EQ = auto()  # ==
    NE = auto()  # !=
    LT = auto()  # <
    LE = auto()  # <=
    GT = auto()  # >
    GE = auto()  # >=
    CONTAINS = auto()  # substring match
    REGEX = auto()  # regex match
    STARTSWITH = auto()
    ENDSWITH = auto()


@dataclass(frozen=True)
class Node:
    """Base class for all AST nodes."""

    pass


@dataclass(frozen=True)
class Source(Node):
    """Source node representing input file(s)."""

    path: str
    format: str = "text"  # text, csv, json


@dataclass(frozen=True)
class Filter(Node):
    """Filter node for row filtering."""

    child: Node
    column: Optional[str]  # None for line-level filtering
    op: FilterOp
    value: Any
    case_sensitive: bool = True


@dataclass(frozen=True)
class Select(Node):
    """Select node for column projection."""

    child: Node
    columns: tuple[Union[str, int], ...]  # column names or indices (1-based for awk)


@dataclass(frozen=True)
class Aggregation(Node):
    """Single aggregation specification."""

    func: AggFunc
    column: Optional[str] = None  # None for COUNT(*)
    alias: Optional[str] = None


@dataclass(frozen=True)
class GroupBy(Node):
    """GroupBy node for aggregations."""

    child: Node
    keys: tuple[str, ...]
    aggregations: tuple[Aggregation, ...]


@dataclass(frozen=True)
class Sort(Node):
    """Sort node."""

    child: Node
    columns: tuple[tuple[str, SortOrder], ...]  # (column, order) pairs
    numeric: bool = False


@dataclass(frozen=True)
class Limit(Node):
    """Limit node to restrict output rows."""

    child: Node
    count: int
    offset: int = 0


@dataclass(frozen=True)
class Distinct(Node):
    """Distinct node to remove duplicates."""

    child: Node
    columns: Optional[tuple[str, ...]] = None  # None means all columns


@dataclass(frozen=True)
class Parse(Node):
    """Parse node to handle format-specific parsing."""

    child: Node
    format: str  # csv, json, text
    delimiter: str = ","
    has_header: bool = True


@dataclass(frozen=True)
class Join(Node):
    """Join node for combining two datasets."""

    left: Node
    right: Node
    on: str  # join column
    how: str = "inner"  # inner, left, right


@dataclass(frozen=True)
class Parallel(Node):
    """Parallel execution wrapper for multi-file processing.

    Wraps a pipeline to execute it in parallel across multiple files
    matching a glob pattern using find | xargs -P.

    Attributes:
        child: The child pipeline to execute in parallel.
        workers: Number of parallel workers. None means auto (CPU count).
    """

    child: Node
    workers: Optional[int] = None  # None = auto (CPU count)


def walk_tree(node: Node):
    """Generator that yields all nodes in the tree (depth-first)."""
    yield node
    if hasattr(node, "child"):
        yield from walk_tree(node.child)
    if hasattr(node, "left"):
        yield from walk_tree(node.left)
    if hasattr(node, "right"):
        yield from walk_tree(node.right)


def get_source(node: Node) -> Optional[Source]:
    """Find the Source node in a query tree."""
    for n in walk_tree(node):
        if isinstance(n, Source):
            return n
    return None
