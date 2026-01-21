"""Main CLI interface for the AutoDev multi-agent system."""

import sys
import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from .config.settings import get_settings, reset_settings
from .core.graph import (
    build_workflow,
    create_workflow_session,
    run_workflow_until_interrupt,
    resume_workflow,
    get_workflow_state,
    print_workflow_summary
)
from .utils.logger import setup_logger, get_logger
from .utils.helpers import generate_session_id


console = Console()
logger = None


def init_cli():
    """Initialize CLI dependencies."""
    global logger
    settings = get_settings()
    logger = setup_logger(
        "autodev",
        level=settings.logging.level,
        log_file=settings.logging.log_file,
        use_colors=settings.logging.use_colors
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="启用详细输出")
@click.option("--human-loop", is_flag=True, help="启用人工审核（在 PRD 和 Design 阶段后暂停等待审核）")
@click.option("--batch-coding", is_flag=True, help="批量执行所有编码任务")
@click.pass_context
def cli(ctx, verbose, human_loop, batch_coding):
    """AutoDev Agents - 智能软件开发多智能体系统。"""
    init_cli()

    # Store options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["human_in_loop"] = human_loop  # 直接使用 human_loop 标志
    ctx.obj["batch_coding"] = batch_coding


@cli.command()
@click.argument("requirement", required=True)
@click.option("--session-id", "-s", help="自定义会话 ID")
@click.option("--output", "-o", help="会话信息输出文件")
@click.pass_context
def start(ctx, requirement, session_id, output):
    """启动新的工作流。

    示例: autodev start "构建一个简单的 Python CLI 待办事项应用"
    """
    human_in_loop = ctx.obj["human_in_loop"]
    batch_coding = ctx.obj["batch_coding"]

    console.print(Panel.fit(f"[bold blue]启动新工作流[/bold blue]"))
    console.print(f"需求: {requirement}")
    console.print(f"人工审核: {'是' if human_in_loop else '否'}")
    console.print(f"批量编码: {'是' if batch_coding else '否'}")
    console.print()

    try:
        # Create workflow session
        workflow, session_id, initial_state = create_workflow_session(
            requirement=requirement,
            session_id=session_id,
            human_in_loop=human_in_loop,
            batch_coding=batch_coding
        )

        # Run until interrupt or completion
        final_state, status, checkpoint = run_workflow_until_interrupt(
            workflow=workflow,
            initial_state=initial_state,
            session_id=session_id
        )

        # Display results
        _display_workflow_result(final_state, status, session_id)

        # Save session info if requested
        if output:
            _save_session_info(final_state, session_id, status, output)

    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        logger.error(f"Start command failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("session_id", required=True)
@click.option("--feedback", "-f", help="为当前阶段提供反馈")
@click.option("--output", "-o", help="会话信息输出文件")
@click.pass_context
def continue_cmd(ctx, session_id, feedback, output):
    """从检查点恢复工作流。

    示例: autodev continue <session_id> --feedback "为第3节添加更多细节"
    """
    try:
        # Build workflow with same settings
        human_in_loop = ctx.obj["human_in_loop"]
        batch_coding = ctx.obj["batch_coding"]

        workflow = build_workflow(
            human_in_loop=human_in_loop,
            batch_coding=batch_coding
        )

        console.print(Panel.fit(f"[bold blue]恢复工作流[/bold blue]"))
        console.print(f"会话 ID: {session_id}")

        if feedback:
            console.print(f"反馈: {feedback}")

        console.print()

        # Resume workflow
        final_state, status, checkpoint = resume_workflow(
            workflow=workflow,
            session_id=session_id,
            feedback=feedback
        )

        # Display results
        _display_workflow_result(final_state, status, session_id)

        # Save session info if requested
        if output:
            _save_session_info(final_state, session_id, status, output)

    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        logger.error(f"Continue command failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("session_id", required=True)
@click.option("--json", "as_json", is_flag=True, help="以 JSON 格式输出")
def status(session_id, as_json):
    """显示工作流会话的当前状态。

    示例: autodev status <session_id>
    """
    try:
        # Build workflow
        workflow = build_workflow()

        # Get state
        state = get_workflow_state(workflow, session_id)

        if state is None:
            console.print(f"[red]会话未找到: {session_id}[/red]")
            sys.exit(1)

        if as_json:
            # Output as JSON
            console.print(json.dumps(state, indent=2, default=str))
        else:
            # Display formatted status
            _display_status(state, session_id)

    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        logger.error(f"Status command failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("session_id", required=True)
@click.option("--artifact", "-a", help="显示的文档类型 (prd, design, tasks)")
def show(session_id, artifact):
    """显示工作流会话的文档。

    示例:
      autodev show <session_id> --artifact prd
      autodev show <session_id> --artifact design
      autodev show <session_id> --artifact tasks
    """
    try:
        # Build workflow
        workflow = build_workflow()

        # Get state
        state = get_workflow_state(workflow, session_id)

        if state is None:
            console.print(f"[red]会话未找到: {session_id}[/red]")
            sys.exit(1)

        # Display the requested artifact
        if artifact == "prd":
            _display_prd(state)
        elif artifact == "design":
            _display_design(state)
        elif artifact == "tasks":
            _display_tasks(state)
        else:
            # Show all artifacts
            _display_prd(state)
            console.print()
            _display_design(state)
            console.print()
            _display_tasks(state)

    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        logger.error(f"Show command failed: {e}")
        sys.exit(1)


@cli.command()
def list_sessions():
    """列出所有工作流会话。

    示例: autodev list-sessions
    """
    try:
        settings = get_settings()
        workspace = Path(settings.workspace.root)

        if not workspace.exists():
            console.print("[yellow]No sessions found (workspace doesn't exist)[/yellow]")
            return

        # Find all session directories
        sessions = [d for d in workspace.iterdir() if d.is_dir()]

        if not sessions:
            console.print("[yellow]No sessions found[/yellow]")
            return

        # Create table
        table = Table(title="Workflow Sessions")
        table.add_column("Session ID", style="cyan")
        table.add_column("Stage", style="magenta")
        table.add_column("PRD", style="green")
        table.add_column("Design", style="green")
        table.add_column("Tasks", style="green")

        for session_dir in sorted(sessions, reverse=True):
            session_id = session_dir.name

            # Check for artifacts
            prd_exists = (session_dir / "PRD.md").exists()
            design_exists = (session_dir / "Design.md").exists()
            tasks_exists = (session_dir / "tasks.json").exists()

            # Try to get stage from state
            stage = "unknown"

            table.add_row(
                session_id,
                stage,
                "[green]✓[/green]" if prd_exists else "[red]✗[/red]",
                "[green]✓[/green]" if design_exists else "[red]✗[/red]",
                "[green]✓[/green]" if tasks_exists else "[red]✗[/red]"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"List sessions command failed: {e}")
        sys.exit(1)


def _display_workflow_result(state: dict, status: str, session_id: str):
    """Display workflow execution result."""
    console.print()

    if status == "interrupted":
        stage = state.get("stage", "unknown")

        if stage == "prd":
            console.print(Panel.fit(
                f"[bold green]PRD Generated[/bold green]\n\n"
                f"Review the PRD and provide feedback using:\n"
                f"[cyan]autodev continue {session_id} --feedback \"your feedback\"[/cyan]\n\n"
                f"Or continue without feedback:\n"
                f"[cyan]autodev continue {session_id}[/cyan]",
                title="Workflow Paused"
            ))
            _display_prd(state)

        elif stage == "design":
            console.print(Panel.fit(
                f"[bold green]Design Document Generated[/bold green]\n\n"
                f"Review the Design and provide feedback using:\n"
                f"[cyan]autodev continue {session_id} --feedback \"your feedback\"[/cyan]\n\n"
                f"Or continue without feedback:\n"
                f"[cyan]autodev continue {session_id}[/cyan]",
                title="Workflow Paused"
            ))
            _display_design(state)
            _display_tasks_summary(state)

        elif stage == "dev":
            console.print(Panel.fit(
                f"[bold green]Coding in Progress[/bold green]\n\n"
                f"Continue to execute more tasks:\n"
                f"[cyan]autodev continue {session_id}[/cyan]",
                title="Workflow Paused"
            ))
            _display_tasks_summary(state)

    elif status == "completed":
        console.print(Panel.fit(
            f"[bold green]Workflow Completed[/bold green]\n\n"
            f"Session: [cyan]{session_id}[/cyan]\n"
            f"Check the workspace directory for generated files.",
            title="Success"
        ))
        print_workflow_summary(state)

    elif status == "error":
        console.print(Panel.fit(
            f"[bold red]Workflow Error[/bold red]\n\n"
            f"Error: {state.get('error', 'Unknown error')}",
            title="Error"
        ))


def _display_status(state: dict, session_id: str):
    """Display detailed status of a session."""
    console.print(f"\n[bold]Session:[/bold] {session_id}")
    console.print(f"[bold]Stage:[/bold] {state.get('stage', 'unknown')}")

    # PRD status
    prd_path = state.get("prd_file_path")
    if prd_path:
        console.print(f"[bold]PRD:[/bold] {prd_path}")
    else:
        console.print("[bold]PRD:[/bold] Not generated")

    # Design status
    design_path = state.get("design_file_path")
    if design_path:
        console.print(f"[bold]Design:[/bold] {design_path}")
    else:
        console.print("[bold]Design:[/bold] Not generated")

    # Tasks status
    task_list = state.get("task_list", [])
    if task_list:
        completed = len(state.get("completed_tasks", []))
        console.print(f"[bold]Tasks:[/bold] {completed}/{len(task_list)} completed")
    else:
        console.print("[bold]Tasks:[/bold] Not generated")

    # Code status
    code_dir = state.get("code_directory")
    if code_dir:
        console.print(f"[bold]Code:[/bold] {code_dir}")

    # Iterations
    prd_iter = state.get("prd_iteration", 0)
    design_iter = state.get("design_iteration", 0)
    console.print(f"[bold]Iterations:[/bold] PRD={prd_iter}, Design={design_iter}")

    # Error
    if state.get("error"):
        console.print(f"\n[red][bold]Error:[/bold] {state['error']}[/red]")


def _display_prd(state: dict):
    """Display PRD content."""
    prd_content = state.get("prd_content", "")
    if prd_content:
        console.print("\n[bold cyan]Product Requirements Document:[/bold cyan]")
        console.print(Panel(prd_content[:2000], border_style="cyan"))
        if len(prd_content) > 2000:
            console.print(f"... ({len(prd_content) - 2000} more characters)")


def _display_design(state: dict):
    """Display Design content."""
    design_content = state.get("design_content", "")
    if design_content:
        console.print("\n[bold cyan]Technical Design Document:[/bold cyan]")
        console.print(Panel(design_content[:2000], border_style="cyan"))
        if len(design_content) > 2000:
            console.print(f"... ({len(design_content) - 2000} more characters)")


def _display_tasks(state: dict):
    """Display tasks list."""
    task_list = state.get("task_list", [])
    if task_list:
        table = Table(title="Tasks")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Status", style="magenta")
        table.add_column("Priority", style="yellow")

        for task in task_list:
            status = task.get("status", "unknown")
            status_style = "green" if status == "completed" else "yellow"

            table.add_row(
                task["id"],
                task["title"][:50],
                f"[{status_style}]{status}[/{status_style}]",
                str(task.get("priority", 0))
            )

        console.print(table)


def _display_tasks_summary(state: dict):
    """Display summary of tasks."""
    task_list = state.get("task_list", [])
    completed = state.get("completed_tasks", [])

    if task_list:
        console.print(f"\n[bold]Tasks Progress:[/bold] {len(completed)}/{len(task_list)} completed")

        # Show pending tasks
        pending = [t for t in task_list if t["id"] not in completed and t.get("status") != "completed"]
        if pending:
            console.print(f"\n[bold]Pending Tasks:[/bold]")
            for task in pending[:5]:  # Show first 5
                console.print(f"  - {task['id']}: {task['title'][:50]}")
            if len(pending) > 5:
                console.print(f"  ... and {len(pending) - 5} more")


def _save_session_info(state: dict, session_id: str, status: str, output: str):
    """Save session info to a file."""
    output_path = Path(output)

    info = {
        "session_id": session_id,
        "status": status,
        "stage": state.get("stage"),
        "prd_file": state.get("prd_file_path"),
        "design_file": state.get("design_file_path"),
        "code_directory": state.get("code_directory"),
        "tasks": len(state.get("task_list", [])),
        "completed_tasks": len(state.get("completed_tasks", [])),
    }

    with output_path.open("w") as f:
        json.dump(info, f, indent=2)

    console.print(f"\n[green]Session info saved to: {output}[/green]")


# Entry point for "python -m src.main"
def main():
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
