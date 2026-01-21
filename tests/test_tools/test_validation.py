"""Unit tests for validation functions."""

import pytest

from src.tools.validation import (
    validate_prd,
    validate_design,
    validate_tasks,
    validate_tasks_json,
    validate_coding_output,
    validate_requirement,
    OutputValidator,
    ValidationError,
)


class TestValidation:
    """Test validation functions."""

    def test_validate_prd_valid(self):
        """Test validating a valid PRD."""
        prd = """
# Product Requirements Document

## Overview
This is a comprehensive test project demonstrating the PRD validation requirements.
The project aims to deliver a complete solution with clear requirements and success criteria.

## User Stories
As a user, I want to login so that I can access my account and use the application features.
As an administrator, I want to manage users so that I can maintain system security.
As a user, I want to view my dashboard so that I can track my progress and activities.

## Functional Requirements
### Core Features
- Login feature
  - Acceptance Criteria: Users can login with email and password securely
  - Description: Implement authentication with proper session management
- Dashboard feature
  - Acceptance Criteria: Users see personalized content after login
  - Description: Display relevant information and quick actions
- User management
  - Acceptance Criteria: Admins can create, update, and delete users
  - Description: Provide CRUD operations for user accounts

### Secondary Features
- Profile management
  - Acceptance Criteria: Users can update their profile information
- Password reset
  - Acceptance Criteria: Users can recover access to their accounts

## Non-Functional Requirements
- Performance: Response time under 200ms for API calls
- Security: All data transmission must be encrypted
- Reliability: System uptime should be 99.9%
- Scalability: Support up to 10,000 concurrent users

## Success Metrics
- 1000 active users within first month
- 99% user satisfaction rate
- Average session duration greater than 5 minutes
"""
        is_valid, errors = validate_prd(prd)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_prd_missing_sections(self):
        """Test validating PRD with missing sections."""
        prd = "# Title\n\nSome content."
        is_valid, errors = validate_prd(prd)
        assert is_valid is False
        assert len(errors) > 0
        assert any("overview" in e.lower() for e in errors)

    def test_validate_design_valid(self):
        """Test validating a valid design document."""
        design = """
# Technical Design Document

## Architecture Overview
- **Architecture Pattern**: MVC (Model-View-Controller)
- **Technology Stack**:
  - Language: Python 3.10+
  - Framework: Flask
  - Database: SQLite
  - Testing: pytest

## System Design
### Components
- **API Server**: Handles HTTP requests and responses
- **Business Logic**: Implements core application functionality
- **Data Layer**: Manages database operations and data persistence

### Data Models
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    # User entity representing application users
    id: int
    name: str
    email: str
    created_at: Optional[str] = None
```

## File Structure
```
project/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   └── services.py
├── tests/
│   ├── __init__.py
│   └── test_app.py
├── requirements.txt
└── README.md
```

## Implementation Approach
We will use Flask for the web framework with a modular structure.
The application will follow the MVC pattern with clear separation of concerns.
Development will proceed in phases: data layer, business logic, API layer, and testing.

## Testing Strategy
Unit tests for all components using pytest with coverage reporting.
Integration tests for API endpoints to verify correct request/response handling.
End-to-end tests for critical user workflows to ensure system reliability.
This comprehensive testing approach ensures high code quality and system stability.
"""
        is_valid, errors = validate_design(design)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_tasks_valid(self):
        """Test validating valid tasks."""
        tasks = [
            {
                "id": "task_001",
                "title": "Create database schema",
                "description": "Define the database models",
                "dependencies": [],
                "status": "pending",
                "priority": 10
            },
            {
                "id": "task_002",
                "title": "Implement API",
                "description": "Create REST API endpoints",
                "dependencies": ["task_001"],
                "status": "pending",
                "priority": 9
            }
        ]
        is_valid, errors = validate_tasks(tasks)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_tasks_missing_fields(self):
        """Test validating tasks with missing required fields."""
        tasks = [
            {
                "id": "task_001",
                # Missing title
                "description": "Test task"
            }
        ]
        is_valid, errors = validate_tasks(tasks)
        assert is_valid is False
        assert any("title" in e.lower() for e in errors)

    def test_validate_tasks_duplicate_ids(self):
        """Test validating tasks with duplicate IDs."""
        tasks = [
            {"id": "task_001", "title": "Task 1", "status": "pending"},
            {"id": "task_001", "title": "Task 2", "status": "pending"}
        ]
        is_valid, errors = validate_tasks(tasks)
        assert is_valid is False
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_tasks_json_valid(self):
        """Test validating tasks JSON string."""
        tasks_json = """[
            {
                "id": "task_001",
                "title": "Task 1",
                "description": "First task",
                "dependencies": [],
                "status": "pending",
                "priority": 10
            }
        ]"""
        is_valid, errors, tasks = validate_tasks_json(tasks_json)
        assert is_valid is True
        assert tasks is not None
        assert len(tasks) == 1

    def test_validate_tasks_json_invalid_json(self):
        """Test validating invalid JSON."""
        tasks_json = "{ invalid json }"
        is_valid, errors, tasks = validate_tasks_json(tasks_json)
        assert is_valid is False
        assert tasks is None

    def test_validate_coding_output_success(self):
        """Test validating successful coding output."""
        output = "Created file: main.py\nImplementation complete."
        is_success, message = validate_coding_output(output)
        assert is_success is True

    def test_validate_coding_output_failure(self):
        """Test validating failed coding output."""
        output = "Error: Failed to create file"
        is_success, message = validate_coding_output(output)
        assert is_success is False

    def test_validate_requirement_valid(self):
        """Test validating a valid requirement."""
        requirement = "Build a todo app with add, list, and delete features"
        is_valid, errors = validate_requirement(requirement)
        assert is_valid is True

    def test_validate_requirement_too_short(self):
        """Test validating a requirement that's too short."""
        requirement = "Hi"
        is_valid, errors = validate_requirement(requirement)
        assert is_valid is False

    def test_output_validator_prd(self):
        """Test OutputValidator for PRD."""
        validator = OutputValidator()
        prd = """
# Product Requirements Document

## Overview
Project for implementing comprehensive features with proper documentation and validation.

## User Stories
As a user, I want features so that I can benefit from the system functionality.
As an administrator, I want management capabilities to maintain the system effectively.

## Functional Requirements
### Core Features
- Feature 1
  - Acceptance Criteria: Criteria defined clearly with measurable outcomes
- Feature 2
  - Acceptance Criteria: Second feature with validation requirements

### Secondary Features
- Additional features to extend system capabilities
  - Acceptance Criteria: Proper testing and validation completed

## Non-Functional Requirements
- Performance: Fast response times under 100ms
- Security: Data protection with encryption and access controls
- Reliability: System uptime of 99.9% or higher
- Scalability: Support for growing user base

## Success Metrics
- 1000 users engaged within first month
- User satisfaction score above 90%
- System performance meets all defined benchmarks
Additional content to ensure minimum length requirements are satisfied for PRD validation.
This comprehensive document provides clear guidance for implementation and testing phases.
"""

        # Should not raise
        validator.validate_prd_output(prd)

    def test_output_validator_prd_invalid(self):
        """Test OutputValidator with invalid PRD."""
        validator = OutputValidator()
        prd = "Too short"

        with pytest.raises(ValidationError):
            validator.validate_prd_output(prd)

    def test_output_validator_design(self):
        """Test OutputValidator for design."""
        validator = OutputValidator()
        design = """
# Technical Design Document

## Architecture Overview
- **Technology Stack**:
  - Language: Python 3.10+
  - Framework: Flask
  - Database: SQLite

## System Design
### Components
- API Server: Handles requests
- Business Logic: Implements functionality
- Data Layer: Manages persistence

### Data Models
```python
from dataclasses import dataclass

@dataclass
class Model:
    id: int
    name: str
```

## File Structure
```
app/
├── models.py
├── routes.py
└── services.py
```

## Implementation Approach
Development approach with iterative phases.
Phase 1: Setup project structure
Phase 2: Implement data models
Phase 3: Build API endpoints
Phase 4: Add testing

This comprehensive design document provides detailed technical specifications for the system.
We have carefully considered all aspects of the architecture to ensure scalability and maintainability.
The chosen technology stack balances performance, development speed, and operational requirements.
Additional content to meet validation requirements while providing valuable technical guidance.
The system will be built using industry best practices and proven architectural patterns.
"""

        # Should not raise
        validator.validate_design_output(design)

    def test_output_validator_tasks(self):
        """Test OutputValidator for tasks."""
        validator = OutputValidator()
        tasks = [
            {
                "id": "task_001",
                "title": "Task",
                "description": "Description",
                "status": "pending"
            }
        ]

        # Should not raise
        validator.validate_tasks_output(tasks)
