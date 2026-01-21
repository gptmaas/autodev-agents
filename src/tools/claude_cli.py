"""Claude Code CLI wrapper for executing coding tasks."""

import os
import subprocess
import tempfile
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

    def run(
        self,
        prompt: str,
        work_dir: Optional[str] = None,
        timeout: Optional[int] = None,
        non_interactive: bool = True
    ) -> ClaudeCLIResult:
        """Execute Claude Code CLI with the given prompt.

        Args:
            prompt: Prompt to send to Claude Code
            work_dir: Working directory for execution
            timeout: Override default timeout
            non_interactive: Whether to run in non-interactive mode

        Returns:
            ClaudeCLIResult with execution details
        """
        # Use provided timeout or default
        actual_timeout = timeout or self.timeout

        # Prepare command
        cmd = self._build_command(prompt, work_dir, non_interactive)

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
        non_interactive: bool
    ) -> List[str]:
        """Build the command list for Claude CLI.

        Args:
            prompt: Prompt to execute
            work_dir: Working directory
            non_interactive: Non-interactive mode flag

        Returns:
            Command as list of strings
        """
        cmd = [self.claude_path]

        if non_interactive:
            cmd.extend(["--prompt", prompt])

        if work_dir:
            cmd.extend(["--cwd", work_dir])

        return cmd

    def _execute_command(
        self,
        cmd: List[str],
        timeout: int,
        work_dir: Optional[str]
    ) -> ClaudeCLIResult:
        """Execute the command and capture output.

        Args:
            cmd: Command to execute
            timeout: Timeout in seconds
            work_dir: Working directory

        Returns:
            ClaudeCLIResult with execution details
        """
        try:
            # Execute command
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
        work_dir: Optional[str] = None
    ) -> ClaudeCLIResult:
        """Execute Claude CLI with a prompt from a file.

        Args:
            prompt_file: Path to file containing prompt
            work_dir: Working directory for execution

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
        return self.run(prompt, work_dir)

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
    timeout: Optional[int] = None
) -> ClaudeCLIResult:
    """Convenience function to run Claude CLI.

    Args:
        prompt: Prompt to send to Claude Code
        work_dir: Working directory for execution
        timeout: Override default timeout

    Returns:
        ClaudeCLIResult with execution details
    """
    wrapper = get_claude_cli()
    return wrapper.run(prompt, work_dir, timeout)


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
