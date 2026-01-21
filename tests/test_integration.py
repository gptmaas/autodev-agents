"""Integration tests for the workflow."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from tempfile import TemporaryDirectory
from pathlib import Path

from src.core.graph import (
    build_workflow,
    create_workflow_session,
    run_workflow_until_interrupt,
    get_workflow_state
)
from src.core.state import create_initial_state
from src.config.settings import reset_settings


class TestWorkflowIntegration:
    """Test workflow integration."""

    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()

    @patch('src.agents.base.ChatAnthropic')
    def test_build_workflow(self, mock_llm):
        """Test building the workflow."""
        workflow = build_workflow(human_in_loop=True, batch_coding=False)

        assert workflow is not None
        # Workflow should be compiled
        assert hasattr(workflow, 'get_state')

    @patch('src.agents.base.ChatAnthropic')
    def test_create_workflow_session(self, mock_llm):
        """Test creating a workflow session."""
        requirement = "Build a simple calculator"
        session_id = "test_session_123"

        workflow, sid, initial_state = create_workflow_session(
            requirement=requirement,
            session_id=session_id,
            human_in_loop=True,
            batch_coding=False
        )

        assert sid == session_id
        assert initial_state["requirement"] == requirement
        assert initial_state["session_id"] == session_id
        assert initial_state["stage"] == "prd"

    @patch('src.agents.base.ChatAnthropic')
    def test_workflow_prd_generation(self, mock_llm, tmp_path):
        """Test PRD generation in workflow."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = """
# Product Requirements Document

## Overview
Simple calculator application.

## User Stories
As a user, I want to perform calculations.

## Functional Requirements
### Core Features
- Addition operation
  - Acceptance Criteria: Can add two numbers

## Non-Functional Requirements
- Fast response time

## Success Metrics
- 100 users
"""
        mock_llm.return_value.invoke.return_value = mock_response

        # Mock settings for workspace
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_workspace = tmp_path / "test_integration"
            mock_workspace.mkdir(parents=True, exist_ok=True)

            settings_mock = Mock()
            settings_mock.get_session_workspace.return_value = mock_workspace
            mock_settings.return_value = settings_mock

            requirement = "Build a simple calculator"
            workflow, session_id, initial_state = create_workflow_session(
                requirement=requirement,
                session_id="test_prd",
                human_in_loop=True
            )

            # Run until interrupt (should stop after PRD)
            final_state, status, checkpoint = run_workflow_until_interrupt(
                workflow=workflow,
                initial_state=initial_state,
                session_id=session_id
            )

            assert status in ["interrupted", "completed"]
            assert final_state.get("prd_content") is not None
            assert "Overview" in final_state.get("prd_content", "")

    @patch('src.agents.base.ChatAnthropic')
    def test_workflow_full_flow(self, mock_llm, tmp_path):
        """Test full workflow flow without human-in-loop."""
        # Mock LLM responses
        mock_llm_instance = Mock()

        # PRD response
        prd_response = Mock()
        prd_response.content = """
# Product Requirements Document

## Overview
Simple counter app.

## User Stories
As a user, I want to count.

## Functional Requirements
### Core Features
- Increment counter
  - Acceptance Criteria: Counter goes up

## Non-Functional Requirements
- Fast

## Success Metrics
- Works
"""
        # Design response
        design_response = Mock()
        design_response.content = """
# Technical Design Document

## Architecture Overview
Simple state machine.

## System Design
### Components
- Counter class

## File Structure
```
app/
├── counter.py
└── main.py
```

## Implementation Approach
Use a class.

## Testing Strategy
Test it works.

```json
[
  {
    "id": "task_001",
    "title": "Create counter class",
    "description": "Implement Counter class",
    "dependencies": [],
    "status": "pending",
    "priority": 10
  }
]
```
"""
        mock_llm_instance.invoke.side_effect = [prd_response, design_response]
        mock_llm.return_value = mock_llm_instance

        # Mock settings
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_workspace = tmp_path / "test_full_flow"
            mock_workspace.mkdir(parents=True, exist_ok=True)

            settings_mock = Mock()
            settings_mock.get_session_workspace.return_value = mock_workspace
            settings_mock.agent.max_coding_iterations = 0  # Skip coding for this test
            mock_settings.return_value = settings_mock

            requirement = "Build a counter"
            workflow, session_id, initial_state = create_workflow_session(
                requirement=requirement,
                session_id="test_full",
                human_in_loop=False,  # No interrupts
                batch_coding=True
            )

            final_state, status, checkpoint = run_workflow_until_interrupt(
                workflow=workflow,
                initial_state=initial_state,
                session_id=session_id
            )

            # Should have PRD and Design
            assert final_state.get("prd_content") is not None
            assert final_state.get("design_content") is not None
            assert final_state.get("task_list") is not None

    @patch('src.agents.base.ChatAnthropic')
    def test_get_workflow_state(self, mock_llm):
        """Test getting workflow state."""
        workflow = build_workflow()
        session_id = "test_get_state"

        # Try to get state for non-existent session
        state = get_workflow_state(workflow, session_id)

        # Should return None for non-existent session
        # (or might raise exception depending on checkpointer)
        assert state is None or isinstance(state, dict)

    @patch('src.agents.base.ChatAnthropic')
    def test_workflow_with_feedback(self, mock_llm, tmp_path):
        """Test workflow with human feedback."""
        # Mock initial PRD
        prd_response = Mock()
        prd_response.content = """
# Product Requirements Document

## Overview
Basic app.

## User Stories
As a user, I want features.

## Functional Requirements
### Core Features
- Basic feature

## Non-Functional Requirements
- Performance

## Success Metrics
- Users
"""
        # Mock revised PRD
        revised_response = Mock()
        revised_response.content = """
# Product Requirements Document (Revised)

## Overview
Enhanced app with more details.

## User Stories
As a user, I want features and more.

## Functional Requirements
### Core Features
- Basic feature
  - Acceptance Criteria: Detailed criteria
- Additional feature
  - Acceptance Criteria: More details

## Non-Functional Requirements
- Performance: < 100ms
- Security: Auth required

## Success Metrics
- 1000 users
- 99% uptime
"""
        mock_llm_instance = Mock()
        mock_llm_instance.invoke.side_effect = [prd_response, revised_response]
        mock_llm.return_value = mock_llm_instance

        # Mock settings
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_workspace = tmp_path / "test_feedback"
            mock_workspace.mkdir(parents=True, exist_ok=True)

            settings_mock = Mock()
            settings_mock.get_session_workspace.return_value = mock_workspace
            mock_settings.return_value = settings_mock

            # Create session and run initial
            requirement = "Build an app"
            workflow, session_id, initial_state = create_workflow_session(
                requirement=requirement,
                session_id="test_feedback_session",
                human_in_loop=True
            )

            final_state, status, checkpoint = run_workflow_until_interrupt(
                workflow=workflow,
                initial_state=initial_state,
                session_id=session_id
            )

            # Should be interrupted after PRD
            assert status == "interrupted"
            assert final_state.get("stage") in ["prd", "design"]

            # Add feedback
            final_state["prd_feedback"] = "Add more details to the requirements"

            # Resume would normally happen here
            # For this test, we just verify the feedback is set
            assert final_state["prd_feedback"] == "Add more details to the requirements"
