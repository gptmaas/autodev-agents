"""Architect Agent for generating technical design documents."""

import re
from typing import Any, Dict

from ..core.state import AgentState
from ..agents.base import LLMAgent
from ..config.settings import get_settings
from ..config.prompts import ARCHITECT_SYSTEM_PROMPT, get_architect_prompt
from ..tools.file_ops import write_file, parse_markdown_code_blocks, write_tasks_json
from ..tools.validation import OutputValidator, validate_design, validate_tasks, validate_tasks_json, validate_json_output
from ..utils.logger import get_logger
from ..utils.helpers import generate_session_id, extract_code_blocks


logger = get_logger()


class ArchitectAgent(LLMAgent):
    """Architect Agent responsible for technical design.

    This agent:
    - Reads the PRD
    - Creates comprehensive technical design documents
    - Generates task breakdowns (tasks.json)
    - Incorporates feedback to revise designs
    """

    def __init__(self):
        """Initialize the Architect Agent."""
        settings = get_settings()
        super().__init__(
            name="Architect_Agent",
            model_config=settings.architect_model,
            system_prompt=ARCHITECT_SYSTEM_PROMPT
        )

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for Architect agent."""
        return ARCHITECT_SYSTEM_PROMPT

    def _build_prompt(self, state: AgentState) -> str:
        """Build the prompt for design generation.

        Args:
            state: Current agent state

        Returns:
            Prompt string
        """
        prd_path = state.get("prd_file_path", "")
        feedback = state.get("design_feedback", "")

        prompt = get_architect_prompt(prd_path)

        if feedback:
            prompt += f"\n\n## Feedback to Address\n\n{feedback}\n\nPlease revise the design to address this feedback."

        return prompt

    def _parse_response(self, response: str, state: AgentState) -> Dict[str, Any]:
        """Parse the LLM response into state updates.

        Args:
            response: LLM response text
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        logger.info("Parsing design response")

        # Split design and tasks
        design_content, tasks_json = self._split_design_and_tasks(response)

        # Validate design content
        is_valid, errors = validate_design(design_content)
        if not is_valid:
            logger.warning(f"Design validation warnings: {errors}")

        # Parse and validate tasks
        tasks = None
        if tasks_json:
            is_valid, errors, parsed_tasks = validate_tasks_json(tasks_json)
            if is_valid:
                tasks = parsed_tasks
                logger.info(f"Parsed {len(tasks)} tasks")
            else:
                logger.warning(f"Tasks validation failed: {errors}")
                # Try to extract tasks more flexibly
                tasks = self._extract_tasks_flexible(response)
        else:
            # Try to extract tasks from response
            tasks = self._extract_tasks_flexible(response)

        # Save artifacts to workspace
        session_id = state.get("session_id", generate_session_id())
        settings = get_settings()
        workspace = settings.get_session_workspace(session_id)

        # Save design document
        design_path = workspace / "Design.md"
        try:
            write_file(design_path, design_content)
            logger.info(f"Design saved to: {design_path}")
        except Exception as e:
            logger.error(f"Failed to save design: {e}")

        # Save tasks.json
        tasks_path = workspace / "tasks.json"
        if tasks:
            try:
                write_tasks_json(tasks_path, tasks)
                logger.info(f"Tasks saved to: {tasks_path}")
            except Exception as e:
                logger.error(f"Failed to save tasks: {e}")

        # Update state
        updates = {
            "design_content": design_content,
            "design_file_path": str(design_path),
            "task_list": tasks or [],
            "current_task_index": 0,
            "stage": "design",
            "design_iteration": state.get("design_iteration", 0) + 1,
        }

        # Clear feedback after processing
        if state.get("design_feedback"):
            updates["design_feedback"] = ""

        return updates

    def _split_design_and_tasks(self, response: str) -> tuple[str, str | None]:
        """Split the response into design content and tasks JSON.

        Args:
            response: Full LLM response

        Returns:
            Tuple of (design_content, tasks_json_string)
        """
        # Look for JSON code block
        json_blocks = parse_markdown_code_blocks(response, "json")

        if json_blocks:
            # Extract the JSON block
            tasks_json = json_blocks[0][1]  # (language, content) tuple
            # Remove the JSON block from the response
            design_content = re.sub(r'```json\n.*?\n```', '', response, flags=re.DOTALL)
            return design_content.strip(), tasks_json

        # Look for tasks.json reference
        if "tasks.json" in response.lower():
            # Try to find JSON content after "tasks.json"
            match = re.search(r'tasks\.json[:\s]*```(?:json)?\s*\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
            if match:
                tasks_json = match.group(1).strip()
                design_content = response[:match.start()].strip()
                return design_content, tasks_json

        # No tasks found, return full response as design
        return response, None

    def _extract_tasks_flexible(self, response: str) -> list[dict] | None:
        """Try to extract tasks from response using various methods.

        Args:
            response: Full LLM response

        Returns:
            List of task dictionaries or None
        """
        import json

        # Method 1: Look for JSON array
        json_match = re.search(r'\[\s*\{.*?\}\s*\]', response, re.DOTALL)
        if json_match:
            try:
                tasks = json.loads(json_match.group(0))
                if isinstance(tasks, list) and len(tasks) > 0:
                    if "id" in tasks[0]:
                        return tasks
            except json.JSONDecodeError:
                pass

        # Method 2: Parse markdown list into tasks
        tasks = []
        task_pattern = r'[-*]\s+\*\*Task\s+(\d+)[:\s]*\*\*(.+?)(?=\n[-*]|\Z|\n\n|\Z)'
        matches = re.findall(task_pattern, response, re.DOTALL)

        for i, (num, content) in enumerate(matches):
            task_id = f"task_{int(num):03d}"
            # Extract title from content (first line)
            lines = content.strip().split('\n')
            title = lines[0].strip() if lines else f"Task {num}"
            description = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""

            tasks.append({
                "id": task_id,
                "title": title,
                "description": description or content.strip(),
                "dependencies": [],
                "status": "pending",
                "priority": 10 - i  # Earlier tasks have higher priority
            })

        if tasks:
            logger.info(f"Extracted {len(tasks)} tasks from markdown format")
            return tasks

        # Method 3: Generate default tasks based on PRD
        logger.warning("Could not extract tasks, generating placeholder tasks")
        return [
            {
                "id": "task_001",
                "title": "Review Design Document",
                "description": "Review the technical design document before implementation",
                "dependencies": [],
                "status": "pending",
                "priority": 10
            },
            {
                "id": "task_002",
                "title": "Implement Core Features",
                "description": "Implement the core features as specified in the design",
                "dependencies": ["task_001"],
                "status": "pending",
                "priority": 9
            }
        ]


def architect_agent_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node function for the Architect agent.

    This function is called by LangGraph during workflow execution.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("Architect Agent Node Invoked")
    logger.info("=" * 60)

    agent = ArchitectAgent()
    return agent.execute(state)


def architect_revision_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node for design revision based on feedback.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("Architect Revision Node Invoked")
    logger.info("=" * 60)

    # Check if there's feedback to process
    feedback = state.get("design_feedback", "")
    if not feedback:
        logger.info("No design feedback, skipping revision")
        return {}

    agent = ArchitectAgent()
    return agent.execute(state)


def validate_design_node(state: AgentState) -> Dict[str, Any]:
    """Node for validating design before proceeding.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("Validating design")

    design_content = state.get("design_content", "")
    task_list = state.get("task_list", [])

    try:
        validator = OutputValidator()

        # Validate design
        validator.validate_design_output(design_content)

        # Validate tasks
        validator.validate_tasks_output(task_list)

        logger.info("Design validation passed")
        return {"design_validation_passed": True}
    except Exception as e:
        logger.error(f"Design validation failed: {e}")
        return {
            "design_validation_passed": False,
            "error": str(e)
        }
