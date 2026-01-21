"""PM Agent for generating Product Requirements Documents."""

from typing import Any, Dict

from ..core.state import AgentState
from ..agents.base import LLMAgent
from ..config.settings import get_settings
from ..config.prompts import PM_AGENT_SYSTEM_PROMPT, get_pm_prompt, get_pm_revision_prompt
from ..tools.file_ops import write_file
from ..tools.validation import OutputValidator, validate_prd
from ..utils.logger import get_logger
from ..utils.helpers import generate_session_id


logger = get_logger()


class PMAgent(LLMAgent):
    """Product Manager Agent responsible for PRD generation.

    This agent:
    - Analyzes user requirements
    - Generates comprehensive PRDs
    - Incorporates feedback to revise PRDs
    """

    def __init__(self):
        """Initialize the PM Agent."""
        settings = get_settings()
        super().__init__(
            name="PM_Agent",
            model_config=settings.pm_model,
            system_prompt=PM_AGENT_SYSTEM_PROMPT
        )

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for PM agent."""
        return PM_AGENT_SYSTEM_PROMPT

    def _build_prompt(self, state: AgentState) -> str:
        """Build the prompt for PRD generation.

        Args:
            state: Current agent state

        Returns:
            Prompt string
        """
        requirement = state.get("requirement", "")
        feedback = state.get("prd_feedback", "")
        iteration = state.get("prd_iteration", 0)

        if iteration > 0 and feedback:
            # Revision mode
            prd_content = state.get("prd_content", "")
            return get_pm_revision_prompt(prd_content, feedback)
        else:
            # Initial generation mode
            return get_pm_prompt(requirement, feedback)

    def _parse_response(self, response: str, state: AgentState) -> Dict[str, Any]:
        """Parse the LLM response into state updates.

        Args:
            response: LLM response text
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        logger.info("Parsing PRD response")

        # Validate PRD content
        is_valid, errors = validate_prd(response)
        if not is_valid:
            error_msg = f"PRD validation failed: {errors}"
            logger.warning(error_msg)
            # Still continue with the content, but log the issues

        # Save PRD to file
        session_id = state.get("session_id", generate_session_id())
        settings = get_settings()
        workspace = settings.get_session_workspace(session_id)
        prd_path = workspace / "PRD.md"

        try:
            write_file(prd_path, response)
            logger.info(f"PRD saved to: {prd_path}")
        except Exception as e:
            logger.error(f"Failed to save PRD: {e}")
            # Continue anyway, the content is in memory

        # Update state
        updates = {
            "prd_content": response,
            "prd_file_path": str(prd_path),
            "stage": "prd",
            "prd_iteration": state.get("prd_iteration", 0) + 1,
        }

        # Clear feedback after processing
        if state.get("prd_feedback"):
            updates["prd_feedback"] = ""

        return updates


def pm_agent_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node function for the PM agent.

    This function is called by LangGraph during workflow execution.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("PM Agent Node Invoked")
    logger.info("=" * 60)

    agent = PMAgent()
    return agent.execute(state)


def pm_revision_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node for PRD revision based on feedback.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("PM Revision Node Invoked")
    logger.info("=" * 60)

    # Check if there's feedback to process
    feedback = state.get("prd_feedback", "")
    if not feedback:
        logger.info("No PRD feedback, skipping revision")
        return {}

    agent = PMAgent()
    return agent.execute(state)


def validate_prd_node(state: AgentState) -> Dict[str, Any]:
    """Node for validating PRD before proceeding.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("Validating PRD")

    prd_content = state.get("prd_content", "")

    try:
        validator = OutputValidator()
        validator.validate_prd_output(prd_content)
        logger.info("PRD validation passed")
        return {"prd_validation_passed": True}
    except Exception as e:
        logger.error(f"PRD validation failed: {e}")
        return {
            "prd_validation_passed": False,
            "error": str(e)
        }
