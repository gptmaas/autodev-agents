"""PM Agent for generating Product Requirements Documents."""

from typing import Any, Dict
import re

from ..core.state import AgentState
from ..agents.base import LLMAgent
from ..config.settings import get_settings
from ..config.prompts import PM_AGENT_SYSTEM_PROMPT, get_pm_prompt, get_pm_revision_prompt, get_pm_revision_with_reviews_prompt
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
        reviews = state.get("prd_reviews", {})
        iteration = state.get("prd_iteration", 0)

        # Check if this is a revision based on reviews
        if iteration > 0 and reviews and len(reviews) == 3:
            # Revision mode based on reviews from all three reviewers
            prd_content = state.get("prd_content", "")
            logger.info("Building prompt for PRD revision based on reviews")
            return get_pm_revision_with_reviews_prompt(prd_content, reviews)
        elif iteration > 0 and feedback:
            # Revision mode based on human feedback
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

        # Check if this is a revision based on reviews
        reviews = state.get("prd_reviews", {})
        iteration = state.get("prd_iteration", 0)

        # Extract revision summary if present (when revising based on reviews)
        revision_summary = ""
        if "# PRD 修订说明" in response or "# PRD Revision" in response:
            # Extract the revision summary section
            summary_match = re.search(
                r"# (PRD 修订说明|PRD Revision)\s*\n## (主要变更内容|Major Changes)\s*\n(.*?)(?=\n##|$)",
                response,
                re.DOTALL | re.MULTILINE
            )
            if summary_match:
                revision_summary = summary_match.group(3).strip()
                logger.info(f"Extracted revision summary: {revision_summary[:100]}...")

        # Save reviews to file if present
        reviews_path = ""
        if reviews and len(reviews) == 3:
            reviews_path = workspace / "PRD_Reviews.md"
            reviews_content = self._format_reviews_for_file(reviews)
            try:
                write_file(reviews_path, reviews_content)
                logger.info(f"PRD reviews saved to: {reviews_path}")
            except Exception as e:
                logger.error(f"Failed to save PRD reviews: {e}")

        # Update state
        updates = {
            "prd_content": response,
            "prd_file_path": str(prd_path),
            "prd_iteration": iteration + 1,
        }

        # If we just processed reviews, clear them and mark as reviewed
        if reviews and len(reviews) == 3:
            updates["prd_reviewed"] = True
            updates["prd_reviews_file_path"] = str(reviews_path)
            updates["prd_revision_summary"] = revision_summary

        # Determine next stage based on whether we've done reviews
        if state.get("prd_reviewed"):
            # Already reviewed, move to design stage
            updates["stage"] = "design"
        elif reviews and len(reviews) == 3:
            # Just finished revision based on reviews, move to design
            updates["stage"] = "design"
        else:
            # Still in PRD stage
            updates["stage"] = "prd"

        # Clear feedback after processing
        if state.get("prd_feedback"):
            updates["prd_feedback"] = ""

        return updates

    def _format_reviews_for_file(self, reviews: dict) -> str:
        """Format reviews for saving to a markdown file.

        Args:
            reviews: Dictionary of reviews with keys "pm", "dev", "qa"

        Returns:
            Formatted markdown string
        """
        role_names = {
            "pm": "产品经理",
            "dev": "开发工程师",
            "qa": "测试工程师",
        }

        output = "# PRD 评审意见汇总\n\n"
        output += f"评审时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        output += "---\n\n"

        for role, review in reviews.items():
            output += f"## {role_names.get(role, role)}评审意见\n\n"
            output += review
            output += "\n\n---\n\n"

        return output


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
