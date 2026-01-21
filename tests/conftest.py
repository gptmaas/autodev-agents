"""Pytest configuration and fixtures."""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Set required environment variables before importing anything
os.environ["ANTHROPIC_API_KEY"] = "test_key_for_testing"


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.workspace = Mock()
    settings.workspace.root = "/tmp/test_workspace"
    settings.claude_cli = Mock()
    settings.claude_cli.timeout = 300
    settings.claude_cli.max_retries = 3
    settings.claude_cli.retry_delay = 1.0
    settings.agent = Mock()
    settings.agent.max_coding_iterations = 50
    settings.agent.human_in_loop = True
    settings.logging = Mock()
    settings.logging.level = "INFO"
    settings.logging.log_file = None
    settings.logging.use_colors = False
    settings.pm_model = Mock()
    settings.pm_model.model = "claude-3-5-sonnet-20241022"
    settings.architect_model = Mock()
    settings.architect_model.model = "claude-3-5-sonnet-20241022"
    settings.coder_model = Mock()
    settings.coder_model.model = "claude-3-5-sonnet-20241022"
    settings.default_model = Mock()
    settings.default_model.model = "claude-3-5-sonnet-20241022"
    settings.anthropic_api_key = "test_key"
    return settings


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@pytest.fixture
def sample_prd():
    """Sample PRD content for testing."""
    return """
# Product Requirements Document: Simple Todo App

## 1. Overview
- **Project Name**: Simple Todo CLI
- **Description**: A command-line todo application for task management
- **Goals**: Help users track their daily tasks efficiently

## 2. User Stories
- As a user, I want to add new todo items so that I can remember tasks
- As a user, I want to list all todos so that I can see what needs to be done
- As a user, I want to mark todos as complete so that I can track progress
- As a user, I want to delete todos so that I can remove completed tasks

## 3. Functional Requirements
### 3.1 Core Features
- **Add Todo**: Add new todo items with descriptions
  - Acceptance Criteria: Todo is saved and appears in list
- **List Todos**: Display all todo items
  - Acceptance Criteria: All todos shown with status
- **Complete Todo**: Mark todo as done
  - Acceptance Criteria: Todo status changes to complete
- **Delete Todo**: Remove a todo item
  - Acceptance Criteria: Todo is removed from storage

## 4. Non-Functional Requirements
- **Performance**: Commands should execute within 100ms
- **Reliability**: Data should persist between sessions
- **Usability**: Simple, intuitive CLI interface

## 5. Data Requirements
- **Data Models**: Todo (id, title, completed, created_at)
- **Data Storage**: JSON file storage

## 6. Success Metrics
- Successfully add, list, complete, and delete todos
- Data persists across application restarts
"""


@pytest.fixture
def sample_design():
    """Sample design document for testing."""
    return """
# Technical Design Document: Simple Todo CLI

## 1. Architecture Overview
- **Architecture Pattern**: Command Pattern
- **Technology Stack**:
  - Language: Python 3.10+
  - Framework: argparse for CLI
  - Storage: JSON file
  - Dependencies: No external dependencies required

## 2. System Design
### 2.1 Components
- **CLI Parser**: Handles command-line argument parsing
- **TodoManager**: Manages todo operations
- **Storage**: Handles file I/O operations

### 2.2 Data Models
```python
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Todo:
    id: str
    title: str
    completed: bool
    created_at: datetime
```

### 2.3 API/Interface Design
- `add_todo(title: str) -> Todo`
- `list_todos() -> List[Todo]`
- `complete_todo(todo_id: str) -> bool`
- `delete_todo(todo_id: str) -> bool`

## 3. File Structure
```
todo_app/
├── todo.py          # Main entry point
├── manager.py       # TodoManager class
├── storage.py       # Storage operations
├── models.py        # Todo dataclass
├── todos.json       # Data storage
└── README.md        # Usage instructions
```

## 4. Implementation Approach
- **Phase 1**: Implement data models and storage
- **Phase 2**: Create TodoManager with CRUD operations
- **Phase 3**: Build CLI interface with argparse
- **Phase 4**: Add error handling and validation

## 5. Testing Strategy
- **Unit Tests**: Test each component independently
- **Integration Tests**: Test CLI commands end-to-end
- **Manual Testing**: Verify user workflows

## 6. Considerations
- **Performance**: JSON parsing is fast enough for this scale
- **Security**: No security concerns for local CLI app
- **Scalability**: Design allows easy migration to database
- **Maintainability**: Clear separation of concerns

## 7. Tasks
```json
[
  {
    "id": "task_001",
    "title": "Create data models",
    "description": "Implement Todo dataclass with required fields",
    "dependencies": [],
    "status": "pending",
    "priority": 10
  },
  {
    "id": "task_002",
    "title": "Implement storage layer",
    "description": "Create JSON file storage operations",
    "dependencies": ["task_001"],
    "status": "pending",
    "priority": 9
  },
  {
    "id": "task_003",
    "title": "Create TodoManager",
    "description": "Implement business logic for CRUD operations",
    "dependencies": ["task_002"],
    "status": "pending",
    "priority": 8
  },
  {
    "id": "task_004",
    "title": "Build CLI interface",
    "description": "Create argparse CLI with add/list/complete/delete commands",
    "dependencies": ["task_003"],
    "status": "pending",
    "priority": 7
  },
  {
    "id": "task_005",
    "title": "Add error handling",
    "description": "Implement proper error handling and validation",
    "dependencies": ["task_004"],
    "status": "pending",
    "priority": 6
  },
  {
    "id": "task_006",
    "title": "Write README",
    "description": "Create documentation with usage examples",
    "dependencies": ["task_005"],
    "status": "pending",
    "priority": 5
  }
]
```
"""


@pytest.fixture
def sample_tasks():
    """Sample task list for testing."""
    return [
        {
            "id": "task_001",
            "title": "Create data models",
            "description": "Implement Todo dataclass",
            "dependencies": [],
            "status": "pending",
            "priority": 10
        },
        {
            "id": "task_002",
            "title": "Implement storage",
            "description": "Create JSON storage",
            "dependencies": ["task_001"],
            "status": "pending",
            "priority": 9
        },
        {
            "id": "task_003",
            "title": "Create manager",
            "description": "Implement TodoManager",
            "dependencies": ["task_002"],
            "status": "pending",
            "priority": 8
        }
    ]
