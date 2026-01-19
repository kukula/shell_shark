"""JQ code generator for JSON operations."""

import shlex
from typing import Optional

from shellspark.ast import (
    Filter,
    FilterOp,
    Node,
    Parse,
    Select,
    Source,
    walk_tree,
)
from shellspark.codegen.base import CodeGenerator
from shellspark.tools import detect_jq


class JQGenerator(CodeGenerator):
    """Generate jq commands for JSON processing."""

    def can_handle(self, node: Node) -> bool:
        """
        Check if this generator can handle the node tree.

        Returns True if there's a Parse node with format='json'.
        """
        for n in walk_tree(node):
            if isinstance(n, Parse) and n.format == "json":
                return True
        return False

    def generate(self, node: Node, input_cmd: Optional[str] = None) -> str:
        """
        Generate jq command for the node tree.

        Walks the tree and collects all operations to generate
        a single jq command.
        """
        jq_info = detect_jq()
        if jq_info is None:
            raise RuntimeError(
                "jq not found. Install it with:\n"
                "  macOS: brew install jq\n"
                "  Ubuntu/Debian: apt install jq\n"
                "  https://jqlang.github.io/jq/download/"
            )

        # Collect operations from tree
        filters: list[Filter] = []
        select_node: Optional[Select] = None
        source: Optional[Source] = None

        for n in walk_tree(node):
            if isinstance(n, Filter) and n.column is not None:
                filters.append(n)
            elif isinstance(n, Select):
                select_node = n
            elif isinstance(n, Source):
                source = n

        # Build jq filter expression
        jq_parts = []

        # Add select() expressions for filters
        for f in filters:
            jq_filter = self._filter_to_jq(f)
            jq_parts.append(f"select({jq_filter})")

        # Add field projection for select
        if select_node:
            projection = self._select_to_jq(select_node)
            jq_parts.append(projection)

        # Combine with pipe
        if jq_parts:
            jq_expr = " | ".join(jq_parts)
        else:
            jq_expr = "."

        # Build full command
        cmd_parts = [jq_info.path, "-c", shlex.quote(jq_expr)]

        if input_cmd:
            return f"{input_cmd} | {' '.join(cmd_parts)}"
        elif source:
            cmd_parts.append(shlex.quote(source.path))
            return " ".join(cmd_parts)
        else:
            return " ".join(cmd_parts)

    def priority(self) -> int:
        """JQ has higher priority than AWK for JSON operations."""
        return 20

    def _filter_to_jq(self, filter_node: Filter) -> str:
        """Convert Filter node to jq select() expression."""
        column = filter_node.column
        value = filter_node.value
        op = filter_node.op

        # Handle nested field access: user.city -> .user.city
        field = self._field_ref(column)

        # Quote string values, leave numbers as-is
        if isinstance(value, str):
            quoted_value = self._quote_jq_string(value)
        else:
            quoted_value = str(value)

        if op == FilterOp.EQ:
            return f"{field} == {quoted_value}"
        elif op == FilterOp.NE:
            return f"{field} != {quoted_value}"
        elif op == FilterOp.LT:
            return f"{field} < {quoted_value}"
        elif op == FilterOp.LE:
            return f"{field} <= {quoted_value}"
        elif op == FilterOp.GT:
            return f"{field} > {quoted_value}"
        elif op == FilterOp.GE:
            return f"{field} >= {quoted_value}"
        elif op == FilterOp.CONTAINS:
            return f"{field} | contains({quoted_value})"
        elif op == FilterOp.REGEX:
            # Regex uses test() function
            return f'{field} | test({quoted_value})'
        elif op == FilterOp.STARTSWITH:
            return f"{field} | startswith({quoted_value})"
        elif op == FilterOp.ENDSWITH:
            return f"{field} | endswith({quoted_value})"
        else:
            raise ValueError(f"Unsupported filter operation: {op}")

    def _select_to_jq(self, select_node: Select) -> str:
        """Convert Select node to jq field projection."""
        fields = []
        for col in select_node.columns:
            if isinstance(col, int):
                raise ValueError(
                    f"Integer column indices not supported for JSON: {col}"
                )
            fields.append(str(col))

        if len(fields) == 1:
            # Single field - just extract it
            return self._field_ref(fields[0])
        else:
            # Multiple fields - create object
            return "{" + ", ".join(fields) + "}"

    def _field_ref(self, column: str) -> str:
        """Convert column name to jq field reference."""
        # Handle nested field access: user.city -> .user.city
        # If column already starts with dot, use as-is
        if column.startswith("."):
            return column
        return "." + column

    def _quote_jq_string(self, s: str) -> str:
        """Quote a string for use in jq expression."""
        # Escape backslashes and quotes
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
