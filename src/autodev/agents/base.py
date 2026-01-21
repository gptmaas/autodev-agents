"""Base agent class for all agents in the multi-agent system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from ..core.state import AgentState
from ..config.settings import get_settings, ModelConfig
from ..utils.logger import get_logger
from ..utils.helpers import truncate_text


logger = get_logger()


class BaseAgent(ABC):
    """Base class for all agents.

    Provides common functionality for LLM interaction, prompt management,
    and state updates.
    """

    def __init__(
        self,
        name: str,
        model_config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None
    ):
        """Initialize the base agent.

        Args:
            name: Agent name (for logging)
            model_config: Model configuration (uses default if None)
            system_prompt: System prompt for the agent
        """
        self.name = name
        self.model_config = model_config or get_settings().default_model
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Initialize LLM
        self.llm = self._create_llm()

        logger.debug(f"Initialized agent: {self.name}")

    def _create_llm(self) -> ChatAnthropic:
        """Create the LLM instance for this agent.

        Returns:
            ChatAnthropic instance
        """
        settings = get_settings()

        # Build kwargs for ChatAnthropic
        kwargs = {
            "model": self.model_config.model,
            "temperature": self.model_config.temperature,
            "max_tokens": self.model_config.max_tokens,
            "timeout": self.model_config.timeout,
            "api_key": settings.anthropic_api_key,
        }

        # Add base_url if configured
        if self.model_config.base_url:
            kwargs["base_url"] = self.model_config.base_url

        return ChatAnthropic(**kwargs)

    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for this agent.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the agent's primary function.

        Args:
            state: Current agent state

        Returns:
            Dictionary of state updates to apply
        """
        pass

    def invoke_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Invoke the LLM with a prompt.

        Args:
            prompt: User prompt to send
            system_prompt: Optional override for system prompt

        Returns:
            LLM response text
        """
        messages = []

        # Add system prompt
        sys_prompt = system_prompt or self.system_prompt
        if sys_prompt:
            messages.append(SystemMessage(content=sys_prompt))

        # Add user prompt
        messages.append(HumanMessage(content=prompt))

        # Log the prompt (truncated)
        log_prompt = truncate_text(prompt, 200)
        logger.debug(f"[{self.name}] Invoking LLM with prompt: {log_prompt}")

        try:
            response = self.llm.invoke(messages)
            result = response.content if hasattr(response, 'content') else str(response)

            # Log the response (truncated)
            log_result = truncate_text(result, 200)
            logger.debug(f"[{self.name}] LLM response: {log_result}")

            return result

        except Exception as e:
            logger.error(f"[{self.name}] LLM invocation failed: {e}")
            raise

    def invoke_llm_with_history(
        self,
        messages: list,
        system_prompt: Optional[str] = None
    ) -> str:
        """Invoke the LLM with a conversation history.

        Args:
            messages: List of message objects (HumanMessage, AIMessage, etc.)
            system_prompt: Optional override for system prompt

        Returns:
            LLM response text
        """
        # Prepend system prompt if provided
        if system_prompt or self.system_prompt:
            sys_prompt = system_prompt or self.system_prompt
            messages = [SystemMessage(content=sys_prompt)] + messages

        # Log invocation
        logger.debug(f"[{self.name}] Invoking LLM with {len(messages)} messages")

        try:
            response = self.llm.invoke(messages)
            result = response.content if hasattr(response, 'content') else str(response)

            # Log the response (truncated)
            log_result = truncate_text(result, 200)
            logger.debug(f"[{self.name}] LLM response: {log_result}")

            return result

        except Exception as e:
            logger.error(f"[{self.name}] LLM invocation failed: {e}")
            raise

    def add_message(self, state: AgentState, message: str) -> None:
        """Add a message to the state's message history.

        Args:
            state: Agent state
            message: Message to add
        """
        if "messages" not in state:
            state["messages"] = []
        state["messages"].append(f"[{self.name}] {message}")
        logger.debug(f"[{self.name}] Added message to state")

    def update_stage(self, state: AgentState, stage: str) -> None:
        """Update the workflow stage in state.

        Args:
            state: Agent state
            stage: New stage name
        """
        state["stage"] = stage
        logger.info(f"[{self.name}] Stage updated to: {stage}")

    def set_error(self, state: AgentState, error: str) -> None:
        """Set an error in the state.

        Args:
            state: Agent state
            error: Error message
        """
        state["error"] = error
        logger.error(f"[{self.name}] Error set: {error}")

    def increment_retry(self, state: AgentState) -> int:
        """Increment and return the retry count.

        Args:
            state: Agent state

        Returns:
            New retry count
        """
        state["retry_count"] = state.get("retry_count", 0) + 1
        logger.warning(f"[{self.name}] Retry count: {state['retry_count']}")
        return state["retry_count"]

    def clear_error(self, state: AgentState) -> None:
        """Clear error from state.

        Args:
            state: Agent state
        """
        state["error"] = ""
        state["retry_count"] = 0
        logger.debug(f"[{self.name}] Error cleared")

    def should_retry(self, state: AgentState, max_retries: int = 3) -> bool:
        """Check if operation should be retried.

        Args:
            state: Agent state
            max_retries: Maximum number of retries allowed

        Returns:
            True if should retry, False otherwise
        """
        retry_count = state.get("retry_count", 0)
        has_error = bool(state.get("error"))
        return has_error and retry_count < max_retries


class LLMAgent(BaseAgent):
    """Agent that uses LLM for text generation tasks.

    This is a simpler agent class for agents that primarily
    generate text (PRD, Design, etc.) without complex workflows.
    """

    def __init__(
        self,
        name: str,
        model_config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None
    ):
        """Initialize the LLM agent.

        Args:
            name: Agent name
            model_config: Model configuration
            system_prompt: System prompt
        """
        super().__init__(name, model_config, system_prompt)

    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt."""
        pass

    @abstractmethod
    def _build_prompt(self, state: AgentState) -> str:
        """Build the prompt for LLM invocation.

        Args:
            state: Current agent state

        Returns:
            Prompt string
        """
        pass

    @abstractmethod
    def _parse_response(self, response: str, state: AgentState) -> Dict[str, Any]:
        """Parse the LLM response into state updates.

        Args:
            response: LLM response text
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        pass

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the agent: invoke LLM and parse response.

        Args:
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        logger.info(f"[{self.name}] Executing agent")

        try:
            # Build prompt
            prompt = self._build_prompt(state)

            # Invoke LLM
            response = self.invoke_llm(prompt)

            # Parse response
            updates = self._parse_response(response, state)

            # Add success message
            self.add_message(state, f"Completed successfully")

            logger.info(f"[{self.name}] Execution completed")
            return updates

        except Exception as e:
            error_msg = f"Execution failed: {e}"
            logger.error(f"[{self.name}] {error_msg}")
            self.set_error(state, error_msg)
            return {"error": error_msg}


class ToolAgent(BaseAgent):
    """Agent that uses tools (like Claude CLI) for execution.

    This agent class is for agents that execute commands and
    perform actions beyond text generation.
    """

    def __init__(
        self,
        name: str,
        model_config: Optional[ModelConfig] = None,
        system_prompt: Optional[str] = None
    ):
        """Initialize the tool agent.

        Args:
            name: Agent name
            model_config: Model configuration
            system_prompt: System prompt
        """
        super().__init__(name, model_config, system_prompt)

    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt."""
        pass

    @abstractmethod
    def _execute_tool(self, state: AgentState) -> Dict[str, Any]:
        """Execute the primary tool operation.

        Args:
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        pass

    def execute(self, state: AgentState) -> Dict[str, Any]:
        """Execute the agent: run tool operations.

        Args:
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        logger.info(f"[{self.name}] Executing agent")

        try:
            # Execute tool operation
            updates = self._execute_tool(state)

            # Add success message
            self.add_message(state, "Completed successfully")

            logger.info(f"[{self.name}] Execution completed")
            return updates

        except Exception as e:
            error_msg = f"Execution failed: {e}"
            logger.error(f"[{self.name}] {error_msg}")
            self.set_error(state, error_msg)
            return {"error": error_msg}
