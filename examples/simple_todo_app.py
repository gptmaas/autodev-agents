"""Example workflow for building a simple Todo CLI application.

This example demonstrates how to use the AutoDev multi-agent system
to build a simple Python CLI todo app with JSON storage.

Usage:
    python examples/simple_todo_app.py

The workflow will:
1. Generate a PRD for a simple todo CLI app
2. Create a technical design document
3. Execute the implementation tasks
4. Generate working code in workspace/
"""

import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.core.graph import (
    build_workflow,
    create_workflow_session,
    run_workflow_until_interrupt,
    resume_workflow,
    print_workflow_summary
)
from src.utils.logger import setup_logger, get_logger


def main():
    """Run the simple todo app workflow example."""
    # Setup logging
    logger = setup_logger("autodev_example", level="INFO")
    settings = get_settings()

    print("=" * 60)
    print("AutoDev Agents - Simple Todo App Example")
    print("=" * 60)
    print()

    # Define the requirement
    requirement = """
    Build a simple Python CLI todo application with the following features:

    1. Add a new todo item
    2. List all todo items
    3. Mark a todo item as completed
    4. Delete a todo item

    Technical requirements:
    - Use JSON file for data storage
    - Use argparse for CLI argument parsing
    - Include proper error handling
    - Follow Python best practices
    - Include a README with usage instructions
    """

    print(f"Requirement: {requirement.strip()}")
    print()
    print("Starting workflow...")
    print()

    # Create workflow session
    workflow, session_id, initial_state = create_workflow_session(
        requirement=requirement,
        session_id="simple_todo_example",
        human_in_loop=False,  # Run without human intervention for demo
        batch_coding=True  # Execute all coding tasks at once
    )

    print(f"Session ID: {session_id}")
    print()

    # Run the workflow
    print("Executing workflow (this may take several minutes)...")
    print()

    try:
        final_state, status, checkpoint = run_workflow_until_interrupt(
            workflow=workflow,
            initial_state=initial_state,
            session_id=session_id,
            max_steps=20
        )

        # Display results
        print_workflow_summary(final_state)

        # Show what was generated
        workspace = settings.get_session_workspace(session_id)
        print(f"\nWorkspace: {workspace}")
        print()

        # List generated files
        code_dir = settings.get_code_directory(session_id)
        if code_dir.exists():
            print("Generated files:")
            for file in sorted(code_dir.rglob("*")):
                if file.is_file():
                    print(f"  - {file.relative_to(code_dir)}")

        print()
        print("=" * 60)
        print("Workflow Complete!")
        print("=" * 60)
        print()
        print("You can now:")
        print(f"1. Review the generated code in: {code_dir}")
        print(f"2. Run the todo app: python {code_dir}/todo.py --help")
        print(f"3. Check the artifacts in: {workspace}")

    except Exception as e:
        print(f"\nError: {e}")
        logger.error(f"Workflow failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
