# Cross-Platform Compatibility

ShellSpark is designed to work seamlessly on both macOS (BSD tools) and Linux (GNU tools). This document explains the platform differences and how ShellSpark handles them.

## Key Incompatibilities

| Issue | macOS (BSD) | Linux (GNU) | ShellSpark Solution |
|-------|-------------|-------------|---------------------|
| CPU count | `sysctl -n hw.ncpu` | `nproc` | Platform detection at runtime |
| Sort parallel | Not supported | `--parallel` flag | Capability detection |
| Grep PCRE | Not supported | `-P` flag | Use `rg` or basic regex |
| awk in-place | Not supported | `-i inplace` | Use temp file pattern |

## Tool Preference with Fallbacks

ShellSpark automatically selects the best available tool:

- **awk**: mawk > gawk > awk (detect availability)
- **grep**: rg > GNU grep > BSD grep

Tool detection uses `shutil.which()` combined with version parsing to determine capabilities. Results are cached using a lazy singleton pattern to avoid repeated detection overhead.

## How Detection Works

The `tools.py` module handles all platform-specific logic:

```python
from shellspark.tools import ToolDetector

detector = ToolDetector()

# Get the best available awk
awk = detector.get_awk()  # Returns 'mawk', 'gawk', or 'awk'

# Check if GNU sort parallel is available
if detector.has_sort_parallel():
    # Use --parallel flag
    pass

# Get CPU count (works on both platforms)
cpus = detector.get_cpu_count()
```

## Environment Variable Overrides

You can force specific tools via environment variables:

```bash
# Force gawk instead of mawk
export SHELLSPARK_AWK=gawk

# Force GNU grep
export SHELLSPARK_GREP=ggrep
```

## Platform-Specific Notes

### macOS

- Install GNU tools via Homebrew for better compatibility:
  ```bash
  brew install gawk coreutils ripgrep jq
  ```
- GNU sort (gsort) supports `--parallel` flag
- ripgrep (`rg`) provides consistent regex behavior

### Linux

- Most distributions include GNU tools by default
- mawk may need to be installed separately:
  ```bash
  # Debian/Ubuntu
  apt install mawk

  # RHEL/Fedora
  dnf install mawk
  ```

## Testing Cross-Platform

Run tests on both platforms to ensure compatibility:

```bash
# Run the full test suite
pytest tests/

# Test a specific pipeline on both platforms
python -c "
from shellspark import Pipeline
cmd = Pipeline('test.csv').parse('csv').filter(status='active').to_shell()
print(cmd)
"
```

The GitHub Actions CI matrix tests against both `ubuntu-latest` and `macos-latest`.
