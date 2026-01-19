"""Pipeline class for building shell transformations."""

from typing import Iterator, Optional, Union

import os
import shlex

from shellspark.tools import detect_awk, detect_grep
from shellspark.ast import (
    AggFunc,
    Aggregation,
    Distinct,
    Filter,
    FilterOp,
    GroupBy,
    Limit,
    Node,
    Parallel,
    Parse,
    Select,
    Sort,
    SortOrder,
    Source,
    get_source,
    walk_tree,
)
from shellspark.codegen.awk import AWKGenerator
from shellspark.codegen.grep import GrepGenerator
from shellspark.codegen.jq import JQGenerator
from shellspark.codegen.sort import SortGenerator
from shellspark.executor import ExecutionResult, execute, stream_execute
from shellspark.optimizer import QueryOptimizer


# Module-level cache for compiled shell commands
_command_cache: dict[tuple, str] = {}
_CACHE_MAX_SIZE = 128


def _get_cached_command(key: tuple) -> Optional[str]:
    """Get cached shell command by key."""
    return _command_cache.get(key)


def _set_cached_command(key: tuple, cmd: str) -> None:
    """Cache a shell command, evicting oldest entries if full."""
    if len(_command_cache) >= _CACHE_MAX_SIZE:
        # Simple eviction: clear oldest half
        keys = list(_command_cache.keys())[: len(_command_cache) // 2]
        for k in keys:
            del _command_cache[k]
    _command_cache[key] = cmd


def clear_command_cache() -> None:
    """Clear the command cache.

    Use this after changing tool configuration or to free memory.
    The cache stores compiled shell commands keyed by AST hash and tool paths.

    Example:
        >>> from shellspark import clear_command_cache
        >>> clear_command_cache()
    """
    _command_cache.clear()


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
        self._pending_group_keys: Optional[tuple[str, ...]] = None

    def _get_cache_key(self) -> tuple:
        """Generate cache key from AST and tool configuration."""
        # Include AST hash + tool info for complete key
        # Frozen dataclasses are hashable via __hash__
        return (hash(self._root), detect_awk().path, detect_grep().path)

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
                "lte": FilterOp.LE,  # alias
                "gt": FilterOp.GT,
                "ge": FilterOp.GE,
                "gte": FilterOp.GE,  # alias
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

    def group_by(self, *columns: str) -> "Pipeline":
        """
        Group data by one or more columns.

        Must be followed by agg() to specify aggregations.

        Args:
            *columns: Column names to group by.

        Returns:
            Self for method chaining.

        Example:
            >>> Pipeline("data.csv").parse("csv").group_by("dept").agg(cnt=count_())
        """
        if not columns:
            raise ValueError("group_by() requires at least one column")
        self._pending_group_keys = tuple(columns)
        return self

    def agg(self, **aggregations: Union[Aggregation, tuple]) -> "Pipeline":
        """
        Apply aggregations to grouped data.

        Must be called after group_by().

        Args:
            **aggregations: Named aggregations using helper functions or tuples.
                Keys become output column aliases.
                Values can be:
                - Aggregation objects: sum_("col"), avg_("col"), count_()
                - Tuples: ("col", "sum"), ("*", "count"), ("col", "countdistinct")

        Supported tuple functions: count, sum, avg, mean, min, max, countdistinct

        Returns:
            Self for method chaining.

        Example:
            >>> from shellspark import sum_, avg_, count_
            >>> Pipeline("data.csv").parse("csv").group_by("dept").agg(
            ...     total=sum_("salary"),
            ...     average=avg_("salary"),
            ...     headcount=count_()
            ... )
            >>> # Or using tuple syntax:
            >>> Pipeline("data.csv").parse("csv").group_by("dept").agg(
            ...     total=("salary", "sum"),
            ...     average=("salary", "avg"),
            ...     headcount=("*", "count")
            ... )
        """
        if self._pending_group_keys is None:
            raise ValueError("agg() must be called after group_by()")

        if not aggregations:
            raise ValueError("agg() requires at least one aggregation")

        # Map string function names to AggFunc enum
        func_mapping = {
            "count": AggFunc.COUNT,
            "sum": AggFunc.SUM,
            "avg": AggFunc.AVG,
            "mean": AggFunc.AVG,  # alias
            "min": AggFunc.MIN,
            "max": AggFunc.MAX,
            "first": AggFunc.FIRST,
            "last": AggFunc.LAST,
            "countdistinct": AggFunc.COUNTDISTINCT,
        }

        # Create Aggregation nodes with aliases
        agg_nodes = []
        for alias, agg in aggregations.items():
            if isinstance(agg, Aggregation):
                # Already an Aggregation node
                agg_with_alias = Aggregation(
                    func=agg.func, column=agg.column, alias=alias
                )
            elif isinstance(agg, tuple) and len(agg) == 2:
                # Tuple syntax: ("column", "func")
                col, func_name = agg
                func_name_lower = func_name.lower()
                if func_name_lower not in func_mapping:
                    raise ValueError(
                        f"Unknown aggregation function '{func_name}'. "
                        f"Supported: {', '.join(func_mapping.keys())}"
                    )
                func = func_mapping[func_name_lower]
                # Handle "*" column (count all)
                column = None if col == "*" else col
                agg_with_alias = Aggregation(func=func, column=column, alias=alias)
            else:
                raise TypeError(
                    f"Expected Aggregation or tuple for '{alias}', got {type(agg).__name__}. "
                    "Use helper functions like sum_(), avg_(), count_() "
                    "or tuples like ('column', 'sum')."
                )
            agg_nodes.append(agg_with_alias)

        # Create GroupBy node
        self._root = GroupBy(
            child=self._root,
            keys=self._pending_group_keys,
            aggregations=tuple(agg_nodes),
        )

        # Clear pending group keys
        self._pending_group_keys = None

        return self

    def sort(
        self,
        column: Union[str, int],
        order: SortOrder = SortOrder.ASC,
        numeric: bool = False,
        desc: bool = False,
    ) -> "Pipeline":
        """
        Sort by a column.

        Args:
            column: Column name (str) or 1-based index (int) to sort by.
            order: Sort order (SortOrder.ASC or SortOrder.DESC). Default is ASC.
            numeric: If True, sort numerically. Default is False (lexicographic).
            desc: If True, sort in descending order. Shorthand for order=SortOrder.DESC.

        Returns:
            Self for method chaining.

        Example:
            >>> Pipeline("data.csv").parse("csv").sort("age", numeric=True)
            >>> Pipeline("data.csv").parse("csv").sort("name", order=SortOrder.DESC)
            >>> Pipeline("data.csv").parse("csv").sort("name", desc=True)
        """
        col_str = str(column)
        # desc=True overrides order parameter
        sort_order = SortOrder.DESC if desc else order
        self._root = Sort(
            child=self._root,
            columns=((col_str, sort_order),),
            numeric=numeric,
        )
        return self

    def limit(self, count: int, offset: int = 0) -> "Pipeline":
        """
        Limit output to a number of rows.

        Args:
            count: Maximum number of rows to return. Must be >= 1.
            offset: Number of rows to skip before returning. Default is 0.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If count < 1 or offset < 0.

        Example:
            >>> Pipeline("data.csv").limit(10)  # First 10 rows
            >>> Pipeline("data.csv").limit(10, offset=5)  # Skip 5, take 10
        """
        if count < 1:
            raise ValueError("limit count must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        self._root = Limit(child=self._root, count=count, offset=offset)
        return self

    def distinct(self, *columns: Union[str, int]) -> "Pipeline":
        """
        Remove duplicate rows.

        Args:
            *columns: Optional column names or indices to consider for uniqueness.
                     If not specified, all columns are compared.

        Returns:
            Self for method chaining.

        Example:
            >>> Pipeline("data.csv").distinct()  # Unique rows
            >>> Pipeline("data.csv").distinct("name")  # Unique by name column
        """
        cols = tuple(str(c) for c in columns) if columns else None
        self._root = Distinct(child=self._root, columns=cols)
        return self

    def parallel(self, workers: Optional[int] = None) -> "Pipeline":
        """
        Enable parallel processing for glob patterns.

        Processes files matching the glob pattern in parallel using
        find | xargs -P. This is useful for processing multiple files
        like "logs/*.log" across multiple CPU cores.

        Args:
            workers: Number of parallel workers. Default is CPU count.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If the pipeline contains operations that cannot
                       be parallelized (sort, distinct, group_by/agg).

        Example:
            >>> Pipeline("logs/*.log").filter(line__contains="ERROR").parallel(workers=4).to_shell()
            'find logs -name '*.log' -print0 | xargs -0 -P4 grep -F 'ERROR''
        """
        # Validate that we don't have operations that require global state
        self._validate_parallel_operations(self._root)

        self._root = Parallel(child=self._root, workers=workers)
        return self

    def _validate_parallel_operations(self, node: Node) -> None:
        """Validate that the pipeline can be parallelized.

        Operations that require global state across all files cannot
        be parallelized: sort, distinct, group_by/agg.
        """
        for n in walk_tree(node):
            if isinstance(n, Sort):
                raise ValueError(
                    "Cannot parallelize pipeline with sort(). "
                    "Sort requires all data to be collected first."
                )
            if isinstance(n, Distinct):
                raise ValueError(
                    "Cannot parallelize pipeline with distinct(). "
                    "Distinct requires all data to be collected first."
                )
            if isinstance(n, GroupBy):
                raise ValueError(
                    "Cannot parallelize pipeline with group_by()/agg(). "
                    "Aggregations require all data to be collected first."
                )
            if isinstance(n, Limit):
                raise ValueError(
                    "Cannot parallelize pipeline with limit(). "
                    "Limit requires all data to be collected first."
                )

    def _needs_awk(self) -> bool:
        """Check if the pipeline requires AWK (has column-level operations)."""
        for node in walk_tree(self._root):
            if isinstance(node, Parse):
                return True
            if isinstance(node, Select):
                return True
            if isinstance(node, GroupBy):
                return True
            if isinstance(node, Filter) and node.column is not None:
                return True
        return False

    def _is_json_pipeline(self, node: Node) -> bool:
        """Check if pipeline processes JSON data."""
        for n in walk_tree(node):
            if isinstance(n, Parse) and n.format == "json":
                return True
        return False

    def to_shell(self) -> str:
        """
        Compile the pipeline to a shell command string (cached).

        Returns:
            Shell command that implements this pipeline.

        Raises:
            ValueError: If the pipeline cannot be compiled.
        """
        cache_key = self._get_cache_key()

        # Check cache
        cached = _get_cached_command(cache_key)
        if cached is not None:
            return cached

        # Generate command
        optimizer = QueryOptimizer()
        optimized_root = optimizer.optimize(self._root)
        command = self._generate_command(optimized_root)

        # Cache and return
        _set_cached_command(cache_key, command)
        return command

    def _generate_command(self, node: Node) -> str:
        """Generate shell command for the pipeline."""
        # Handle Parallel at top level
        if isinstance(node, Parallel):
            return self._generate_parallel(node)

        # Handle Sort, Limit, Distinct at the top level
        if isinstance(node, (Sort, Limit, Distinct)):
            return self._generate_sort_limit_distinct(node)

        # Check for JSON first (higher priority)
        if self._is_json_pipeline(node):
            generator = JQGenerator()
            if generator.can_handle(node):
                return generator.generate(node)

        # Check if we need AWK (column-level operations)
        if self._needs_awk():
            generator = AWKGenerator()
            if generator.can_handle(node):
                return generator.generate(node)

        # Fall back to node-by-node generation for simple pipelines
        return self._generate_command_recursive(node)

    def _parse_glob_pattern(self, pattern: str) -> tuple:
        """Parse a glob pattern into directory and filename pattern.

        Args:
            pattern: A glob pattern like 'logs/*.log' or 'data/**/*.csv'.

        Returns:
            Tuple of (directory, filename_pattern).

        Examples:
            >>> _parse_glob_pattern('logs/*.log')
            ('logs', '*.log')
            >>> _parse_glob_pattern('*.txt')
            ('.', '*.txt')
        """
        directory = os.path.dirname(pattern) or "."
        filename = os.path.basename(pattern)
        return directory, filename

    def _generate_parallel(self, node: Parallel) -> str:
        """Generate find | xargs -P command for parallel execution.

        Args:
            node: Parallel AST node.

        Returns:
            Shell command using find | xargs for parallel processing.
        """
        from shellspark.tools import get_parallel_workers

        # Get source and parse pattern
        source = get_source(node)
        if source is None:
            raise ValueError("Parallel pipeline must have a Source node")

        directory, filename_pattern = self._parse_glob_pattern(source.path)

        # Get worker count
        workers = get_parallel_workers(node.workers)

        # Generate inner command (without the source file - xargs provides it)
        inner_cmd = self._generate_inner_command(node.child)

        # Build find | xargs command
        # -print0 and -0 handle filenames with spaces/special chars
        find_cmd = f"find {shlex.quote(directory)} -name {shlex.quote(filename_pattern)} -print0"
        xargs_cmd = f"xargs -0 -P{workers} {inner_cmd}"

        return f"{find_cmd} | {xargs_cmd}"

    def _generate_inner_command(self, node: Node) -> str:
        """Generate command for use with xargs (no source file in command).

        The generated command expects the file path to be provided by xargs
        as the last argument.

        Args:
            node: AST node to generate command for.

        Returns:
            Shell command without source file path.
        """
        # Check for JSON first (higher priority)
        if self._is_json_pipeline(node):
            generator = JQGenerator()
            if generator.can_handle(node):
                # Get the full command and strip the source file
                full_cmd = generator.generate(node)
                return self._strip_source_from_command(full_cmd, node)

        # Check if we need AWK (column-level operations)
        needs_awk = False
        for n in walk_tree(node):
            if isinstance(n, Parse):
                needs_awk = True
                break
            if isinstance(n, Select):
                needs_awk = True
                break
            if isinstance(n, Filter) and n.column is not None:
                needs_awk = True
                break

        if needs_awk:
            generator = AWKGenerator()
            if generator.can_handle(node):
                full_cmd = generator.generate(node)
                return self._strip_source_from_command(full_cmd, node)

        # Fall back to grep-style generation
        return self._generate_inner_recursive(node)

    def _strip_source_from_command(self, cmd: str, node: Node) -> str:
        """Strip the source file path from a command.

        Commands like 'awk ... file.txt' become 'awk ...' so xargs can
        append the filename.

        Args:
            cmd: Full command with source file.
            node: AST node to find Source.

        Returns:
            Command without source file path.
        """
        source = get_source(node)
        if source is None:
            return cmd

        # The source path is typically at the end of the command
        quoted_path = shlex.quote(source.path)

        # Try to remove quoted path from end
        if cmd.endswith(quoted_path):
            return cmd[: -len(quoted_path)].rstrip()

        # Try unquoted path (simple paths without special chars)
        if cmd.endswith(source.path):
            return cmd[: -len(source.path)].rstrip()

        # If command ends with '<' for input redirection
        if f"< {quoted_path}" in cmd:
            return cmd.replace(f"< {quoted_path}", "").rstrip()

        return cmd

    def _generate_inner_recursive(self, node: Node) -> str:
        """Generate shell command for xargs, handling filters recursively.

        Args:
            node: AST node to generate command for.

        Returns:
            Shell command for use with xargs.
        """
        if isinstance(node, Source):
            return ""

        if isinstance(node, Filter):
            # For filters, we use GrepGenerator but without the file
            generator = GrepGenerator()
            if generator.can_handle(node):
                # Generate with a placeholder and strip it
                full_cmd = generator.generate(node)
                return self._strip_source_from_command(full_cmd, node)

        raise ValueError(f"Cannot generate inner code for node type: {type(node).__name__}")

    def _generate_sort_limit_distinct(self, node: Node) -> str:
        """Generate command for Sort, Limit, or Distinct with child command."""
        sort_generator = SortGenerator()

        # Generate child command first
        child_cmd = self._generate_child_command(node.child)

        # Generate sort/limit/distinct command
        if child_cmd:
            return sort_generator.generate(node, input_cmd=child_cmd)
        else:
            return sort_generator.generate(node)

    def _generate_child_command(self, node: Node) -> str:
        """Generate command for a child node (used by sort/limit/distinct)."""
        if isinstance(node, Source):
            return ""

        if isinstance(node, (Sort, Limit, Distinct)):
            return self._generate_sort_limit_distinct(node)

        # Check for JSON first (higher priority)
        if self._is_json_pipeline(node):
            generator = JQGenerator()
            if generator.can_handle(node):
                return generator.generate(node)

        # Check if child needs AWK
        needs_awk = False
        for n in walk_tree(node):
            if isinstance(n, Parse):
                needs_awk = True
                break
            if isinstance(n, Select):
                needs_awk = True
                break
            if isinstance(n, GroupBy):
                needs_awk = True
                break
            if isinstance(n, Filter) and n.column is not None:
                needs_awk = True
                break

        if needs_awk:
            generator = AWKGenerator()
            if generator.can_handle(node):
                return generator.generate(node)

        # Fall back to recursive generation
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

    def _get_output_columns(self) -> Optional[list[str]]:
        """Get output column names from the AST if structured output is expected."""
        for node in walk_tree(self._root):
            if isinstance(node, GroupBy):
                # Column order: group keys + aggregation aliases
                columns = list(node.keys)
                for agg in node.aggregations:
                    columns.append(agg.alias or agg.column or "value")
                return columns
        return None

    def _get_output_delimiter(self) -> str:
        """Get the output delimiter based on the pipeline structure."""
        # AWK codegen uses the input format's delimiter for output
        # Look for Parse node to determine delimiter
        for node in walk_tree(self._root):
            if isinstance(node, Parse):
                return node.delimiter
        # Default to tab for non-CSV/non-parsed pipelines
        return "\t"

    def _parse_structured_output(
        self, stdout: str, columns: list[str], delimiter: str = "\t"
    ) -> list[dict]:
        """Parse TSV output into list of dicts."""
        results = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            values = line.split(delimiter)
            row = {}
            for i, col in enumerate(columns):
                if i < len(values):
                    # Try to convert numeric values
                    val = values[i]
                    try:
                        # Try int first
                        row[col] = int(val)
                    except ValueError:
                        try:
                            # Then float
                            row[col] = float(val)
                        except ValueError:
                            # Keep as string
                            row[col] = val
                else:
                    row[col] = None
            results.append(row)
        return results

    def run(
        self, timeout: Optional[float] = None, cwd: Optional[str] = None
    ) -> Union[list[str], list[dict]]:
        """
        Execute the pipeline and return results.

        For pipelines with structured output (e.g., group_by + agg), returns
        a list of dicts with column names as keys. For simple pipelines,
        returns a list of output lines.

        Args:
            timeout: Maximum execution time in seconds.
            cwd: Working directory for execution.

        Returns:
            List of dicts for structured output, or list of lines for text output.

        Raises:
            subprocess.TimeoutExpired: If timeout is exceeded.
            RuntimeError: If command exits with non-zero status.
        """
        command = self.to_shell()
        result = execute(command, timeout=timeout, cwd=cwd)

        if result.return_code != 0:
            # grep returns 1 when no matches found - that's not an error
            if result.return_code == 1 and not result.stderr:
                return []
            raise RuntimeError(
                f"Command failed with exit code {result.return_code}: {result.stderr}"
            )

        # Check if we have structured output
        columns = self._get_output_columns()
        if columns:
            delimiter = self._get_output_delimiter()
            return self._parse_structured_output(result.stdout, columns, delimiter)

        # Return list of lines for text output
        lines = result.stdout.split("\n")
        # Remove trailing empty line if present (from trailing newline)
        if lines and lines[-1] == "":
            lines = lines[:-1]
        return lines

    def run_raw(
        self, timeout: Optional[float] = None, cwd: Optional[str] = None
    ) -> str:
        """
        Execute the pipeline and return raw stdout (always as string).

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
