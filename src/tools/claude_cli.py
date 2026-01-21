"""Claude Code CLI wrapper for executing coding tasks."""

import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from ..config.settings import get_settings
from ..utils.logger import get_logger
from .validation import validate_coding_output


logger = get_logger()


@dataclass
class ClaudeCLIResult:
    """Result from Claude Code CLI execution."""

    success: bool
    """Whether execution was successful."""

    output: str
    """Output from the CLI."""

    error: Optional[str] = None
    """Error message if execution failed."""

    files_created: List[str] = None
    """List of files that were created."""

    files_modified: List[str] = None
    """List of files that were modified."""

    exit_code: int = 0
    """Process exit code."""

    def __post_init__(self):
        if self.files_created is None:
            self.files_created = []
        if self.files_modified is None:
            self.files_modified = []


class ClaudeCLIWrapper:
    """Wrapper for Claude Code CLI execution."""

    def __init__(
        self,
        claude_path: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        """Initialize the Claude CLI wrapper.

        Args:
            claude_path: Path to claude executable (default: from settings)
            timeout: Timeout in seconds (default: from settings)
            max_retries: Maximum number of retries (default: from settings)
        """
        settings = get_settings()

        self.claude_path = claude_path or settings.claude_cli.claude_cli_path
        self.timeout = timeout or settings.claude_cli.timeout
        self.max_retries = max_retries or settings.claude_cli.max_retries
        self.retry_delay = settings.claude_cli.retry_delay
        self.enable_stream_output = settings.claude_cli.enable_stream_output
        self.heartbeat_interval = settings.claude_cli.heartbeat_interval

    def run(
        self,
        prompt: str,
        work_dir: Optional[str] = None,
        timeout: Optional[int] = None,
        non_interactive: bool = True,
        add_dir: Optional[str | List[str]] = None
    ) -> ClaudeCLIResult:
        """Execute Claude Code CLI with the given prompt.

        Args:
            prompt: Prompt to send to Claude Code
            work_dir: Working directory for execution
            timeout: Override default timeout
            non_interactive: Whether to run in non-interactive mode
            add_dir: Directory path(s) to add with --add-dir flag (string or list of strings)

        Returns:
            ClaudeCLIResult with execution details
        """
        # Use provided timeout or default
        actual_timeout = timeout or self.timeout

        # Prepare command
        cmd = self._build_command(prompt, work_dir, non_interactive, add_dir)

        # Execute with retries
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Executing Claude CLI (attempt {attempt + 1}/{self.max_retries + 1})")
                result = self._execute_command(cmd, actual_timeout, work_dir)

                if result.success:
                    logger.info("Claude CLI execution succeeded")
                    return result
                elif attempt < self.max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
                    return result

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout after {actual_timeout}s (attempt {attempt + 1})")
                if attempt >= self.max_retries:
                    return ClaudeCLIResult(
                        success=False,
                        output="",
                        error=f"Timeout after {actual_timeout} seconds"
                    )
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                if attempt >= self.max_retries:
                    return ClaudeCLIResult(
                        success=False,
                        output="",
                        error=str(e)
                    )

        # Should not reach here, but just in case
        return ClaudeCLIResult(
            success=False,
            output="",
            error="Max retries exceeded"
        )

    def _build_command(
        self,
        prompt: str,
        work_dir: Optional[str],
        non_interactive: bool,
        add_dir: Optional[str | List[str]] = None
    ) -> List[str]:
        """Build the command list for Claude CLI.

        Args:
            prompt: Prompt to execute
            work_dir: Working directory (passed to subprocess.run, not CLI)
            non_interactive: Non-interactive mode flag
            add_dir: Directory path(s) to add with --add-dir flag (string or list of strings)

        Returns:
            Command as list of strings
        """
        cmd = [self.claude_path]

        # Add --add-dir if specified (supports multiple directories)
        if add_dir:
            # Normalize to list
            dirs_to_add = [add_dir] if isinstance(add_dir, str) else add_dir
            for dir_path in dirs_to_add:
                cmd.extend(["--add-dir", dir_path])
            logger.info(f"Using --add-dir: {dirs_to_add}")

        if non_interactive:
            # 自动接受文件编辑，避免等待确认
            cmd.extend(["--permission-mode", "acceptEdits"])
            cmd.extend(["-p", prompt])

        # Note: work_dir is handled by subprocess.run(cwd=work_dir), not as a CLI arg
        return cmd

    def _execute_command(
        self,
        cmd: List[str],
        timeout: int,
        work_dir: Optional[str]
    ) -> ClaudeCLIResult:
        """Execute the command with streaming output and heartbeat.

        Args:
            cmd: Command to execute
            timeout: Timeout in seconds
            work_dir: Working directory

        Returns:
            ClaudeCLIResult with execution details
        """
        try:
            # Use streaming mode if enabled
            if self.enable_stream_output:
                return self._execute_with_streaming(cmd, timeout, work_dir)
            else:
                return self._execute_silent(cmd, timeout, work_dir)

        except subprocess.TimeoutExpired as e:
            # Re-raise to be caught by retry logic
            raise
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return ClaudeCLIResult(
                success=False,
                output="",
                error=str(e)
            )

    def _execute_silent(
        self,
        cmd: List[str],
        timeout: int,
        work_dir: Optional[str]
    ) -> ClaudeCLIResult:
        """Execute command without streaming (legacy mode).

        Args:
            cmd: Command to execute
            timeout: Timeout in seconds
            work_dir: Working directory

        Returns:
            ClaudeCLIResult with execution details
        """
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir
        )

        output = result.stdout
        error_output = result.stderr
        exit_code = result.returncode

        # Log output (truncated for readability)
        log_output = output[:500] + "..." if len(output) > 500 else output
        logger.debug(f"Claude CLI output: {log_output}")

        return self._process_result(output, error_output, exit_code)

    def _execute_with_streaming(
        self,
        cmd: List[str],
        timeout: int,
        work_dir: Optional[str]
    ) -> ClaudeCLIResult:
        """Execute command with real-time streaming and heartbeat.

        Args:
            cmd: Command to execute
            timeout: Timeout in seconds
            work_dir: Working directory

        Returns:
            ClaudeCLIResult with execution details
        """
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=work_dir
        )

        output_lines = []
        error_lines = []
        start_time = time.time()
        stop_heartbeat = threading.Event()

        # Heartbeat thread
        def heartbeat():
            while not stop_heartbeat.is_set():
                if process.poll() is not None:
                    break
                elapsed = int(time.time() - start_time)
                logger.info(f"Claude CLI 执行中... (已运行 {elapsed} 秒)")
                stop_heartbeat.wait(self.heartbeat_interval)

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        try:
            # Stream output
            while True:
                # Check if process is still running
                if process.poll() is not None:
                    # Read any remaining output
                    remaining_stdout, remaining_stderr = process.communicate()
                    if remaining_stdout:
                        output_lines.append(remaining_stdout)
                    if remaining_stderr:
                        error_lines.append(remaining_stderr)
                    break

                # Read available output with timeout
                try:
                    # Use readline with a small timeout to avoid blocking
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line)
                        # Stream to logger in real-time
                        logger.info(f"Claude CLI: {line.rstrip()}")
                    else:
                        # No output available, small sleep
                        time.sleep(0.1)
                except:
                    break

        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=1)

        elapsed_time = int(time.time() - start_time)
        logger.info(f"Claude CLI 执行完成 (用时 {elapsed_time} 秒)")

        output = "".join(output_lines)
        error_output = "".join(error_lines)
        exit_code = process.returncode

        return self._process_result(output, error_output, exit_code)

    def _process_result(
        self,
        output: str,
        error_output: str,
        exit_code: int
    ) -> ClaudeCLIResult:
        """Process command execution result.

        Args:
            output: Standard output
            error_output: Error output
            exit_code: Process exit code

        Returns:
            ClaudeCLIResult with execution details
        """
        # Check for success
        is_success = exit_code == 0
        is_success_output, _ = validate_coding_output(output)

        if not is_success:
            error_msg = error_output or f"Exit code: {exit_code}"
            logger.error(f"Claude CLI failed: {error_msg}")
            return ClaudeCLIResult(
                success=False,
                output=output,
                error=error_msg,
                exit_code=exit_code
            )

        if not is_success_output:
            logger.warning("Claude CLI output validation failed")
            return ClaudeCLIResult(
                success=False,
                output=output,
                error="Output validation failed",
                exit_code=exit_code
            )

        # Parse files created/modified from output
        files_created = self._extract_files_from_output(output, "created")
        files_modified = self._extract_files_from_output(output, "modified")

        return ClaudeCLIResult(
            success=True,
            output=output,
            files_created=files_created,
            files_modified=files_modified,
            exit_code=exit_code
        )

    def _extract_files_from_output(self, output: str, action: str) -> List[str]:
        """Extract file information from CLI output.

        Args:
            output: CLI output text
            action: Either "created" or "modified"

        Returns:
            List of file paths
        """
        import re

        files = []
        patterns = [
            rf"({action}\s+(?:file|files?):\s*[^\n]+)",
            rf"({action}\s+[^\s]+\.(?:py|js|ts|json|md|txt|yaml|yml|toml|ini))",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for match in matches:
                # Extract file paths from the match
                file_paths = re.findall(r"[\w/\-\\]+\.\w+", match)
                files.extend(file_paths)

        return files

    def execute_prompt_file(
        self,
        prompt_file: Path,
        work_dir: Optional[str] = None,
        add_dir: Optional[str | List[str]] = None
    ) -> ClaudeCLIResult:
        """Execute Claude CLI with a prompt from a file.

        Args:
            prompt_file: Path to file containing prompt
            work_dir: Working directory for execution
            add_dir: Directory path(s) to add with --add-dir flag (string or list of strings)

        Returns:
            ClaudeCLIResult with execution details
        """
        if not prompt_file.exists():
            return ClaudeCLIResult(
                success=False,
                output="",
                error=f"Prompt file not found: {prompt_file}"
            )

        prompt = prompt_file.read_text()
        return self.run(prompt, work_dir, add_dir=add_dir)

    def check_available(self) -> bool:
        """Check if Claude CLI is available.

        Returns:
            True if claude command is available
        """
        try:
            result = subprocess.run(
                [self.claude_path, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False


# Global wrapper instance
_wrapper: Optional[ClaudeCLIWrapper] = None


def get_claude_cli() -> ClaudeCLIWrapper:
    """Get the global Claude CLI wrapper instance.

    Returns:
        ClaudeCLIWrapper instance
    """
    global _wrapper
    if _wrapper is None:
        _wrapper = ClaudeCLIWrapper()
    return _wrapper


def run_claude_cli(
    prompt: str,
    work_dir: Optional[str] = None,
    timeout: Optional[int] = None,
    add_dir: Optional[str | List[str]] = None
) -> ClaudeCLIResult:
    """Convenience function to run Claude CLI.

    Args:
        prompt: Prompt to send to Claude Code
        work_dir: Working directory for execution
        timeout: Override default timeout
        add_dir: Directory path(s) to add with --add-dir flag (string or list of strings)

    Returns:
        ClaudeCLIResult with execution details
    """
    wrapper = get_claude_cli()
    return wrapper.run(prompt, work_dir, timeout, add_dir=add_dir)


def create_non_interactive_prompt(
    task_description: str,
    context: str = "",
    constraints: List[str] = None
) -> str:
    """Create a non-interactive prompt for Claude CLI.

    Args:
        task_description: Description of the task
        context: Additional context
        constraints: List of constraints/constraints

    Returns:
        Formatted prompt string
    """
    prompt_parts = []

    if context:
        prompt_parts.append(f"Context:\n{context}\n")

    prompt_parts.append(f"Task:\n{task_description}\n")

    if constraints:
        prompt_parts.append("Constraints:")
        for constraint in constraints:
            prompt_parts.append(f"- {constraint}")

    # Add non-interactive instruction
    prompt_parts.append("\nExecute directly without asking for confirmation.")

    return "\n".join(prompt_parts)
