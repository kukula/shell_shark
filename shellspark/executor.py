"""Subprocess execution for shell pipelines."""

import subprocess
from dataclasses import dataclass
from typing import Iterator, Optional


@dataclass
class ExecutionResult:
    """Result of executing a shell command."""

    stdout: str
    stderr: str
    return_code: int
    command: str


def execute(
    command: str,
    timeout: Optional[float] = None,
    shell: bool = True,
    cwd: Optional[str] = None,
) -> ExecutionResult:
    """
    Execute a shell command and return the result.

    Args:
        command: The shell command to execute.
        timeout: Maximum time to wait in seconds (None for no timeout).
        shell: Whether to run through shell (default True for pipelines).
        cwd: Working directory for command execution.

    Returns:
        ExecutionResult with stdout, stderr, return_code, and command.

    Raises:
        subprocess.TimeoutExpired: If timeout is exceeded.
    """
    result = subprocess.run(
        command,
        shell=shell,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )
    return ExecutionResult(
        stdout=result.stdout,
        stderr=result.stderr,
        return_code=result.returncode,
        command=command,
    )


def stream_execute(
    command: str,
    shell: bool = True,
    cwd: Optional[str] = None,
) -> Iterator[str]:
    """
    Execute a shell command and stream output line by line.

    Args:
        command: The shell command to execute.
        shell: Whether to run through shell (default True for pipelines).
        cwd: Working directory for command execution.

    Yields:
        Lines of stdout as they become available.

    Raises:
        subprocess.CalledProcessError: If command exits with non-zero status.
    """
    process = subprocess.Popen(
        command,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
    )

    assert process.stdout is not None
    assert process.stderr is not None

    try:
        for line in process.stdout:
            yield line.rstrip("\n")
    finally:
        process.wait()
        if process.returncode != 0:
            stderr = process.stderr.read()
            raise subprocess.CalledProcessError(
                process.returncode, command, stderr=stderr
            )
