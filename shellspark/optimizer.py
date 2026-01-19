"""Query plan optimizer with rule-based transformation passes."""

from dataclasses import replace
from typing import Optional

from shellspark.ast import (
    Distinct,
    Filter,
    GroupBy,
    Limit,
    Node,
    Parse,
    Select,
    Sort,
    Source,
)


class QueryOptimizer:
    """
    Rule-based query optimizer.

    Transforms AST to improve generated shell command performance.
    Applies the following optimization passes in order:
    1. Filter pushdown - move filters closer to Source
    2. Redundancy elimination - remove no-op operations
    3. Limit optimization - optimize Limit placement
    """

    def optimize(self, node: Node) -> Node:
        """
        Apply all optimization passes to the AST.

        Args:
            node: Root of the AST to optimize.

        Returns:
            Optimized AST (new tree, original unchanged).
        """
        node = self._push_filters_down(node)
        node = self._eliminate_redundancy(node)
        node = self._optimize_limits(node)
        return node

    def _push_filters_down(self, node: Node) -> Node:
        """
        Push Filter nodes closer to Source.

        Filters are pushed down past Select and Parse when safe.
        This reduces the amount of data processed by subsequent operations.

        Rules:
        - Filter can move past Select if filter column is in Select's columns
        - Filter can move past Parse (stays in AWK)
        - Filter cannot move past GroupBy (aggregation changes semantics)
        - Filter cannot move past Sort, Limit, Distinct
        """
        return self._push_filters_recursive(node)

    def _push_filters_recursive(self, node: Node) -> Node:
        """Recursively push filters down through the tree."""
        if isinstance(node, Source):
            return node

        # First, recursively optimize child
        if hasattr(node, "child"):
            optimized_child = self._push_filters_recursive(node.child)
            node = replace(node, child=optimized_child)

        # Now try to push filter down if this is a Filter node
        if isinstance(node, Filter):
            return self._try_push_filter_down(node)

        return node

    def _try_push_filter_down(self, filter_node: Filter) -> Node:
        """Try to push a filter node down past its child."""
        child = filter_node.child

        # Can't push past Source
        if isinstance(child, Source):
            return filter_node

        # Check if we can push past the child
        if self._can_push_filter_past(filter_node, child):
            # Swap filter and child
            swapped = self._swap_filter_past(filter_node, child)
            # Recursively try to push further
            return self._try_push_filter_down_through(swapped)

        return filter_node

    def _can_push_filter_past(self, filter_node: Filter, target: Node) -> bool:
        """Check if a filter can be pushed past a target node."""
        if isinstance(target, Select):
            # Filter column must be in Select's columns (or be line-level filter)
            if filter_node.column is None:
                return True  # Line-level filters can always move
            return filter_node.column in target.columns

        if isinstance(target, Parse):
            return True  # Filters can always move past Parse

        if isinstance(target, (GroupBy, Sort, Limit, Distinct)):
            return False  # Cannot reorder past these

        if isinstance(target, Filter):
            return True  # Filters can move past other filters

        return False

    def _swap_filter_past(self, filter_node: Filter, target: Node) -> Node:
        """
        Swap filter to be below target node.

        Before: Filter(child=Target(child=X))
        After:  Target(child=Filter(child=X))
        """
        if isinstance(target, Select):
            new_filter = replace(filter_node, child=target.child)
            return replace(target, child=new_filter)

        if isinstance(target, Parse):
            new_filter = replace(filter_node, child=target.child)
            return replace(target, child=new_filter)

        if isinstance(target, Filter):
            new_filter = replace(filter_node, child=target.child)
            return replace(target, child=new_filter)

        # Shouldn't reach here if _can_push_filter_past is correct
        return filter_node

    def _try_push_filter_down_through(self, node: Node) -> Node:
        """After swapping, continue trying to push the filter further down."""
        if not hasattr(node, "child"):
            return node

        child = node.child
        if isinstance(child, Filter):
            # Recursively try to push the filter further
            pushed_child = self._try_push_filter_down(child)
            return replace(node, child=pushed_child)

        return node

    def _eliminate_redundancy(self, node: Node) -> Node:
        """
        Remove redundant operations.

        Rules:
        - Remove Distinct after GroupBy (group_by keys are already unique)
        - Remove consecutive identical Filters
        - Remove Select that selects all columns (identity projection) - skipped as we
          don't track available columns
        """
        return self._eliminate_redundancy_recursive(node)

    def _eliminate_redundancy_recursive(self, node: Node) -> Node:
        """Recursively eliminate redundancy in the tree."""
        if isinstance(node, Source):
            return node

        # First, recursively optimize child
        if hasattr(node, "child"):
            optimized_child = self._eliminate_redundancy_recursive(node.child)
            node = replace(node, child=optimized_child)

        # Check for redundant patterns
        if isinstance(node, Distinct):
            # Remove Distinct after GroupBy (group_by keys are already unique)
            if isinstance(node.child, GroupBy):
                return node.child

        if isinstance(node, Filter):
            # Remove consecutive identical Filters
            if isinstance(node.child, Filter):
                if self._filters_identical(node, node.child):
                    return node.child

        return node

    def _filters_identical(self, f1: Filter, f2: Filter) -> bool:
        """Check if two filters are identical (ignoring child)."""
        return (
            f1.column == f2.column
            and f1.op == f2.op
            and f1.value == f2.value
            and f1.case_sensitive == f2.case_sensitive
        )

    def _optimize_limits(self, node: Node) -> Node:
        """
        Optimize Limit placement.

        Rules:
        - Limit stays after Sort (need full sort before limiting)
        - Limit can move before Select (fewer columns doesn't affect row count)
        - Limit cannot move past GroupBy (need all rows for aggregation)
        - Multiple consecutive limits: keep the smaller one
        """
        return self._optimize_limits_recursive(node)

    def _optimize_limits_recursive(self, node: Node) -> Node:
        """Recursively optimize limits in the tree."""
        if isinstance(node, Source):
            return node

        # First, recursively optimize child
        if hasattr(node, "child"):
            optimized_child = self._optimize_limits_recursive(node.child)
            node = replace(node, child=optimized_child)

        # Optimize consecutive limits
        if isinstance(node, Limit):
            if isinstance(node.child, Limit):
                # Merge consecutive limits: take the smaller count
                inner_limit = node.child
                # The outer limit restricts what the inner limit produces
                # So effective count is min(outer, inner)
                effective_count = min(node.count, inner_limit.count)
                # Offset is more complex - outer offset skips from inner's output
                # For simplicity, if outer has offset, we can't easily merge
                if node.offset == 0:
                    return replace(
                        inner_limit,
                        count=effective_count,
                        child=inner_limit.child,
                    )

        return node

    def _get_columns_from_node(self, node: Node) -> Optional[set]:
        """
        Get the set of columns available from a node.

        Returns None if columns cannot be determined.
        """
        if isinstance(node, Select):
            return set(node.columns)
        if isinstance(node, GroupBy):
            # GroupBy produces keys + aggregation aliases
            cols = set(node.keys)
            for agg in node.aggregations:
                if agg.alias:
                    cols.add(agg.alias)
            return cols
        return None
