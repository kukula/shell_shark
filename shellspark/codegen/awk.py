"""AWK code generator for field operations."""

import shlex
from typing import Optional

from shellspark.ast import (
    AggFunc,
    Aggregation,
    Filter,
    FilterOp,
    GroupBy,
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
        - GroupBy node (aggregations)
        - Filter with column != None (column-level filter)
        """
        for n in walk_tree(node):
            if isinstance(n, Parse):
                return True
            if isinstance(n, Select):
                return True
            if isinstance(n, GroupBy):
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
        group_by_node: Optional[GroupBy] = None
        source: Optional[Source] = None

        for n in walk_tree(node):
            if isinstance(n, Parse):
                parse_node = n
            elif isinstance(n, Filter) and n.column is not None:
                filters.append(n)
            elif isinstance(n, Select):
                select_node = n
            elif isinstance(n, GroupBy):
                group_by_node = n
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

        # Get field separator
        fs = handler.awk_field_separator()
        fs_flag = f"-F{shlex.quote(fs)}" if fs else ""

        # Dispatch to groupby generator if present
        if group_by_node is not None:
            return self._generate_groupby(
                group_by_node, filters, handler, fs, fs_flag, awk_info, source, input_cmd
            )

        # Build AWK script parts for non-groupby case
        parts = []

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

    def _generate_groupby(
        self,
        group_by_node: GroupBy,
        filters: list[Filter],
        handler,
        fs: Optional[str],
        fs_flag: str,
        awk_info,
        source: Optional[Source],
        input_cmd: Optional[str],
    ) -> str:
        """Generate AWK code for GroupBy with aggregations."""
        parts = []

        # Add header handling code
        header_code = handler.awk_header_code()
        if header_code:
            parts.append(header_code)

        # Build group key expression
        key_refs = [handler.field_ref(k) for k in group_by_node.keys]
        if len(key_refs) == 1:
            key_expr = key_refs[0]
        else:
            # Use SUBSEP for composite keys
            key_expr = "(" + " SUBSEP ".join(key_refs) + ")"

        # Build filter conditions
        conditions = []
        for f in filters:
            cond = self._filter_to_condition(f, handler)
            conditions.append(cond)

        # Build accumulation statements for each aggregation
        accum_stmts = []
        for agg in group_by_node.aggregations:
            array_name = self._get_array_name(agg)
            field_ref = handler.field_ref(agg.column) if agg.column else None

            if agg.func == AggFunc.COUNT:
                accum_stmts.append(f"{array_name}[key]++")
            elif agg.func == AggFunc.SUM:
                accum_stmts.append(f"{array_name}[key]+={field_ref}")
            elif agg.func == AggFunc.AVG:
                # AVG needs both sum and count
                sum_arr = f"_sum_{self._sanitize_name(agg.alias or agg.column)}"
                cnt_arr = f"_cnt_{self._sanitize_name(agg.alias or agg.column)}"
                accum_stmts.append(f"{sum_arr}[key]+={field_ref}")
                accum_stmts.append(f"{cnt_arr}[key]++")
            elif agg.func == AggFunc.MIN:
                # MIN with initialization check
                seen_arr = f"_seen_{self._sanitize_name(agg.alias or agg.column)}"
                accum_stmts.append(
                    f"if(!{seen_arr}[key]||{field_ref}<{array_name}[key])"
                    f"{{{array_name}[key]={field_ref};{seen_arr}[key]=1}}"
                )
            elif agg.func == AggFunc.MAX:
                # MAX with initialization check
                seen_arr = f"_seen_{self._sanitize_name(agg.alias or agg.column)}"
                accum_stmts.append(
                    f"if(!{seen_arr}[key]||{field_ref}>{array_name}[key])"
                    f"{{{array_name}[key]={field_ref};{seen_arr}[key]=1}}"
                )
            elif agg.func == AggFunc.FIRST:
                # FIRST - only set if not seen
                seen_arr = f"_seen_{self._sanitize_name(agg.alias or agg.column)}"
                accum_stmts.append(
                    f"if(!{seen_arr}[key]){{{array_name}[key]={field_ref};{seen_arr}[key]=1}}"
                )
            elif agg.func == AggFunc.LAST:
                # LAST - always overwrite
                accum_stmts.append(f"{array_name}[key]={field_ref}")
            elif agg.func == AggFunc.COUNTDISTINCT:
                # COUNTDISTINCT - track unique (key, value) pairs
                # Using composite key with SUBSEP to track (group_key, column_value)
                seen_arr = f"_cd_{self._sanitize_name(agg.alias or agg.column)}"
                accum_stmts.append(f"{seen_arr}[key,{field_ref}]=1")

        # Always track group keys for iteration (needed for COUNTDISTINCT and safer in general)
        accum_stmts.append("_keys[key]=1")

        # Build main block with key assignment and accumulations
        main_block_stmts = [f"key={key_expr}"] + accum_stmts
        main_block = "{" + "; ".join(main_block_stmts) + "}"

        # Add condition if filters exist
        if conditions:
            combined_condition = " && ".join(conditions)
            parts.append(f"{combined_condition}{main_block}")
        else:
            parts.append(main_block)

        # Build END block - use _keys array for iteration
        iter_array = "_keys"

        # Build output expression for each aggregation
        output_exprs = []

        # Handle composite key splitting in END block
        if len(group_by_node.keys) > 1:
            # Need to split composite key
            split_stmt = f"split(k,_parts,SUBSEP)"
            key_outputs = [f"_parts[{i+1}]" for i in range(len(group_by_node.keys))]
        else:
            split_stmt = None
            key_outputs = ["k"]

        output_exprs.extend(key_outputs)

        # Build code to compute COUNTDISTINCT values before printing
        countdistinct_setup = []
        for agg in group_by_node.aggregations:
            array_name = self._get_array_name(agg)
            if agg.func == AggFunc.AVG:
                sum_arr = f"_sum_{self._sanitize_name(agg.alias or agg.column)}"
                cnt_arr = f"_cnt_{self._sanitize_name(agg.alias or agg.column)}"
                output_exprs.append(f"{sum_arr}[k]/{cnt_arr}[k]")
            elif agg.func == AggFunc.COUNTDISTINCT:
                # Need to count unique values for this group key
                seen_arr = f"_cd_{self._sanitize_name(agg.alias or agg.column)}"
                count_var = f"_cdc_{self._sanitize_name(agg.alias or agg.column)}"
                # Count entries in seen_arr that match this group key
                # The seen_arr has keys like (group_key SUBSEP value)
                countdistinct_setup.append(f"{count_var}=0")
                countdistinct_setup.append(
                    f"for(_cdkey in {seen_arr}){{split(_cdkey,_cdparts,SUBSEP);"
                    f"if(_cdparts[1]==k){count_var}++}}"
                )
                output_exprs.append(count_var)
            else:
                output_exprs.append(f"{array_name}[k]")

        # Build print statement
        output_sep = fs if fs else ","
        output_sep_escaped = _escape_awk_string(output_sep)
        sep_str = f'"{output_sep_escaped}"'

        if len(output_exprs) == 1:
            print_stmt = f"print {output_exprs[0]}"
        else:
            joined = sep_str.join(output_exprs)
            print_stmt = f"print {joined}"

        # Assemble END block
        end_stmts = []
        if split_stmt:
            end_stmts.append(split_stmt)
        end_stmts.extend(countdistinct_setup)
        end_stmts.append(print_stmt)

        end_body = f"for(k in {iter_array}){{{'; '.join(end_stmts)}}}"
        parts.append(f"END{{{end_body}}}")

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

    def _get_array_name(self, agg: Aggregation) -> str:
        """Generate unique array name for an aggregation."""
        name = self._sanitize_name(agg.alias or agg.column or "all")
        func_prefix = agg.func.name.lower()
        return f"_{func_prefix}_{name}"

    def _sanitize_name(self, name: str) -> str:
        """Make a name safe for use as AWK variable."""
        # Replace non-alphanumeric chars with underscore
        result = []
        for c in name:
            if c.isalnum() or c == "_":
                result.append(c)
            else:
                result.append("_")
        return "".join(result)


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
