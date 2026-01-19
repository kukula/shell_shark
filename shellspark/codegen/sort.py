"""Sort, limit, and distinct code generators."""

import shlex
from typing import Optional

from shellspark.ast import (
    Distinct,
    GroupBy,
    Limit,
    Node,
    Parse,
    Sort,
    SortOrder,
    Source,
    walk_tree,
)
from shellspark.codegen.base import CodeGenerator
from shellspark.formats import get_format_handler
from shellspark.tools import detect_sort, get_cpu_count, sort_supports_parallel


class SortGenerator(CodeGenerator):
    """Generate shell commands for Sort, Limit, and Distinct operations."""

    def can_handle(self, node: Node) -> bool:
        """
        Check if this generator can handle the node tree.

        Returns True if node is Sort, Limit, or Distinct.
        """
        return isinstance(node, (Sort, Limit, Distinct))

    def generate(self, node: Node, input_cmd: Optional[str] = None) -> str:
        """
        Generate shell command for Sort, Limit, or Distinct node.

        Args:
            node: The AST node to generate code for.
            input_cmd: Optional input command to pipe from.

        Returns:
            Shell command string.
        """
        if isinstance(node, Sort):
            return self._generate_sort(node, input_cmd)
        elif isinstance(node, Limit):
            return self._generate_limit(node, input_cmd)
        elif isinstance(node, Distinct):
            return self._generate_distinct(node, input_cmd)
        else:
            raise ValueError(f"Cannot handle node type: {type(node).__name__}")

    def _generate_sort(self, node: Sort, input_cmd: Optional[str] = None) -> str:
        """Generate sort command."""
        sort_info = detect_sort()

        # Find Parse, Source, and GroupBy nodes in tree
        parse_node: Optional[Parse] = None
        source: Optional[Source] = None
        group_by_node: Optional[GroupBy] = None

        for n in walk_tree(node):
            if isinstance(n, Parse):
                parse_node = n
            elif isinstance(n, Source):
                source = n
            elif isinstance(n, GroupBy):
                group_by_node = n

        # Get format handler for column index resolution
        handler = None
        delimiter = None
        if parse_node:
            handler = get_format_handler(
                parse_node.format,
                delimiter=parse_node.delimiter,
                header=parse_node.has_header,
            )
            delimiter = parse_node.delimiter

        # Build column name -> index mapping from GroupBy output
        column_map = {}
        if group_by_node:
            # GroupBy output columns: keys + aggregations
            idx = 1
            for key in group_by_node.keys:
                column_map[key] = idx
                idx += 1
            for agg in group_by_node.aggregations:
                alias = agg.alias or agg.column or "value"
                column_map[alias] = idx
                idx += 1
            # GroupBy outputs using the input delimiter (or comma by default)
            # The AWK generator uses: output_sep = fs if fs else ","
            if delimiter is None:
                delimiter = ","

        # Build sort flags
        flags = []

        # Add field separator
        if delimiter:
            flags.append(f"-t{shlex.quote(delimiter)}")

        # Add sort key specifications
        for column, order in node.columns:
            key_spec = self._build_sort_key(
                column, order, node.numeric, handler, column_map
            )
            flags.append(key_spec)

        # Add parallel flag for GNU sort if available
        if sort_supports_parallel():
            cpu = get_cpu_count()
            if cpu > 1:
                flags.append(f"--parallel={cpu}")
                flags.append("-S 80%")

        # Build command
        cmd_parts = [sort_info.path] + flags

        if input_cmd:
            return f"{input_cmd} | {' '.join(cmd_parts)}"
        elif source:
            cmd_parts.append(shlex.quote(source.path))
            return " ".join(cmd_parts)
        else:
            return " ".join(cmd_parts)

    def _build_sort_key(
        self,
        column: str,
        order: SortOrder,
        numeric: bool,
        handler,
        column_map: Optional[dict] = None,
    ) -> str:
        """Build sort -k specification for a column."""
        col_index = None

        # First, try to look up column name in the column_map (from GroupBy)
        if column_map and column in column_map:
            col_index = column_map[column]
        else:
            # Try to parse as integer
            try:
                col_index = int(column)
            except ValueError:
                # Check if handler has header info
                if handler and hasattr(handler, "_header") and handler._header:
                    raise ValueError(
                        f"Sort by column name '{column}' requires header parsing. "
                        "Use numeric column index instead, or ensure the data "
                        "is pre-processed with AWK."
                    )
                else:
                    raise ValueError(
                        f"Cannot resolve column name '{column}'. "
                        "Use numeric column index instead."
                    )

        # Build key spec: -k<start>,<end>[n][r]
        key_parts = [f"-k{col_index},{col_index}"]

        # Add numeric flag
        if numeric:
            key_parts.append("n")

        # Add reverse flag for descending
        if order == SortOrder.DESC:
            key_parts.append("r")

        return "".join(key_parts)

    def _generate_limit(self, node: Limit, input_cmd: Optional[str] = None) -> str:
        """Generate head/tail command for limit."""
        # Find Source node
        source: Optional[Source] = None
        for n in walk_tree(node):
            if isinstance(n, Source):
                source = n

        if node.offset > 0:
            # Use tail to skip, then head to limit
            # tail -n +<offset+1> skips first `offset` lines
            tail_cmd = f"tail -n +{node.offset + 1}"
            head_cmd = f"head -n {node.count}"

            if input_cmd:
                return f"{input_cmd} | {tail_cmd} | {head_cmd}"
            elif source:
                return f"{tail_cmd} {shlex.quote(source.path)} | {head_cmd}"
            else:
                return f"{tail_cmd} | {head_cmd}"
        else:
            # Simple head
            head_cmd = f"head -n {node.count}"

            if input_cmd:
                return f"{input_cmd} | {head_cmd}"
            elif source:
                return f"{head_cmd} {shlex.quote(source.path)}"
            else:
                return head_cmd

    def _generate_distinct(self, node: Distinct, input_cmd: Optional[str] = None) -> str:
        """Generate sort -u command for distinct."""
        sort_info = detect_sort()

        # Find Parse and Source nodes
        parse_node: Optional[Parse] = None
        source: Optional[Source] = None

        for n in walk_tree(node):
            if isinstance(n, Parse):
                parse_node = n
            elif isinstance(n, Source):
                source = n

        # Build sort -u command
        flags = ["-u"]

        # Add field separator for CSV
        if parse_node:
            delimiter = parse_node.delimiter
            flags.insert(0, f"-t{shlex.quote(delimiter)}")

        # Add specific column keys if specified
        if node.columns:
            # For specific columns, we need to specify which fields to compare
            # sort -u compares entire lines, so we'd need -k flags
            for col in node.columns:
                try:
                    col_index = int(col)
                except ValueError:
                    raise ValueError(
                        f"Distinct by column name '{col}' requires numeric index."
                    )
                flags.append(f"-k{col_index},{col_index}")

        # Build command
        cmd_parts = [sort_info.path] + flags

        if input_cmd:
            return f"{input_cmd} | {' '.join(cmd_parts)}"
        elif source:
            cmd_parts.append(shlex.quote(source.path))
            return " ".join(cmd_parts)
        else:
            return " ".join(cmd_parts)

    def priority(self) -> int:
        """Sort generator has medium priority."""
        return 5
