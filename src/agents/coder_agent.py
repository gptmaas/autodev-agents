"""Coder Agent for executing coding tasks via Claude Code CLI."""

from typing import Any, Dict, List

from ..core.state import AgentState
from ..agents.base import ToolAgent
from ..config.settings import get_settings
from ..config.prompts import CODER_SYSTEM_PROMPT, get_coder_prompt
from ..tools.claude_cli import run_claude_cli, create_non_interactive_prompt
from ..tools.file_ops import read_file, get_ready_tasks, get_task_by_id
from ..tools.validation import validate_coding_output
from ..utils.logger import get_logger
from ..utils.helpers import generate_session_id


logger = get_logger()


class CoderAgent(ToolAgent):
    """Coder Agent responsible for code execution.

    This agent:
    - Loops through tasks from task_list
    - For each task: calls Claude Code CLI
    - Validates completion
    - Updates current_task_index
    """

    def __init__(self):
        """Initialize the Coder Agent."""
        settings = get_settings()
        super().__init__(
            name="Coder_Agent",
            model_config=settings.coder_model,
            system_prompt=CODER_SYSTEM_PROMPT
        )
        self.max_iterations = settings.agent.max_coding_iterations

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for Coder agent."""
        return CODER_SYSTEM_PROMPT

    def _execute_tool(self, state: AgentState) -> Dict[str, Any]:
        """Execute coding tasks using Claude Code CLI.

        Args:
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        task_list = state.get("task_list", [])
        current_index = state.get("current_task_index", 0)
        completed_tasks = state.get("completed_tasks", [])
        coding_iterations = state.get("coding_iterations", 0)

        if not task_list:
            logger.warning("No tasks to execute")
            return {
                "stage": "done",
                "coding_output": "No tasks to execute"
            }

        # Check if we're done
        if current_index >= len(task_list):
            logger.info("All tasks completed")
            return {
                "stage": "done",
                "coding_output": f"Completed {len(completed_tasks)} tasks"
            }

        # Check iteration limit
        if coding_iterations >= self.max_iterations:
            logger.warning(f"Reached maximum coding iterations ({self.max_iterations})")
            return {
                "stage": "done",
                "coding_output": f"Reached maximum iterations. Completed {len(completed_tasks)}/{len(task_list)} tasks"
            }

        # Get current task
        task = task_list[current_index]

        # Check if task is already completed
        if task["id"] in completed_tasks or task.get("status") == "completed":
            logger.info(f"Task {task['id']} already completed, skipping")
            return {
                "current_task_index": current_index + 1,
                "coding_output": f"Task {task['id']} already completed"
            }

        # Check dependencies
        dependencies = task.get("dependencies", [])
        if not all(dep in completed_tasks for dep in dependencies):
            logger.info(f"Task {task['id']} has unmet dependencies, skipping")
            # Try to find a task that can be executed
            ready_tasks = get_ready_tasks(task_list, completed_tasks)
            if ready_tasks:
                # Execute the first ready task instead
                next_task = ready_tasks[0]
                next_index = next((i for i, t in enumerate(task_list) if t["id"] == next_task["id"]), current_index)
                return {
                    "current_task_index": next_index,
                    "coding_output": f"Switched to task {next_task['id']} (unmet dependencies for {task['id']})"
                }
            else:
                # No tasks ready, we're stuck
                logger.error("No tasks ready to execute (circular dependencies?)")
                return {
                    "stage": "done",
                    "coding_output": "No tasks ready to execute - possible circular dependencies"
                }

        # Execute the current task
        return self._execute_single_task(state, task)

    def _execute_single_task(self, state: AgentState, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single coding task.

        Args:
            state: Current agent state
            task: Task to execute

        Returns:
            Dictionary of state updates
        """
        logger.info(f"Executing task: {task['id']} - {task['title']}")

        # Get workspace
        session_id = state.get("session_id", generate_session_id())
        settings = get_settings()
        work_dir = str(settings.get_code_directory(session_id))
        design_path = state.get("design_file_path", "")

        # Read design for context
        design_content = ""
        if design_path:
            try:
                design_content = read_file(design_path)
            except Exception as e:
                logger.warning(f"Could not read design file: {e}")

        # Build the prompt for Claude Code CLI
        task_description = f"""
Task ID: {task['id']}
Title: {task['title']}
Description: {task.get('description', '')}

{f'References: {design_path}' if design_path else ''}

Implement this task according to the technical design.
"""
        prompt = create_non_interactive_prompt(
            task_description=task_description,
            context=f"Working in directory: {work_dir}",
            constraints=[
                "Do not ask for confirmation",
                "Create all necessary files",
                "Follow the design specification",
                "Include error handling",
                "Write clean, readable code"
            ]
        )

        # Execute via Claude Code CLI
        result = run_claude_cli(
            prompt=prompt,
            work_dir=work_dir
        )

        # Process result
        if result.success:
            logger.info(f"Task {task['id']} completed successfully")

            # Update task status in task list
            task_list = state.get("task_list", [])
            for t in task_list:
                if t["id"] == task["id"]:
                    t["status"] = "completed"
                    break

            # Update completed tasks
            completed_tasks = state.get("completed_tasks", [])
            completed_tasks.append(task["id"])

            # Update state
            current_index = state.get("current_task_index", 0)
            return {
                "task_list": task_list,
                "current_task_index": current_index + 1,
                "completed_tasks": completed_tasks,
                "coding_iterations": state.get("coding_iterations", 0) + 1,
                "coding_output": f"Task {task['id']} completed: {result.output[:500]}",
                "stage": "dev",
                "code_directory": work_dir
            }
        else:
            error_msg = f"Task {task['id']} failed: {result.error}"
            logger.error(error_msg)

            # Mark task as failed/blocked
            task_list = state.get("task_list", [])
            for t in task_list:
                if t["id"] == task["id"]:
                    t["status"] = "blocked"
                    break

            return {
                "task_list": task_list,
                "error": error_msg,
                "coding_iterations": state.get("coding_iterations", 0) + 1,
                "coding_output": error_msg
            }

    def execute_all_tasks(self, state: AgentState) -> Dict[str, Any]:
        """Execute all remaining tasks in a batch.

        This method loops through all tasks and executes them.
        Returns when all tasks are done or max iterations reached.

        Args:
            state: Current agent state

        Returns:
            Dictionary of state updates
        """
        logger.info("Executing all remaining tasks")

        task_list = state.get("task_list", [])
        total_tasks = len(task_list)
        completed_tasks = state.get("completed_tasks", [])

        for i in range(self.max_iterations):
            current_index = state.get("current_task_index", 0)

            # Check if done
            if current_index >= len(task_list):
                logger.info(f"All {total_tasks} tasks completed")
                return {
                    "stage": "done",
                    "coding_output": f"Completed all {total_tasks} tasks"
                }

            # Execute current task
            updates = self._execute_tool(state)
            state.update(updates)

            # Check for error
            if updates.get("error"):
                logger.warning(f"Task execution failed, continuing with next task")

        # Reached max iterations
        logger.warning(f"Reached maximum iterations, completed {len(completed_tasks)}/{total_tasks} tasks")
        return {
            "stage": "done",
            "coding_output": f"Reached maximum iterations. Completed {len(completed_tasks)}/{total_tasks} tasks"
        }


def coder_agent_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node function for the Coder agent.

    This function is called by LangGraph during workflow execution.
    It executes a single task and returns control to the graph.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("Coder Agent Node Invoked")
    logger.info("=" * 60)

    agent = CoderAgent()
    return agent.execute(state)


def check_coding_finished(state: AgentState) -> str:
    """Conditional edge function to check if coding is complete.

    Args:
        state: Current agent state

    Returns:
        Next node name: "continue_coding" or "coding_done"
    """
    task_list = state.get("task_list", [])
    current_index = state.get("current_task_index", 0)
    coding_iterations = state.get("coding_iterations", 0)

    # Get max iterations from settings
    settings = get_settings()
    max_iterations = settings.agent.max_coding_iterations

    # Check if all tasks are done
    if current_index >= len(task_list):
        logger.info("Coding phase complete - all tasks finished")
        return "coding_done"

    # Check if we've reached max iterations
    if coding_iterations >= max_iterations:
        logger.info(f"Coding phase complete - reached max iterations ({max_iterations})")
        return "coding_done"

    # Check if there's an error that prevents continuation
    if state.get("error") and not state.get("task_list"):
        logger.warning("Coding phase stopped due to error")
        return "coding_done"

    # Continue coding
    logger.info(f"Continuing coding (task {current_index + 1}/{len(task_list)})")
    return "continue_coding"


def coder_batch_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node that executes all remaining tasks at once.

    Use this for non-interactive workflows where you want to
    complete all coding in one go.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates
    """
    logger.info("=" * 60)
    logger.info("Coder Batch Node Invoked (Execute All Tasks)")
    logger.info("=" * 60)

    agent = CoderAgent()
    return agent.execute_all_tasks(state)
