"""Aggregation helper functions for ShellSpark.

These functions return Aggregation AST nodes for use with Pipeline.agg().

Helper functions use trailing underscore to avoid conflicts with Python builtins:
    sum_, avg_, count_, min_, max_, first_, last_

Example:
    Pipeline("data.csv").parse("csv").group_by("dept").agg(
        total=sum_("salary"),
        average=avg_("salary"),
        headcount=count_()
    )
"""

from typing import Optional

from shellspark.ast import AggFunc, Aggregation


def count_(column: Optional[str] = None) -> Aggregation:
    """
    Create a COUNT aggregation.

    Args:
        column: Column to count. If None, counts all rows (COUNT(*)).

    Returns:
        Aggregation node for COUNT.

    Example:
        >>> count_()
        Aggregation(func=<AggFunc.COUNT: 1>, column=None, alias=None)

        >>> count_("id")
        Aggregation(func=<AggFunc.COUNT: 1>, column='id', alias=None)
    """
    return Aggregation(func=AggFunc.COUNT, column=column)


def sum_(column: str) -> Aggregation:
    """
    Create a SUM aggregation.

    Args:
        column: Column to sum.

    Returns:
        Aggregation node for SUM.

    Example:
        >>> sum_("salary")
        Aggregation(func=<AggFunc.SUM: 2>, column='salary', alias=None)
    """
    return Aggregation(func=AggFunc.SUM, column=column)


def avg_(column: str) -> Aggregation:
    """
    Create an AVG aggregation.

    Args:
        column: Column to average.

    Returns:
        Aggregation node for AVG.

    Example:
        >>> avg_("salary")
        Aggregation(func=<AggFunc.AVG: 3>, column='salary', alias=None)
    """
    return Aggregation(func=AggFunc.AVG, column=column)


def min_(column: str) -> Aggregation:
    """
    Create a MIN aggregation.

    Args:
        column: Column to find minimum of.

    Returns:
        Aggregation node for MIN.

    Example:
        >>> min_("age")
        Aggregation(func=<AggFunc.MIN: 4>, column='age', alias=None)
    """
    return Aggregation(func=AggFunc.MIN, column=column)


def max_(column: str) -> Aggregation:
    """
    Create a MAX aggregation.

    Args:
        column: Column to find maximum of.

    Returns:
        Aggregation node for MAX.

    Example:
        >>> max_("age")
        Aggregation(func=<AggFunc.MAX: 5>, column='age', alias=None)
    """
    return Aggregation(func=AggFunc.MAX, column=column)


def first_(column: str) -> Aggregation:
    """
    Create a FIRST aggregation.

    Args:
        column: Column to get first value of.

    Returns:
        Aggregation node for FIRST.

    Example:
        >>> first_("name")
        Aggregation(func=<AggFunc.FIRST: 6>, column='name', alias=None)
    """
    return Aggregation(func=AggFunc.FIRST, column=column)


def last_(column: str) -> Aggregation:
    """
    Create a LAST aggregation.

    Args:
        column: Column to get last value of.

    Returns:
        Aggregation node for LAST.

    Example:
        >>> last_("timestamp")
        Aggregation(func=<AggFunc.LAST: 7>, column='timestamp', alias=None)
    """
    return Aggregation(func=AggFunc.LAST, column=column)


def countdistinct_(column: str) -> Aggregation:
    """
    Create a COUNT DISTINCT aggregation.

    Args:
        column: Column to count distinct values of.

    Returns:
        Aggregation node for COUNTDISTINCT.

    Example:
        >>> countdistinct_("ip")
        Aggregation(func=<AggFunc.COUNTDISTINCT: 8>, column='ip', alias=None)
    """
    return Aggregation(func=AggFunc.COUNTDISTINCT, column=column)


def mean_(column: str) -> Aggregation:
    """
    Create a MEAN (average) aggregation.

    This is an alias for avg_().

    Args:
        column: Column to average.

    Returns:
        Aggregation node for AVG.

    Example:
        >>> mean_("response_time")
        Aggregation(func=<AggFunc.AVG: 3>, column='response_time', alias=None)
    """
    return Aggregation(func=AggFunc.AVG, column=column)
