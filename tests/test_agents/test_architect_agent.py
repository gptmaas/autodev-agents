"""Unit tests for Architect Agent."""

import pytest
from unittest.mock import Mock, patch

from src.agents.architect_agent import ArchitectAgent, architect_agent_node
from src.core.state import create_initial_state


class TestArchitectAgent:
    """Test Architect Agent functionality."""

    def test_init(self):
        """Test Architect agent initialization."""
        agent = ArchitectAgent()
        assert agent.name == "Architect_Agent"
        assert agent.system_prompt is not None

    def test_get_default_system_prompt(self):
        """Test getting default system prompt."""
        agent = ArchitectAgent()
        prompt = agent._get_default_system_prompt()
        assert "Software Architect" in prompt
        assert "Technical Design" in prompt

    def test_build_prompt(self):
        """Test building prompt for design generation."""
        agent = ArchitectAgent()
        state = create_initial_state(
            requirement="Build a todo app",
            session_id="test_session"
        )
        state["prd_file_path"] = "/path/to/PRD.md"

        prompt = agent._build_prompt(state)

        assert "/path/to/PRD.md" in prompt
        assert "Technical Design" in prompt

    def test_split_design_and_tasks(self):
        """Test splitting design and tasks from response."""
        agent = ArchitectAgent()

        response = """
# Technical Design Document

## Architecture Overview
We will use a simple architecture.

```json
[
  {
    "id": "task_001",
    "title": "Setup project",
    "description": "Initialize the project structure",
    "dependencies": [],
    "status": "pending",
    "priority": 10
  }
]
```
"""
        design, tasks_json = agent._split_design_and_tasks(response)

        assert "Architecture Overview" in design
        assert tasks_json is not None
        assert "task_001" in tasks_json

    def test_split_design_no_tasks(self):
        """Test splitting when no tasks present."""
        agent = ArchitectAgent()

        response = """
# Technical Design Document

## Architecture Overview
Simple architecture.
"""
        design, tasks_json = agent._split_design_and_tasks(response)

        assert "Architecture Overview" in design
        assert tasks_json is None

    def test_extract_tasks_flexible(self):
        """Test flexible task extraction."""
        agent = ArchitectAgent()

        # Test markdown list format
        response = """
Tasks:
- **Task 1:** Setup project
  Create the basic structure
- **Task 2:** Implement features
  Add the main functionality
"""
        tasks = agent._extract_tasks_flexible(response)

        assert tasks is not None
        assert len(tasks) >= 1
        assert "id" in tasks[0]

    @patch('src.agents.base.ChatAnthropic')
    def test_parse_response(self, mock_llm, tmp_path):
        """Test parsing LLM response."""
        agent = ArchitectAgent()
        state = create_initial_state(
            requirement="Build a todo app",
            session_id="test_session"
        )

        response = """
# Technical Design Document

## Architecture Overview
- **Architecture Pattern**: MVC (Model-View-Controller)
- **Technology Stack**:
  - Language: Python 3.10+
  - Framework: Flask
  - Database: SQLite

## System Design
### Components
- API Layer: Handles HTTP requests and responses
- Data Layer: Manages data persistence and retrieval
- Business Logic: Implements core application functionality

### Data Models
```python
from dataclasses import dataclass

@dataclass
class TodoItem:
    id: int
    title: str
    completed: bool
```

## File Structure
```
project/
├── app/
│   ├── models.py
│   ├── routes.py
│   └── services.py
├── tests/
└── requirements.txt
```

## Implementation Approach
Use Flask framework with modular structure.
Phase 1: Setup project structure and dependencies.
Phase 2: Implement data models and database layer.
Phase 3: Build API endpoints and business logic.
Phase 4: Add testing and documentation.

This comprehensive design document provides detailed specifications for the system architecture.
We have carefully considered technology choices to ensure performance, scalability, and maintainability.
The chosen stack balances development speed with operational requirements for a robust production system.

## Testing Strategy
Unit tests with pytest for all components.
Integration tests for API endpoints.
End-to-end tests for user workflows.

```json
[
  {
    "id": "task_001",
    "title": "Setup project",
    "description": "Initialize project",
    "dependencies": [],
    "status": "pending",
    "priority": 10
  },
  {
    "id": "task_002",
    "title": "Implement API",
    "description": "Create endpoints",
    "dependencies": ["task_001"],
    "status": "pending",
    "priority": 9
  }
]
```
"""

        # Mock workspace
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_workspace = tmp_path / "test_session"
            mock_workspace.mkdir(parents=True, exist_ok=True)

            mock_settings.return_value.get_session_workspace.return_value = mock_workspace

            updates = agent._parse_response(response, state)

            assert "design_content" in updates
            assert "design_file_path" in updates
            assert "task_list" in updates
            assert updates["current_task_index"] == 0
            assert len(updates["task_list"]) == 2

    def test_architect_agent_node(self):
        """Test Architect agent node function."""
        state = create_initial_state(
            requirement="Build a simple calculator",
            session_id="test_node"
        )
        state["prd_file_path"] = "/path/to/PRD.md"

        with patch('src.agents.architect_agent.ArchitectAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.execute.return_value = {
                "design_content": "# Design",
                "design_file_path": "/path/to/Design.md",
                "task_list": [{"id": "task_001", "title": "Task 1"}]
            }
            mock_agent_class.return_value = mock_agent

            result = architect_agent_node(state)

            mock_agent.execute.assert_called_once()
            assert "design_content" in result
            assert "task_list" in result
