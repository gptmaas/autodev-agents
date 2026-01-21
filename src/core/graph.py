"""LangGraph workflow definition for the multi-agent system."""

from typing import Literal, Optional, Any, Dict
from pathlib import Path

from langgraph.graph import StateGraph, END

from .state import AgentState, create_initial_state
from .checkpoint_manager import get_checkpointer
from ..agents.pm_agent import pm_agent_node
from ..agents.architect_agent import architect_agent_node
from ..agents.coder_agent import coder_agent_node, check_coding_finished, coder_batch_node
from ..config.settings import get_settings
from ..utils.logger import get_logger
from ..utils.helpers import generate_session_id
from ..tools.file_ops import read_file, parse_tasks_json


logger = get_logger()


def reconstruct_state_from_workspace(session_id: str) -> Optional[Dict[str, Any]]:
    """Reconstruct state from workspace files when checkpoint is not available.

    Args:
        session_id: Session identifier

    Returns:
        Reconstructed state dictionary or None if workspace not found
    """
    settings = get_settings()
    workspace = settings.get_session_workspace(session_id)

    if not workspace.exists():
        logger.warning(f"Workspace not found for session: {session_id}")
        return None

    # Reconstruct state from files
    state = create_initial_state("", session_id)
    state["session_id"] = session_id

    # Check for PRD
    prd_path = workspace / "PRD.md"
    if prd_path.exists():
        try:
            prd_content = read_file(prd_path)
            state["prd_content"] = prd_content
            state["prd_file_path"] = str(prd_path)
            state["prd_iteration"] = 1
            # Don't set stage yet - let the workflow determine where to continue
            logger.info(f"Reconstructed PRD from: {prd_path}")
        except Exception as e:
            logger.error(f"Failed to read PRD: {e}")

    # Check for Design
    design_path = workspace / "Design.md"
    if design_path.exists():
        try:
            design_content = read_file(design_path)
            state["design_content"] = design_content
            state["design_file_path"] = str(design_path)
            state["design_iteration"] = 1
            # Don't set stage yet
            logger.info(f"Reconstructed Design from: {design_path}")
        except Exception as e:
            logger.error(f"Failed to read Design: {e}")

    # Check for tasks
    tasks_path = workspace / "tasks.json"
    if tasks_path.exists():
        try:
            tasks = parse_tasks_json(tasks_path)
            state["task_list"] = tasks
            logger.info(f"Reconstructed {len(tasks)} tasks from: {tasks_path}")
        except Exception as e:
            logger.error(f"Failed to read tasks: {e}")

    # Determine stage based on what exists
    if state.get("task_list"):
        state["stage"] = "dev"
    elif state.get("design_content"):
        state["stage"] = "design"
    elif state.get("prd_content"):
        state["stage"] = "prd"
    else:
        state["stage"] = "prd"

    return state


def build_workflow(
    human_in_loop: bool = True,
    batch_coding: bool = False
) -> StateGraph:
    """Build the LangGraph workflow for the multi-agent system.

    Args:
        human_in_loop: Whether to include human interrupt points
        batch_coding: Whether to execute all coding tasks at once

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Building LangGraph workflow")

    # Create the state graph
    workflow = StateGraph(AgentState)

    # Add nodes for each agent
    workflow.add_node("pm", pm_agent_node)
    workflow.add_node("architect", architect_agent_node)

    if batch_coding:
        # Use batch coder (executes all tasks at once)
        workflow.add_node("coder", coder_batch_node)
    else:
        # Use iterative coder (one task per invocation)
        workflow.add_node("coder", coder_agent_node)

    # Set entry point
    workflow.set_entry_point("pm")

    # Define edges between nodes
    # PM -> Architect (always proceeds after PRD is generated)
    workflow.add_edge("pm", "architect")

    # Architect -> Coder (always proceeds after design is generated)
    workflow.add_edge("architect", "coder")

    # Coder loop
    if not batch_coding:
        # Conditional edge: check if coding is complete
        workflow.add_conditional_edges(
            "coder",
            check_coding_finished,
            {
                "continue_coding": "coder",
                "coding_done": END
            }
        )
    else:
        # Batch coder goes directly to END
        workflow.add_edge("coder", END)

    # Compile with checkpointer
    checkpointer = get_checkpointer()
    settings = get_settings()

    # Configure interrupt points for human-in-the-loop
    interrupt_before = []
    interrupt_after = []

    if human_in_loop:
        # Interrupt after PM (so human can review PRD)
        interrupt_after.append("pm")
        # Interrupt after Architect (so human can review Design)
        interrupt_after.append("architect")

    compiled = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after
    )

    logger.info(f"Workflow compiled with human-in-loop: {human_in_loop}")
    return compiled


def create_workflow_session(
    requirement: str,
    session_id: Optional[str] = None,
    human_in_loop: bool = True,
    batch_coding: bool = False
) -> tuple[StateGraph, str, Dict[str, Any]]:
    """Create a new workflow session.

    Args:
        requirement: User requirement/description
        session_id: Optional session ID (generated if not provided)
        human_in_loop: Whether to include human interrupt points
        batch_coding: Whether to execute all coding tasks at once

    Returns:
        Tuple of (compiled_workflow, session_id, initial_state)
    """
    if session_id is None:
        session_id = generate_session_id()

    logger.info(f"Creating workflow session: {session_id}")

    # Build workflow
    workflow = build_workflow(
        human_in_loop=human_in_loop,
        batch_coding=batch_coding
    )

    # Create initial state
    initial_state = create_initial_state(requirement, session_id)

    logger.info(f"Session {session_id} created with requirement: {requirement[:100]}...")

    return workflow, session_id, initial_state


def run_workflow_until_interrupt(
    workflow: StateGraph,
    initial_state: Dict[str, Any],
    session_id: str,
    max_steps: int = 10
) -> tuple[Dict[str, Any], str, Optional[Any]]:
    """Run the workflow until it hits an interrupt or completes.

    Args:
        workflow: Compiled StateGraph
        initial_state: Initial state dictionary
        session_id: Session identifier
        max_steps: Maximum number of steps to execute

    Returns:
        Tuple of (final_state, status, checkpoint)
        - status: "interrupted", "completed", or "error"
    """
    logger.info(f"Running workflow for session: {session_id}")

    # Create config for checkpointing
    config = {
        "configurable": {
            "thread_id": session_id
        }
    }

    try:
        # Execute the workflow
        step_count = 0
        state = initial_state

        for event in workflow.stream(state, config, stream_mode="values"):
            step_count += 1
            logger.debug(f"Step {step_count}: {event.get('stage', 'unknown')}")

            if step_count >= max_steps:
                logger.warning(f"Reached max steps ({max_steps})")
                break

        # Get the final state
        final_state = workflow.get_state(config).values
        next_node = workflow.get_state(config).next

        # Check if we're interrupted
        if next_node:
            logger.info(f"Workflow interrupted before: {next_node}")
            return final_state, "interrupted", workflow.get_state(config)
        else:
            logger.info("Workflow completed")
            return final_state, "completed", workflow.get_state(config)

    except Exception as e:
        logger.error(f"Workflow error: {e}")
        # Try to get current state
        try:
            current_state = workflow.get_state(config).values
            return current_state, "error", workflow.get_state(config)
        except:
            return state, "error", None


def resume_workflow(
    workflow: StateGraph,
    session_id: str,
    feedback: Optional[str] = None
) -> tuple[Dict[str, Any], str, Optional[Any]]:
    """Resume a workflow from a checkpoint.

    Args:
        workflow: Compiled StateGraph
        session_id: Session identifier
        feedback: Optional feedback to provide

    Returns:
        Tuple of (final_state, status, checkpoint)
    """
    logger.info(f"Resuming workflow for session: {session_id}")

    config = {
        "configurable": {
            "thread_id": session_id
        }
    }

    # Check if we have a valid checkpoint
    has_checkpoint = False
    try:
        state_snapshot = workflow.get_state(config)
        if state_snapshot and state_snapshot.values:
            has_checkpoint = True
            logger.info("Found valid checkpoint")
    except Exception as e:
        logger.debug(f"No checkpoint available: {e}")

    if has_checkpoint:
        # Resume from checkpoint using the normal flow
        return _resume_from_checkpoint(workflow, config, feedback)
    else:
        # Resume from workspace files
        return _resume_from_workspace(workflow, session_id, config, feedback)


def _resume_from_checkpoint(
    workflow: StateGraph,
    config: Dict[str, Any],
    feedback: Optional[str] = None
) -> tuple[Dict[str, Any], str, Optional[Any]]:
    """Resume workflow from a valid checkpoint.

    Args:
        workflow: Compiled StateGraph
        config: Workflow config with thread_id
        feedback: Optional feedback to provide

    Returns:
        Tuple of (final_state, status, checkpoint)
    """
    try:
        # Get current state
        current_state = workflow.get_state(config).values

        # Add feedback if provided
        if feedback:
            stage = current_state.get("stage", "")
            if stage == "prd":
                current_state["prd_feedback"] = feedback
            elif stage == "design":
                current_state["design_feedback"] = feedback
            current_state["human_feedback"] = feedback

        # Resume execution (this will continue from the interrupt)
        # We need to invoke None to signal "continue"
        for event in workflow.stream(None, config, stream_mode="values"):
            logger.debug(f"Resume step: {event.get('stage', 'unknown')}")

        # Get the final state
        final_state = workflow.get_state(config).values
        next_node = workflow.get_state(config).next

        if next_node:
            logger.info(f"Workflow interrupted before: {next_node}")
            return final_state, "interrupted", workflow.get_state(config)
        else:
            logger.info("Workflow completed")
            return final_state, "completed", workflow.get_state(config)

    except Exception as e:
        logger.error(f"Workflow resume error: {e}")
        try:
            current_state = workflow.get_state(config).values
            return current_state, "error", workflow.get_state(config)
        except:
            return {}, "error", None


def _resume_from_workspace(
    workflow: StateGraph,
    session_id: str,
    config: Dict[str, Any],
    feedback: Optional[str] = None
) -> tuple[Dict[str, Any], str, Optional[Any]]:
    """Resume workflow from workspace files when checkpoint is not available.

    Args:
        workflow: Compiled StateGraph
        session_id: Session identifier
        config: Workflow config with thread_id
        feedback: Optional feedback to provide

    Returns:
        Tuple of (final_state, status, checkpoint)
    """
    try:
        # Reconstruct state from workspace files
        current_state = reconstruct_state_from_workspace(session_id)
        if current_state is None:
            raise ValueError(f"Cannot resume session {session_id}: no workspace files found")

        stage = current_state.get("stage", "prd")
        logger.info(f"Resuming from workspace at stage: {stage}")

        # Add feedback if provided
        if feedback:
            if stage == "prd":
                current_state["prd_feedback"] = feedback
            elif stage == "design":
                current_state["design_feedback"] = feedback
            current_state["human_feedback"] = feedback

        # Determine which node to run next based on stage
        if stage == "prd":
            # PRD exists but not yet reviewed/approved, run architect next
            logger.info("PRD completed, running architect agent")
            # Update state to mark PRD stage complete
            current_state["stage"] = "design"
            # Run architect node directly
            result = architect_agent_node(current_state)
            current_state.update(result)

            # Check if we should continue
            if current_state.get("design_content"):
                # Design generated, this is the next interrupt point
                logger.info("Design generated, workflow interrupted for review")
                return current_state, "interrupted", None

        elif stage == "design":
            # Design exists, run coder next
            logger.info("Design completed, running coder agent")
            current_state["stage"] = "dev"

            # For coding, we use the batch coder to run all tasks
            result = coder_batch_node(current_state)
            current_state.update(result)

            # Check if coding is complete
            task_list = current_state.get("task_list", [])
            current_index = current_state.get("current_task_index", 0)
            if current_index >= len(task_list):
                logger.info("All tasks completed")
                current_state["stage"] = "done"
                return current_state, "completed", None
            else:
                return current_state, "interrupted", None

        elif stage == "dev":
            # In development phase, continue coding
            logger.info("Continuing development phase")

            result = coder_batch_node(current_state)
            current_state.update(result)

            task_list = current_state.get("task_list", [])
            current_index = current_state.get("current_task_index", 0)
            if current_index >= len(task_list):
                logger.info("All tasks completed")
                current_state["stage"] = "done"
                return current_state, "completed", None
            else:
                return current_state, "interrupted", None

        else:
            logger.info(f"Stage is '{stage}', workflow complete")
            current_state["stage"] = "done"
            return current_state, "completed", None

    except Exception as e:
        logger.error(f"Workspace resume error: {e}")
        import traceback
        traceback.print_exc()
        return {}, "error", None


def get_workflow_state(workflow: StateGraph, session_id: str) -> Optional[Dict[str, Any]]:
    """Get the current state of a workflow session.

    Args:
        workflow: Compiled StateGraph
        session_id: Session identifier

    Returns:
        Current state dictionary or None if not found
    """
    config = {
        "configurable": {
            "thread_id": session_id
        }
    }

    try:
        state_snapshot = workflow.get_state(config)
        return state_snapshot.values if state_snapshot else None
    except Exception as e:
        logger.error(f"Error getting workflow state: {e}")
        return None


def print_workflow_summary(state: Dict[str, Any]) -> None:
    """Print a summary of the workflow state.

    Args:
        state: Agent state dictionary
    """
    print("\n" + "=" * 60)
    print("WORKFLOW SUMMARY")
    print("=" * 60)

    print(f"Session ID: {state.get('session_id', 'N/A')}")
    print(f"Stage: {state.get('stage', 'N/A')}")
    print(f"Iteration: {state.get('prd_iteration', 0) + state.get('design_iteration', 0)}")

    # PRD status
    if state.get("prd_file_path"):
        print(f"\nPRD: {state['prd_file_path']}")
    else:
        print("\nPRD: Not generated")

    # Design status
    if state.get("design_file_path"):
        print(f"Design: {state['design_file_path']}")
    else:
        print("Design: Not generated")

    # Tasks status
    task_list = state.get("task_list", [])
    if task_list:
        completed = len(state.get("completed_tasks", []))
        print(f"Tasks: {completed}/{len(task_list)} completed")
    else:
        print("Tasks: Not generated")

    # Code status
    if state.get("code_directory"):
        print(f"Code: {state['code_directory']}")

    # Error status
    if state.get("error"):
        print(f"\nError: {state['error']}")

    print("=" * 60 + "\n")
