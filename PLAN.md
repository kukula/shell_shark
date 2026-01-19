# ShellSpark Implementation Plan

## Overview
ShellSpark is a Python framework that compiles declarative data transformations into Unix shell pipelines. It provides a Spark-like API that generates optimized shell commands using `awk`, `grep`, `sort`, `jq`, and related tools.

**Key Requirement: Must work on both macOS and Linux.**

---

## Cross-Platform Strategy

### Key Incompatibilities to Handle
| Issue | macOS (BSD) | Linux (GNU) | Solution |
|-------|-------------|-------------|----------|
| CPU count | `sysctl -n hw.ncpu` | `nproc` | Platform detection |
| Sort parallel | Not supported | `--parallel` flag | Capability detection |
| Grep PCRE | Not supported | `-P` flag | Use `rg` or basic regex |
| awk in-place | Not supported | `-i inplace` | Use temp file pattern |

### Tool Preference with Fallbacks
- **awk**: mawk > gawk > awk (detect availability)
- **grep**: rg > GNU grep > BSD grep
- Use `shutil.which()` + version parsing to detect capabilities
- Cache tool detection results (lazy singleton pattern)

---

## Implementation Phases

### Phase 1: Foundation (MVP)
Create end-to-end pipeline that filters text files.

**Files to create:**
1. `shellspark/__init__.py` - Package exports
2. `shellspark/tools.py` - Tool detection with cross-platform support
3. `shellspark/ast.py` - Core AST nodes (Source, Filter)
4. `shellspark/codegen/base.py` - Abstract generator interface
5. `shellspark/codegen/grep.py` - Grep code generation
6. `shellspark/pipeline.py` - Pipeline class with `filter()` and `to_shell()`
7. `shellspark/executor.py` - Basic subprocess execution

**Deliverable:**
```python
Pipeline("access.log").filter(line__contains="ERROR").to_shell()
# => grep -F "ERROR" access.log
```

### Phase 2: AWK and Field Operations
Support column-based operations with AWK.

**Files to create:**
1. `shellspark/codegen/awk.py` - AWK code generation
2. `shellspark/formats/__init__.py`, `csv.py`, `text.py` - Format handlers

**New AST nodes:** `Select`, `Parse`

### Phase 3: Aggregations
Support grouping and aggregation.

**New AST nodes:** `GroupBy`, `Aggregation`

**Enhance:** `codegen/awk.py` with associative array patterns

### Phase 4: Sorting and Limits
**Files:** `shellspark/codegen/sort.py`

**New AST nodes:** `Sort`, `Limit`, `Distinct`

**Cross-platform:** Detect GNU sort's `--parallel`, handle `nproc` vs `sysctl`

### Phase 5: Optimizer
**Files:** `shellspark/optimizer.py`

Rule-based passes: filter pushdown, AWK fusion, tool selection

### Phase 6: JSON Support
**Files:** `shellspark/codegen/jq.py`, `shellspark/formats/json.py`

### Phase 7: Parallelization
Add `find | xargs -P` pattern for multi-file processing

### Phase 8: Polish
CLI interface, streaming results, error handling, documentation

---

## Key Design Decisions

1. **AST Nodes**: Frozen dataclasses for immutability
2. **Tool Detection**: Lazy detection with `@lru_cache`, override via env vars
3. **Code Generators**: Strategy pattern with tool-specific adapters
4. **Optimizer**: Rule-based with ordered passes (simpler than cost-based)
5. **Escaping**: Always use `shlex.quote()` for shell safety

---

## Project Structure
```
shellspark/
├── __init__.py
├── pipeline.py        # Main Pipeline class, builder pattern
├── ast.py             # Operation nodes (frozen dataclasses)
├── optimizer.py       # Query plan optimization
├── tools.py           # Tool detection (cross-platform)
├── executor.py        # Run pipelines, stream results
├── codegen/
│   ├── __init__.py
│   ├── base.py        # Abstract code generator
│   ├── awk.py         # AWK code generation
│   ├── grep.py        # grep/ripgrep generation
│   ├── jq.py          # jq for JSON
│   └── sort.py        # sort, uniq, head, tail
└── formats/
    ├── __init__.py
    ├── csv.py
    ├── json.py
    └── text.py
```

---

## Verification Plan

1. **Unit tests** for each module (AST nodes, code generators, optimizer passes)
2. **Integration tests** with sample data files
3. **Cross-platform CI** via GitHub Actions:
   ```yaml
   strategy:
     matrix:
       os: [ubuntu-latest, macos-latest]
       python: ["3.10", "3.11", "3.12"]
   ```
4. **Manual testing**: Run generated shell commands on both platforms
5. **Test commands:**
   ```bash
   pip install -e .
   pytest tests/
   python -c "from shellspark import Pipeline; print(Pipeline('test.txt').filter(line__contains='ERROR').to_shell())"
   ```

---

## Blog Article & Demo

### Blog Post: "ShellSpark: Apache Spark API for Unix Pipelines"

**Target audience:** Data engineers, DevOps, CLI enthusiasts

**Outline:**
1. **Introduction** - The problem: processing large files without Spark infrastructure
2. **The Idea** - What if Spark's API generated shell commands instead of distributed jobs?
3. **Quick Demo** - Show simple examples
4. **Architecture** - How it works (AST → Optimizer → CodeGen)
5. **Cross-Platform Challenges** - macOS vs Linux differences
6. **Performance** - Benchmarks vs Python pandas, vs actual Spark for single-node
7. **Limitations** - When to use ShellSpark vs real Spark
8. **Conclusion** - Links, installation

### Demo Examples (Spark-inspired)

#### 1. Basic Filter and Select (like Spark DataFrame)
```python
from shellspark import Pipeline

# Spark equivalent:
# df = spark.read.csv("sales.csv", header=True)
# df.filter(df.region == "West").select("product", "amount").show()

# ShellSpark:
result = (
    Pipeline("sales.csv")
    .parse(format="csv", header=True)
    .filter(region="West")
    .select("product", "amount")
    .to_shell()
)
# => awk -F',' 'NR==1{for(i=1;i<=NF;i++)h[$i]=i} NR>1&&$h["region"]=="West"{print $h["product"]","$h["amount"]}' sales.csv
```

#### 2. Word Count (Classic Spark Example)
```python
# Spark equivalent:
# lines = spark.read.text("book.txt")
# words = lines.flatMap(lambda x: x.split()).groupBy().count()

# ShellSpark:
result = (
    Pipeline("book.txt")
    .flatmap(split=" ")  # Split lines into words
    .group_by("word")
    .agg(count="*")
    .sort("count", desc=True)
    .limit(10)
    .to_shell()
)
# => tr ' ' '\n' < book.txt | sort | uniq -c | sort -rn | head -10
```

#### 3. Log Analysis (Common Use Case)
```python
# Spark equivalent:
# logs = spark.read.text("access.log")
# errors = logs.filter(logs.value.contains("ERROR"))
#              .groupBy(extract_hour("timestamp")).count()

# ShellSpark:
result = (
    Pipeline("access.log")
    .filter(line__contains="ERROR")
    .parse(format="text", pattern=r'\[(\d{2}:\d{2}):\d{2}\]')
    .group_by("hour")
    .agg(count="*")
    .to_shell()
)
# => grep -F "ERROR" access.log | grep -oE '\[[0-9]{2}:[0-9]{2}' | sort | uniq -c
```

#### 4. Aggregations (Sum, Avg, Max)
```python
# Spark equivalent:
# df.groupBy("department").agg(
#     sum("salary").alias("total"),
#     avg("salary").alias("average"),
#     max("salary").alias("highest")
# )

# ShellSpark:
result = (
    Pipeline("employees.csv")
    .parse(format="csv", header=True)
    .group_by("department")
    .agg(
        total=sum("salary"),
        average=avg("salary"),
        highest=max("salary")
    )
    .to_shell()
)
# => awk -F',' 'NR==1{...} NR>1{sum[$dept]+=$sal; cnt[$dept]++; if($sal>max[$dept])max[$dept]=$sal} END{...}' employees.csv
```

#### 5. JSON Processing
```python
# Spark equivalent:
# df = spark.read.json("events.json")
# df.filter(df.type == "click").select("user_id", "timestamp")

# ShellSpark:
result = (
    Pipeline("events.json")
    .filter(type="click")
    .select("user_id", "timestamp")
    .to_shell()
)
# => jq -c 'select(.type == "click") | {user_id, timestamp}' events.json
```

#### 6. Multi-file Processing with Parallelization
```python
# Spark equivalent:
# df = spark.read.text("logs/*.log")

# ShellSpark:
result = (
    Pipeline("logs/*.log")
    .filter(line__contains="CRITICAL")
    .parallel(workers=4)
    .to_shell()
)
# => find logs -name '*.log' -print0 | xargs -0 -P4 grep -F "CRITICAL"
```

### Live Demo Script

```bash
#!/bin/bash
# demo.sh - ShellSpark live demo

echo "=== ShellSpark Demo ==="
echo ""

# Create sample data
cat > /tmp/sales.csv << 'EOF'
date,region,product,amount
2024-01-01,West,Widget,100
2024-01-01,East,Gadget,200
2024-01-02,West,Widget,150
2024-01-02,West,Gadget,300
2024-01-03,East,Widget,250
EOF

echo "1. Sample data (sales.csv):"
cat /tmp/sales.csv
echo ""

echo "2. Filter West region, select product and amount:"
echo "   Python: Pipeline('sales.csv').parse('csv').filter(region='West').select('product','amount')"
echo "   Shell:  $(python -c "from shellspark import Pipeline; print(Pipeline('/tmp/sales.csv').parse('csv').filter(region='West').select('product','amount').to_shell())")"
echo ""

echo "3. Execute and show results:"
# Run the generated command
python -c "from shellspark import Pipeline; Pipeline('/tmp/sales.csv').parse('csv').filter(region='West').select('product','amount').run()"
```

### Benchmark Ideas for Blog

| Operation | ShellSpark | pandas | PySpark (local) |
|-----------|------------|--------|-----------------|
| Filter 1GB CSV | ? sec | ? sec | ? sec |
| Word count 100MB | ? sec | ? sec | ? sec |
| Group by + sum | ? sec | ? sec | ? sec |

*Expected result: ShellSpark faster for streaming/simple ops, pandas faster for complex transforms, PySpark has overhead for small files*

---

## Marketing / README Tagline Ideas

- "Apache Spark API → Unix Pipelines"
- "DataFrame operations that compile to awk, grep, and sort"
- "Process gigabytes with megabytes of RAM"
- "The data engineer's secret weapon for log analysis"
