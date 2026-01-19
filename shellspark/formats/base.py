"""Abstract base class for format handlers."""

from abc import ABC, abstractmethod
from typing import Optional, Union


class FormatHandler(ABC):
    """
    Abstract base class for format handlers.

    Format handlers provide metadata and AWK code generation
    for different file formats (CSV, JSON, text, etc.).
    """

    @abstractmethod
    def awk_field_separator(self) -> Optional[str]:
        """
        Return the AWK field separator for this format.

        Returns:
            Field separator string (e.g., ",") or None for default whitespace.
        """
        pass

    @abstractmethod
    def awk_header_code(self) -> str:
        """
        Return AWK code to handle headers (if any).

        This code is typically executed for NR==1 to parse column names
        into an associative array.

        Returns:
            AWK code string, or empty string if no header handling needed.
        """
        pass

    @abstractmethod
    def field_ref(self, column: Union[str, int]) -> str:
        """
        Generate AWK field reference for a column.

        Args:
            column: Column name (string) or 1-based index (int).

        Returns:
            AWK field reference (e.g., "$h[\"name\"]" or "$3").

        Raises:
            ValueError: If column type is invalid for this format.
        """
        pass

    @abstractmethod
    def has_header(self) -> bool:
        """
        Return True if this format has a header row.

        Returns:
            True if format has headers, False otherwise.
        """
        pass
