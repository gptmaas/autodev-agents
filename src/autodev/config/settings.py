"""Configuration management for the multi-agent system."""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class ModelConfig:
    """Configuration for AI models."""

    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 8192
    timeout: int = 300
    base_url: Optional[str] = None


@dataclass
class ClaudeCLIConfig:
    """Configuration for Claude Code CLI wrapper."""

    claude_cli_path: str = "claude"
    timeout: int = 300
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_stream_output: bool = True
    heartbeat_interval: int = 30
    validation_mode: str = "lenient"  # "strict" or "lenient"


@dataclass
class WorkspaceConfig:
    """Configuration for workspace management."""

    root: str = "workspace"
    code_dir: str = "code"
    artifacts_dir: str = "artifacts"
    data_root: str = "data"  # 与 workspace 平级的 data 目录，用于存储 checkpoints 等数据


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""

    max_coding_iterations: int = 50
    human_in_loop: bool = False  # 默认不启用人工审核，可通过命令行参数或环境变量启用
    enable_checkpointing: bool = True
    checkpoint_backend: str = "sqlite"  # or "memory"


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    level: str = "INFO"
    log_file: Optional[str] = None
    use_colors: bool = True


@dataclass
class Settings:
    """Global settings for the application."""

    # API Configuration
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # Model configurations
    default_model: ModelConfig = field(default_factory=ModelConfig)
    pm_model: ModelConfig = field(default_factory=ModelConfig)
    architect_model: ModelConfig = field(default_factory=ModelConfig)
    coder_model: ModelConfig = field(default_factory=ModelConfig)

    # Tool configurations
    claude_cli: ClaudeCLIConfig = field(default_factory=ClaudeCLIConfig)
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)

    # Agent configurations
    agent: AgentConfig = field(default_factory=AgentConfig)

    # Logging configuration
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def __post_init__(self):
        """Initialize settings from environment variables."""
        # Override with environment variables if present
        if api_key := os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic_api_key = api_key

        # Read base URL once and apply to all models
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        if base_url:
            self.default_model.base_url = base_url
            self.pm_model.base_url = base_url
            self.architect_model.base_url = base_url
            self.coder_model.base_url = base_url

        if default_model := os.getenv("DEFAULT_MODEL"):
            self.default_model.model = default_model

        if pm_model := os.getenv("PM_MODEL"):
            self.pm_model.model = pm_model

        if architect_model := os.getenv("ARCHITECT_MODEL"):
            self.architect_model.model = architect_model

        if coder_model := os.getenv("CODER_MODEL"):
            self.coder_model.model = coder_model

        if workspace_root := os.getenv("WORKSPACE_ROOT"):
            self.workspace.root = workspace_root

        if data_root := os.getenv("DATA_ROOT"):
            self.workspace.data_root = data_root

        if timeout := os.getenv("CLAUDE_CLI_TIMEOUT"):
            self.claude_cli.timeout = int(timeout)

        if max_retries := os.getenv("CLAUDE_CLI_MAX_RETRIES"):
            self.claude_cli.max_retries = int(max_retries)

        if stream_output := os.getenv("CLAUDE_CLI_STREAM_OUTPUT"):
            self.claude_cli.enable_stream_output = stream_output.lower() in ("true", "1", "yes")

        if heartbeat_interval := os.getenv("CLAUDE_CLI_HEARTBEAT_INTERVAL"):
            self.claude_cli.heartbeat_interval = int(heartbeat_interval)

        if validation_mode := os.getenv("CLAUDE_CLI_VALIDATION_MODE"):
            validation_mode = validation_mode.lower()
            if validation_mode in ("strict", "lenient"):
                self.claude_cli.validation_mode = validation_mode
            else:
                logger.warning(f"Invalid VALIDATION_MODE: {validation_mode}. Must be 'strict' or 'lenient'. Using default: 'lenient'")

        if max_iterations := os.getenv("MAX_CODING_ITERATIONS"):
            self.agent.max_coding_iterations = int(max_iterations)

        if human_in_loop := os.getenv("HUMAN_IN_LOOP"):
            self.agent.human_in_loop = human_in_loop.lower() in ("true", "1", "yes")

        if log_level := os.getenv("LOG_LEVEL"):
            self.logging.level = log_level

        if log_file := os.getenv("LOG_FILE"):
            self.logging.log_file = log_file

    def validate(self) -> None:
        """Validate that required settings are present.

        Raises:
            ValueError: If required settings are missing
        """
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required. Set it in .env or environment.")

    def get_session_workspace(self, session_id: str) -> Path:
        """Get the workspace path for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to session workspace
        """
        workspace_path = Path(self.workspace.root) / session_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        return workspace_path

    def get_code_directory(self, session_id: str) -> Path:
        """Get the code directory for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to code directory
        """
        workspace = self.get_session_workspace(session_id)
        code_dir = workspace / self.workspace.code_dir
        code_dir.mkdir(parents=True, exist_ok=True)
        return code_dir

    def get_artifacts_directory(self, session_id: str) -> Path:
        """Get the artifacts directory for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to artifacts directory
        """
        workspace = self.get_session_workspace(session_id)
        artifacts_dir = workspace / self.workspace.artifacts_dir
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return artifacts_dir

    def get_data_directory(self) -> Path:
        """Get the data directory path (与 workspace 平级).

        Returns:
            Path to data directory
        """
        data_dir = Path(self.workspace.data_root)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Returns:
        Global settings (creates one if doesn't exist)

    Raises:
        ValueError: If settings validation fails
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.validate()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance (useful for testing)."""
    global _settings
    _settings = None
