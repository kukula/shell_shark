"""Abstract base class for code generators."""

from abc import ABC, abstractmethod
from typing import Optional

from shellspark.ast import Node


class CodeGenerator(ABC):
    """Abstract base class for shell code generators."""

    @abstractmethod
    def can_handle(self, node: Node) -> bool:
        """Return True if this generator can handle the given node."""
        pass

    @abstractmethod
    def generate(self, node: Node, input_cmd: Optional[str] = None) -> str:
        """
        Generate shell code for the given node.

        Args:
            node: The AST node to generate code for.
            input_cmd: Optional input command to pipe from.
                      If None, the generator should use the source file directly.

        Returns:
            Shell command string.
        """
        pass

    def priority(self) -> int:
        """
        Return priority for this generator (higher = preferred).

        Used when multiple generators can handle the same node type.
        """
        return 0
