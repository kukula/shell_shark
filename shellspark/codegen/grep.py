"""Grep code generator for filter operations."""

import shlex
from typing import Optional

from shellspark.ast import Filter, FilterOp, Node, Source, get_source
from shellspark.codegen.base import CodeGenerator
from shellspark.tools import detect_grep, grep_supports_pcre


class GrepGenerator(CodeGenerator):
    """Generate grep/ripgrep commands for filter operations."""

    def can_handle(self, node: Node) -> bool:
        """Check if this is a simple filter we can handle with grep."""
        if not isinstance(node, Filter):
            return False

        # Only handle line-level filters (no column specified)
        if node.column is not None:
            return False

        # Only handle CONTAINS, REGEX, STARTSWITH, ENDSWITH
        return node.op in (
            FilterOp.CONTAINS,
            FilterOp.REGEX,
            FilterOp.STARTSWITH,
            FilterOp.ENDSWITH,
        )

    def generate(self, node: Node, input_cmd: Optional[str] = None) -> str:
        """Generate grep command for filter node."""
        if not isinstance(node, Filter):
            raise ValueError(f"GrepGenerator cannot handle {type(node).__name__}")

        grep_info = detect_grep()
        value = str(node.value)

        # Build grep flags
        flags = []

        if grep_info.name == "rg":
            # ripgrep options
            if not node.case_sensitive:
                flags.append("-i")

            if node.op == FilterOp.CONTAINS:
                flags.append("-F")  # Fixed string
                pattern = value
            elif node.op == FilterOp.REGEX:
                pattern = value
            elif node.op == FilterOp.STARTSWITH:
                pattern = f"^{_escape_regex(value)}"
            elif node.op == FilterOp.ENDSWITH:
                pattern = f"{_escape_regex(value)}$"
            else:
                pattern = value

            # ripgrep needs --no-filename for single file consistency
            flags.append("--no-filename")

        else:
            # GNU/BSD grep options
            if not node.case_sensitive:
                flags.append("-i")

            if node.op == FilterOp.CONTAINS:
                flags.append("-F")  # Fixed string (fast)
                pattern = value
            elif node.op == FilterOp.REGEX:
                if grep_supports_pcre():
                    flags.append("-P")  # PCRE
                else:
                    flags.append("-E")  # Extended regex
                pattern = value
            elif node.op == FilterOp.STARTSWITH:
                flags.append("-E")
                pattern = f"^{_escape_regex(value)}"
            elif node.op == FilterOp.ENDSWITH:
                flags.append("-E")
                pattern = f"{_escape_regex(value)}$"
            else:
                pattern = value

        # Build command
        flags_str = " ".join(flags)
        quoted_pattern = shlex.quote(pattern)

        if input_cmd:
            # Piped input
            return f"{input_cmd} | {grep_info.path} {flags_str} {quoted_pattern}"
        else:
            # Direct file input
            source = get_source(node)
            if source:
                quoted_path = shlex.quote(source.path)
                return f"{grep_info.path} {flags_str} {quoted_pattern} {quoted_path}"
            else:
                # Read from stdin
                return f"{grep_info.path} {flags_str} {quoted_pattern}"

    def priority(self) -> int:
        """Grep is preferred for simple string matching."""
        return 10


def _escape_regex(s: str) -> str:
    """Escape special regex characters."""
    special = r"\.^$*+?{}[]|()"
    result = []
    for c in s:
        if c in special:
            result.append("\\")
        result.append(c)
    return "".join(result)
