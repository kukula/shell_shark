# Contributing to ShellSpark

Thank you for your interest in contributing to ShellSpark! This document provides guidelines for development and testing.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/shellspark.git
   cd shellspark
   ```

2. Install in development mode:
   ```bash
   pip install -e .
   ```

3. Install development dependencies:
   ```bash
   pip install pytest
   ```

## Running Tests

```bash
# Run the full test suite
pytest tests/

# Run with verbose output
pytest tests/ -v

# Test a specific module
pytest tests/test_pipeline.py
```

### Quick Verification

Test basic functionality:

```bash
python -c "
from shellspark import Pipeline
print(Pipeline('test.txt').filter(line__contains='ERROR').to_shell())
"
# Expected: grep -F 'ERROR' test.txt
```

## Key Design Decisions

Understanding these decisions will help you contribute effectively:

1. **AST Nodes**: Frozen dataclasses for immutability - operations build up an immutable query plan
2. **Tool Detection**: Lazy detection with `@lru_cache`, override via environment variables
3. **Code Generators**: Strategy pattern with tool-specific adapters in `codegen/`
4. **Optimizer**: Rule-based with ordered passes (simpler than cost-based optimization)
5. **Escaping**: Always use `shlex.quote()` for shell safety - never concatenate raw strings

## Project Structure

```
shellspark/
├── __init__.py
├── pipeline.py        # Main Pipeline class, builder pattern
├── ast.py             # Operation nodes (frozen dataclasses)
├── optimizer.py       # Query plan optimization
├── tools.py           # Tool detection (cross-platform)
├── executor.py        # Run pipelines, stream results
├── aggregations.py    # Aggregation helper functions
├── codegen/
│   ├── __init__.py
│   ├── base.py        # Abstract code generator
│   ├── awk.py         # AWK code generation
│   ├── grep.py        # grep/ripgrep generation
│   ├── jq.py          # jq for JSON
│   └── sort.py        # sort, uniq, head, tail
└── formats/
    ├── __init__.py
    ├── base.py
    ├── csv.py
    └── text.py
```

## Adding a New Operation

1. Add the AST node to `ast.py` as a frozen dataclass
2. Add the Pipeline method to `pipeline.py`
3. Implement code generation in the appropriate `codegen/` module
4. Add optimizer rules if applicable
5. Write tests in `tests/`

## Code Style Guidelines

- Follow PEP 8
- Use type hints for function signatures
- Add docstrings for public methods
- Keep functions focused and small

## Cross-Platform Testing

ShellSpark must work on both macOS and Linux. If you're adding shell command generation:

- Test on both platforms if possible
- Handle tool differences (see `docs/cross-platform.md`)
- Use `tools.py` for platform detection, never hardcode commands

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass on both platforms
5. Submit a PR with a clear description of changes

## Questions?

Open an issue for discussion before starting major changes.
