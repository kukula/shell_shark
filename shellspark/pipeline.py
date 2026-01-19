"""Pipeline class for building shell transformations."""

from typing import Iterator, Optional, Union

from shellspark.ast import Filter, FilterOp, Node, Parse, Select, Source, walk_tree
from shellspark.codegen.awk import AWKGenerator
from shellspark.codegen.grep import GrepGenerator
from shellspark.executor import ExecutionResult, execute, stream_execute


class Pipeline:
    """
    Builder class for creating data transformation pipelines.

    Transforms are compiled into shell commands using grep, awk, sort, etc.

    Example:
        >>> Pipeline("access.log").filter(line__contains="ERROR").to_shell()
        "grep -F 'ERROR' access.log"
    """

    def __init__(self, path: str, format: str = "text"):
        """
        Create a new Pipeline starting from a file.

        Args:
            path: Path to the input file.
            format: Input format (text, csv, json). Default is text.
        """
        self._root: Node = Source(path=path, format=format)

    def filter(self, **kwargs) -> "Pipeline":
        """
        Add a filter operation to the pipeline.

        Supported kwargs:
            line__contains="X"   - Lines containing substring X
            line__regex="X"      - Lines matching regex X
            line__startswith="X" - Lines starting with X
            line__endswith="X"   - Lines ending with X

        Args:
            **kwargs: Filter specification as keyword arguments.

        Returns:
            Self for method chaining.

        Example:
            >>> Pipeline("log.txt").filter(line__contains="ERROR")
        """
        for key, value in kwargs.items():
            parts = key.split("__")
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid filter key '{key}'. Expected format: 'column__op'"
                )

            column_name, op_name = parts

            # Map column name
            column: Optional[str] = None if column_name == "line" else column_name

            # Map operation name to FilterOp
            op_mapping = {
                "contains": FilterOp.CONTAINS,
                "regex": FilterOp.REGEX,
                "startswith": FilterOp.STARTSWITH,
                "endswith": FilterOp.ENDSWITH,
                "eq": FilterOp.EQ,
                "ne": FilterOp.NE,
                "lt": FilterOp.LT,
                "le": FilterOp.LE,
                "gt": FilterOp.GT,
                "ge": FilterOp.GE,
            }

            if op_name not in op_mapping:
                raise ValueError(
                    f"Unknown filter operation '{op_name}'. "
                    f"Supported: {', '.join(op_mapping.keys())}"
                )

            op = op_mapping[op_name]
            self._root = Filter(child=self._root, column=column, op=op, value=value)

        return self

    def parse(
        self, format: str = "csv", delimiter: str = ",", header: bool = True
    ) -> "Pipeline":
        """
        Parse the input file with the specified format.

        Args:
            format: Input format ("csv", "text"). Default is "csv".
            delimiter: Field delimiter for CSV format. Default is ",".
            header: Whether CSV has a header row. Default is True.

        Returns:
            Self for method chaining.

        Example:
            >>> Pipeline("data.csv").parse(format="csv", header=True)
        """
        self._root = Parse(
            child=self._root,
            format=format,
            delimiter=delimiter,
            has_header=header,
        )
        return self

    def select(self, *columns: Union[str, int]) -> "Pipeline":
        """
        Select specific columns from the data.

        Args:
            *columns: Column names (str) or 1-based indices (int).

        Returns:
            Self for method chaining.

        Example:
            >>> Pipeline("data.csv").parse(format="csv").select("name", "age")
            >>> Pipeline("data.txt").select(1, 3)  # First and third columns
        """
        if not columns:
            raise ValueError("select() requires at least one column")
        self._root = Select(child=self._root, columns=tuple(columns))
        return self

    def _needs_awk(self) -> bool:
        """Check if the pipeline requires AWK (has column-level operations)."""
        for node in walk_tree(self._root):
            if isinstance(node, Parse):
                return True
            if isinstance(node, Select):
                return True
            if isinstance(node, Filter) and node.column is not None:
                return True
        return False

    def to_shell(self) -> str:
        """
        Compile the pipeline to a shell command string.

        Returns:
            Shell command that implements this pipeline.

        Raises:
            ValueError: If the pipeline cannot be compiled.
        """
        return self._generate_command(self._root)

    def _generate_command(self, node: Node) -> str:
        """Generate shell command for the pipeline."""
        # Check if we need AWK (column-level operations)
        if self._needs_awk():
            generator = AWKGenerator()
            if generator.can_handle(node):
                return generator.generate(node)

        # Fall back to node-by-node generation for simple pipelines
        return self._generate_command_recursive(node)

    def _generate_command_recursive(self, node: Node) -> str:
        """Generate shell command for a node, recursively handling children."""
        if isinstance(node, Source):
            # Source nodes don't generate commands themselves
            # They're used by child nodes to get the file path
            return ""

        if isinstance(node, Filter):
            # Generate command for child first
            child_cmd = self._generate_command_recursive(node.child)

            # Use GrepGenerator for line-level filters
            generator = GrepGenerator()
            if generator.can_handle(node):
                if child_cmd:
                    return generator.generate(node, input_cmd=child_cmd)
                else:
                    return generator.generate(node)

            raise ValueError(
                f"Cannot generate code for filter: column={node.column}, op={node.op}"
            )

        raise ValueError(f"Cannot generate code for node type: {type(node).__name__}")

    def run(
        self, timeout: Optional[float] = None, cwd: Optional[str] = None
    ) -> str:
        """
        Execute the pipeline and return stdout.

        Args:
            timeout: Maximum execution time in seconds.
            cwd: Working directory for execution.

        Returns:
            Standard output from the pipeline execution.

        Raises:
            subprocess.TimeoutExpired: If timeout is exceeded.
            RuntimeError: If command exits with non-zero status.
        """
        command = self.to_shell()
        result = execute(command, timeout=timeout, cwd=cwd)

        if result.return_code != 0:
            # grep returns 1 when no matches found - that's not an error
            if result.return_code == 1 and not result.stderr:
                return ""
            raise RuntimeError(
                f"Command failed with exit code {result.return_code}: {result.stderr}"
            )

        return result.stdout

    def run_result(
        self, timeout: Optional[float] = None, cwd: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute the pipeline and return full result.

        Args:
            timeout: Maximum execution time in seconds.
            cwd: Working directory for execution.

        Returns:
            ExecutionResult with stdout, stderr, return_code, and command.
        """
        command = self.to_shell()
        return execute(command, timeout=timeout, cwd=cwd)

    def stream(self, cwd: Optional[str] = None) -> Iterator[str]:
        """
        Execute the pipeline and stream results line by line.

        Args:
            cwd: Working directory for execution.

        Yields:
            Lines of output as they become available.
        """
        command = self.to_shell()
        yield from stream_execute(command, cwd=cwd)

    @property
    def ast(self) -> Node:
        """Return the AST root node for inspection."""
        return self._root
