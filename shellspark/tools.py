"""Cross-platform tool detection and capability checking."""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass(frozen=True)
class ToolInfo:
    """Information about an available tool."""

    name: str
    path: str
    version: Optional[str] = None
    is_gnu: bool = False


@lru_cache(maxsize=1)
def get_platform() -> str:
    """Return 'darwin' for macOS, 'linux' for Linux."""
    return platform.system().lower()


@lru_cache(maxsize=1)
def get_cpu_count() -> int:
    """Get CPU count in a cross-platform way."""
    if get_platform() == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.ncpu"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            pass
    else:
        try:
            result = subprocess.run(
                ["nproc"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            pass

    return os.cpu_count() or 1


def _get_tool_version(path: str, version_flag: str = "--version") -> Optional[str]:
    """Get version string from a tool."""
    try:
        result = subprocess.run(
            [path, version_flag],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.split("\n")[0]
        return result.stderr.split("\n")[0] if result.stderr else None
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return None


def _is_gnu_tool(version_string: Optional[str]) -> bool:
    """Check if version string indicates GNU tool."""
    if not version_string:
        return False
    return "gnu" in version_string.lower() or "gawk" in version_string.lower()


@lru_cache(maxsize=1)
def detect_awk() -> ToolInfo:
    """
    Detect best available awk implementation.

    Preference order: mawk > gawk > awk
    Can be overridden with SHELLSPARK_AWK env var.
    """
    override = os.environ.get("SHELLSPARK_AWK")
    if override:
        path = shutil.which(override)
        if path:
            version = _get_tool_version(path)
            return ToolInfo(
                name=os.path.basename(override),
                path=path,
                version=version,
                is_gnu=_is_gnu_tool(version),
            )

    for awk_name in ["mawk", "gawk", "awk"]:
        path = shutil.which(awk_name)
        if path:
            version = _get_tool_version(path)
            return ToolInfo(
                name=awk_name,
                path=path,
                version=version,
                is_gnu=_is_gnu_tool(version) or awk_name == "gawk",
            )

    raise RuntimeError("No awk implementation found")


@lru_cache(maxsize=1)
def detect_grep() -> ToolInfo:
    """
    Detect best available grep implementation.

    Preference order: rg (ripgrep) > GNU grep > BSD grep
    Can be overridden with SHELLSPARK_GREP env var.
    """
    override = os.environ.get("SHELLSPARK_GREP")
    if override:
        path = shutil.which(override)
        if path:
            version = _get_tool_version(path)
            return ToolInfo(
                name=os.path.basename(override),
                path=path,
                version=version,
                is_gnu=_is_gnu_tool(version),
            )

    # Try ripgrep first
    rg_path = shutil.which("rg")
    if rg_path:
        version = _get_tool_version(rg_path)
        return ToolInfo(name="rg", path=rg_path, version=version, is_gnu=False)

    # Fall back to grep
    grep_path = shutil.which("grep")
    if grep_path:
        version = _get_tool_version(grep_path)
        return ToolInfo(
            name="grep",
            path=grep_path,
            version=version,
            is_gnu=_is_gnu_tool(version),
        )

    raise RuntimeError("No grep implementation found")


@lru_cache(maxsize=1)
def detect_sort() -> ToolInfo:
    """Detect sort command and its capabilities."""
    override = os.environ.get("SHELLSPARK_SORT")
    if override:
        path = shutil.which(override)
        if path:
            version = _get_tool_version(path)
            return ToolInfo(
                name=os.path.basename(override),
                path=path,
                version=version,
                is_gnu=_is_gnu_tool(version),
            )

    path = shutil.which("sort")
    if path:
        version = _get_tool_version(path)
        return ToolInfo(
            name="sort",
            path=path,
            version=version,
            is_gnu=_is_gnu_tool(version),
        )

    raise RuntimeError("sort command not found")


@lru_cache(maxsize=1)
def sort_supports_parallel() -> bool:
    """Check if sort supports --parallel flag (GNU sort feature)."""
    sort_info = detect_sort()
    if not sort_info.is_gnu:
        return False

    try:
        result = subprocess.run(
            [sort_info.path, "--parallel=1", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@lru_cache(maxsize=1)
def detect_jq() -> Optional[ToolInfo]:
    """Detect jq for JSON processing."""
    override = os.environ.get("SHELLSPARK_JQ")
    if override:
        path = shutil.which(override)
        if path:
            version = _get_tool_version(path)
            return ToolInfo(name="jq", path=path, version=version, is_gnu=False)

    path = shutil.which("jq")
    if path:
        version = _get_tool_version(path)
        return ToolInfo(name="jq", path=path, version=version, is_gnu=False)

    return None


def get_parallel_workers(requested: Optional[int] = None) -> int:
    """Get number of parallel workers to use.

    Args:
        requested: Specific number of workers requested by user.
                   None means auto-detect based on CPU count.

    Returns:
        Number of workers to use (minimum 1).
    """
    if requested is not None:
        return max(1, requested)
    return get_cpu_count()


@lru_cache(maxsize=1)
def grep_supports_pcre() -> bool:
    """Check if grep supports PCRE (-P flag)."""
    grep_info = detect_grep()

    # ripgrep uses -P for PCRE
    if grep_info.name == "rg":
        return True

    # Only GNU grep supports -P
    if not grep_info.is_gnu:
        return False

    try:
        result = subprocess.run(
            [grep_info.path, "-P", "test", "/dev/null"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode in (0, 1)  # 0=match, 1=no match, both OK
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def clear_tool_cache() -> None:
    """Clear all cached tool detection results.

    Use this after installing new tools or changing environment variables
    (SHELLSPARK_AWK, SHELLSPARK_GREP, etc.) to re-detect available tools.

    Example:
        >>> from shellspark.tools import clear_tool_cache
        >>> clear_tool_cache()
    """
    get_platform.cache_clear()
    get_cpu_count.cache_clear()
    detect_awk.cache_clear()
    detect_grep.cache_clear()
    detect_sort.cache_clear()
    detect_jq.cache_clear()
    sort_supports_parallel.cache_clear()
    grep_supports_pcre.cache_clear()
