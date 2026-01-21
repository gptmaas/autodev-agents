# AutoDev Agents

A LangGraph + Claude Code multi-agent system for automated software development.

[中文文档](README_CN.md) | English Documentation

## Overview

This project implements a Manager-Worker architecture where:
- **LangGraph** acts as the Manager (orchestrates workflow, manages state, makes routing decisions)
- **Claude Code CLI** acts as the Worker (executes coding tasks via CLI)

The system takes a requirement and generates:
1. Product Requirements Document (PRD)
2. Technical Design Document
3. Working code implementation

## Project Structure

```
autodev-agents/
├── src/
│   ├── main.py                           # Entry point CLI
│   ├── config/
│   │   ├── settings.py                   # Configuration & env management
│   │   └── prompts.py                    # Agent prompt templates
│   ├── core/
│   │   ├── state.py                      # AgentState TypedDict
│   │   ├── graph.py                      # LangGraph workflow definition
│   │   └── checkpoint_manager.py         # Checkpoint setup
│   ├── agents/
│   │   ├── base.py                       # Base agent class
│   │   ├── pm_agent.py                   # PRD generation
│   │   ├── review_agent.py               # PRD review
│   │   ├── architect_agent.py            # Technical design
│   │   ├── coder_agent.py                # Code execution loop
│   │   ├── qa_agent.py                   # Testing
│   │   └── bug_fix_agent.py              # Bug resolution
│   ├── tools/
│   │   ├── claude_cli.py                 # Claude Code CLI wrapper
│   │   ├── file_ops.py                   # File operations
│   │   └── validation.py                 # Output validators
│   └── utils/
│       ├── logger.py                     # Structured logging
│       └── helpers.py                    # Utilities
├── workspace/                            # Working directory for generated files
├── tests/
│   ├── test_agents/
│   ├── test_tools/
│   └── fixtures/
├── examples/
│   └── simple_todo_app.py                # Example workflow
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd autodev-agents
```

2. Install dependencies:
```bash
pip install -e ".[dev]"
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Usage

### Start a New Project

```bash
python -m src.main start "Build a simple Python CLI todo app with JSON storage"
```

The system will:
1. Generate a PRD and pause for review
2. Generate a Technical Design and pause for review
3. Execute the implementation automatically

### Resume from Checkpoint

```bash
# After reviewing artifacts, continue the workflow
python -m src.main continue
```

### Check Status

```bash
# Show current state of a session
python -m src.main status <session_id>
```

## Architecture

### Agents (MVP)

1. **PM Agent**: Generates PRD from requirements
2. **Architect Agent**: Creates technical design and task breakdown
3. **Coder Agent**: Executes coding tasks via Claude Code CLI

### Workflow

```
Requirement → [PM Agent] → PRD.md (human review)
         → [Architect Agent] → Design.md + tasks.json (human review)
         → [Coder Agent] → Code Implementation
```

## Development

### Run Tests

```bash
pytest
```

### Run Example

```bash
python examples/simple_todo_app.py
```

## Configuration

See `.env.example` for all configuration options:

- `ANTHROPIC_API_KEY`: Required for Claude API access
- `DEFAULT_MODEL`: Model to use for agents
- `WORKSPACE_ROOT`: Directory for generated files
- `CLAUDE_CLI_TIMEOUT`: Timeout for Claude Code CLI commands

## License

MIT
