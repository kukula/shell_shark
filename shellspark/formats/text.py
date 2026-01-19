"""Plain text format handler."""

from typing import Optional, Union

from shellspark.formats.base import FormatHandler


class TextHandler(FormatHandler):
    """
    Format handler for plain text files.

    Uses default whitespace field separation with no headers.
    Only supports positional column access (1-based indices).
    """

    def awk_field_separator(self) -> Optional[str]:
        """Return None for default whitespace splitting."""
        return None

    def awk_header_code(self) -> str:
        """Return empty string (no headers in plain text)."""
        return ""

    def field_ref(self, column: Union[str, int]) -> str:
        """
        Generate AWK field reference for a column.

        Args:
            column: 1-based column index (int only).

        Returns:
            AWK field reference (e.g., "$3").

        Raises:
            ValueError: If column is a string (not supported without headers).
        """
        if isinstance(column, int):
            return f"${column}"
        elif isinstance(column, str):
            raise ValueError(
                f"Cannot use column name '{column}' in text format. "
                "Text format has no headers. Use integer index instead."
            )
        else:
            raise ValueError(f"Invalid column type: {type(column).__name__}")

    def has_header(self) -> bool:
        """Return False (text format has no headers)."""
        return False
