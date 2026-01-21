"""PRD Reviewer Agents for multi-perspective PRD evaluation.

This module contains three reviewer agents:
- PM Reviewer: Reviews from product management perspective
- Dev Reviewer: Reviews from technical implementation perspective
- QA Reviewer: Reviews from testing and quality perspective
"""

from typing import Any, Dict

from ..core.state import AgentState
from ..agents.base import LLMAgent
from ..config.settings import get_settings
from ..config.prompts import (
    get_prd_reviewer_prompt,
    get_pm_revision_with_reviews_prompt,
    PRD_REVIEWER_PM_SYSTEM_PROMPT,
    PRD_REVIEWER_DEV_SYSTEM_PROMPT,
    PRD_REVIEWER_QA_SYSTEM_PROMPT,
)
from ..tools.file_ops import write_file
from ..utils.logger import get_logger
from ..utils.helpers import generate_session_id


logger = get_logger()


class PRDReviewerAgent(LLMAgent):
    """Base class for PRD reviewer agents."""

    def __init__(self, role: str, system_prompt: str):
        """Initialize a PRD reviewer agent.

        Args:
            role: Reviewer role ("pm", "dev", "qa")
            system_prompt: System prompt for this reviewer
        """
        settings = get_settings()
        # Use pm_model for all reviewers (can be customized later)
        super().__init__(
            name=f"PRD_Reviewer_{role.upper()}",
            model_config=settings.pm_model,
            system_prompt=system_prompt
        )
        self.role = role

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt."""
        return self.system_prompt

    def _build_prompt(self, state: AgentState) -> str:
        """Build the prompt for PRD review.

        Args:
            state: Current agent state

        Returns:
            Prompt string
        """
        prd_content = state.get("prd_content", "")
        return get_prd_reviewer_prompt(self.role, prd_content)

    def _parse_response(self, response: str, state: AgentState) -> Dict[str, Any]:
        """Parse the LLM response into state updates.

        Args:
            response: LLM response text
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        logger.info(f"Parsing PRD review response from {self.role} reviewer")

        # Store review in prd_reviews
        prd_reviews = state.get("prd_reviews", {})
        prd_reviews[self.role] = response

        return {
            "prd_reviews": prd_reviews,
        }


class PMReviewerAgent(PRDReviewerAgent):
    """Product Manager PRD reviewer.

    Reviews from product management perspective, focusing on:
    - Requirement completeness
    - User value
    - Business logic
    - User experience
    """

    def __init__(self):
        super().__init__("pm", PRD_REVIEWER_PM_SYSTEM_PROMPT)


class DevReviewerAgent(PRDReviewerAgent):
    """Developer PRD reviewer.

    Reviews from technical implementation perspective, focusing on:
    - Technical feasibility
    - Implementation complexity
    - Technical risks
    - Design rationality
    """

    def __init__(self):
        super().__init__("dev", PRD_REVIEWER_DEV_SYSTEM_PROMPT)


class QAReviewerAgent(PRDReviewerAgent):
    """QA Engineer PRD reviewer.

    Reviews from testing and quality perspective, focusing on:
    - Testability
    - Test coverage
    - Quality standards
    - Defect prevention
    """

    def __init__(self):
        super().__init__("qa", PRD_REVIEWER_QA_SYSTEM_PROMPT)


def pm_reviewer_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node function for PM reviewer.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("PM Reviewer Node Invoked")
    logger.info("=" * 60)

    agent = PMReviewerAgent()
    return agent.execute(state)


def dev_reviewer_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node function for Dev reviewer.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("Dev Reviewer Node Invoked")
    logger.info("=" * 60)

    agent = DevReviewerAgent()
    return agent.execute(state)


def qa_reviewer_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node function for QA reviewer.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("QA Reviewer Node Invoked")
    logger.info("=" * 60)

    agent = QAReviewerAgent()
    return agent.execute(state)
