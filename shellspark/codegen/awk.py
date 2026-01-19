"""AWK code generator for field operations."""

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
from shellspark.formats import get_format_handler
from shellspark.tools import detect_awk


class AWKGenerator(CodeGenerator):
    """Generate AWK commands for field-level operations."""

    def can_handle(self, node: Node) -> bool:
        """
        Check if this generator can handle the node tree.

        Returns True if any node requires column access:
        - Parse node (format parsing)
        - Select node (column projection)
        - Filter with column != None (column-level filter)
        """
        for n in walk_tree(node):
            if isinstance(n, Parse):
                return True
            if isinstance(n, Select):
                return True
            if isinstance(n, Filter) and n.column is not None:
                return True
        return False

    def generate(self, node: Node, input_cmd: Optional[str] = None) -> str:
        """
        Generate AWK command for the node tree.

        Walks the tree and collects all operations to generate
        a single fused AWK command.
        """
        awk_info = detect_awk()

        # Collect operations from tree
        parse_node: Optional[Parse] = None
        filters: list[Filter] = []
        select_node: Optional[Select] = None
        source: Optional[Source] = None

        for n in walk_tree(node):
            if isinstance(n, Parse):
                parse_node = n
            elif isinstance(n, Filter) and n.column is not None:
                filters.append(n)
            elif isinstance(n, Select):
                select_node = n
            elif isinstance(n, Source):
                source = n

        # Get format handler
        if parse_node:
            handler = get_format_handler(
                parse_node.format,
                delimiter=parse_node.delimiter,
                header=parse_node.has_header,
            )
        else:
            # Default to text format
            handler = get_format_handler("text")

        # Build AWK script parts
        parts = []

        # Add field separator flag
        fs = handler.awk_field_separator()
        fs_flag = f"-F{shlex.quote(fs)}" if fs else ""

        # Add header handling code
        header_code = handler.awk_header_code()
        if header_code:
            parts.append(header_code)

        # Build condition and action
        conditions = []
        for f in filters:
            cond = self._filter_to_condition(f, handler)
            conditions.append(cond)

        action = self._select_to_action(select_node, handler, fs)

        # Combine condition and action
        if conditions:
            combined_condition = " && ".join(conditions)
            parts.append(f"{combined_condition}{{{action}}}")
        else:
            parts.append(f"{{{action}}}")

        # Join all parts
        awk_script = " ".join(parts)

        # Build full command
        cmd_parts = [awk_info.path]
        if fs_flag:
            cmd_parts.append(fs_flag)
        cmd_parts.append(shlex.quote(awk_script))

        if input_cmd:
            return f"{input_cmd} | {' '.join(cmd_parts)}"
        elif source:
            cmd_parts.append(shlex.quote(source.path))
            return " ".join(cmd_parts)
        else:
            return " ".join(cmd_parts)

    def priority(self) -> int:
        """AWK has lower priority than grep for line-level operations."""
        return 5

    def _filter_to_condition(self, filter_node: Filter, handler) -> str:
        """Convert Filter node to AWK condition expression."""
        if filter_node.column is None:
            # Line-level filter - use $0
            field = "$0"
        else:
            field = handler.field_ref(filter_node.column)

        value = filter_node.value
        op = filter_node.op

        # Quote string values
        if isinstance(value, str):
            quoted_value = f'"{_escape_awk_string(value)}"'
        else:
            quoted_value = str(value)

        if op == FilterOp.EQ:
            return f"{field}=={quoted_value}"
        elif op == FilterOp.NE:
            return f"{field}!={quoted_value}"
        elif op == FilterOp.LT:
            return f"{field}<{quoted_value}"
        elif op == FilterOp.LE:
            return f"{field}<={quoted_value}"
        elif op == FilterOp.GT:
            return f"{field}>{quoted_value}"
        elif op == FilterOp.GE:
            return f"{field}>={quoted_value}"
        elif op == FilterOp.CONTAINS:
            return f'index({field},{quoted_value})>0'
        elif op == FilterOp.REGEX:
            # Regex match with ~ operator
            return f"{field}~/{_escape_awk_regex(str(value))}/"
        elif op == FilterOp.STARTSWITH:
            return f'index({field},{quoted_value})==1'
        elif op == FilterOp.ENDSWITH:
            # Use substr for endswith
            return f'substr({field},length({field})-length({quoted_value})+1)=={quoted_value}'
        else:
            raise ValueError(f"Unsupported filter operation: {op}")

    def _select_to_action(
        self, select_node: Optional[Select], handler, field_sep: Optional[str]
    ) -> str:
        """Convert Select node to AWK print statement."""
        if select_node is None:
            # No select - print entire line
            return "print"

        # Build field references
        field_refs = []
        for col in select_node.columns:
            field_refs.append(handler.field_ref(col))

        # Join with separator
        output_sep = field_sep if field_sep else " "
        output_sep_escaped = _escape_awk_string(output_sep)

        if len(field_refs) == 1:
            return f"print {field_refs[0]}"
        else:
            # Join fields with separator
            sep_str = f'"{output_sep_escaped}"'
            joined = sep_str.join(field_refs)
            return f"print {joined}"


def _escape_awk_string(s: str) -> str:
    """Escape special characters in AWK string literals."""
    result = []
    for c in s:
        if c == "\\":
            result.append("\\\\")
        elif c == '"':
            result.append('\\"')
        elif c == "\n":
            result.append("\\n")
        elif c == "\t":
            result.append("\\t")
        else:
            result.append(c)
    return "".join(result)


def _escape_awk_regex(s: str) -> str:
    """Escape special characters in AWK regex."""
    result = []
    for c in s:
        if c == "/":
            result.append("\\/")
        elif c == "\\":
            result.append("\\\\")
        else:
            result.append(c)
    return "".join(result)
