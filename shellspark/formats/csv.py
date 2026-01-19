"""CSV format handler."""

from typing import Optional, Union

from shellspark.formats.base import FormatHandler


class CSVHandler(FormatHandler):
    """
    Format handler for CSV files.

    Supports both header-based column access (by name) and
    positional access (by 1-based index).
    """

    def __init__(self, delimiter: str = ",", header: bool = True):
        """
        Create a CSV format handler.

        Args:
            delimiter: Field delimiter character (default: ",").
            header: Whether the CSV has a header row (default: True).
        """
        self._delimiter = delimiter
        self._header = header

    def awk_field_separator(self) -> Optional[str]:
        """Return the CSV delimiter."""
        return self._delimiter

    def awk_header_code(self) -> str:
        """
        Return AWK code to parse header row into associative array.

        The header values are stored in array `h` where h["column_name"] = index.
        """
        if not self._header:
            return ""
        return "NR==1{for(i=1;i<=NF;i++)h[$i]=i; next}"

    def field_ref(self, column: Union[str, int]) -> str:
        """
        Generate AWK field reference for a column.

        Args:
            column: Column name (string) or 1-based index (int).

        Returns:
            AWK field reference.

        Raises:
            ValueError: If string column name used without headers.
        """
        if isinstance(column, int):
            return f"${column}"
        elif isinstance(column, str):
            if not self._header:
                raise ValueError(
                    f"Cannot use column name '{column}' without headers. "
                    "Use integer index instead."
                )
            return f'$h["{column}"]'
        else:
            raise ValueError(f"Invalid column type: {type(column).__name__}")

    def has_header(self) -> bool:
        """Return True if CSV has a header row."""
        return self._header
