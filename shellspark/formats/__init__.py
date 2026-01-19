"""Format handlers for different file types."""

from shellspark.formats.base import FormatHandler
from shellspark.formats.csv import CSVHandler
from shellspark.formats.text import TextHandler

__all__ = ["FormatHandler", "CSVHandler", "TextHandler", "get_format_handler"]


def get_format_handler(format_name: str, **kwargs) -> FormatHandler:
    """
    Factory function to create format handlers.

    Args:
        format_name: Format name ("csv", "text").
        **kwargs: Format-specific options.
            For CSV: delimiter (str), header (bool).

    Returns:
        FormatHandler instance for the specified format.

    Raises:
        ValueError: If format is unknown.
    """
    format_name = format_name.lower()

    if format_name == "csv":
        delimiter = kwargs.get("delimiter", ",")
        header = kwargs.get("header", True)
        return CSVHandler(delimiter=delimiter, header=header)
    elif format_name == "text":
        return TextHandler()
    else:
        raise ValueError(
            f"Unknown format: {format_name}. Supported formats: csv, text"
        )
