"""Unit tests for PM Agent."""

import pytest
from unittest.mock import Mock, patch

from src.agents.pm_agent import PMAgent, pm_agent_node
from src.core.state import create_initial_state


class TestPMAgent:
    """Test PM Agent functionality."""

    def test_init(self):
        """Test PM agent initialization."""
        agent = PMAgent()
        assert agent.name == "PM_Agent"
        assert agent.system_prompt is not None

    def test_get_default_system_prompt(self):
        """Test getting default system prompt."""
        agent = PMAgent()
        prompt = agent._get_default_system_prompt()
        assert "Product Manager" in prompt
        assert "PRD" in prompt

    @patch('src.agents.base.ChatAnthropic')
    def test_build_prompt_initial(self, mock_llm):
        """Test building prompt for initial PRD generation."""
        agent = PMAgent()
        state = create_initial_state(
            requirement="Build a todo app",
            session_id="test_session"
        )

        prompt = agent._build_prompt(state)

        assert "Build a todo app" in prompt
        assert "Product Requirements Document" in prompt

    @patch('src.agents.base.ChatAnthropic')
    def test_build_prompt_with_feedback(self, mock_llm):
        """Test building prompt for PRD revision."""
        agent = PMAgent()
        state = create_initial_state(
            requirement="Build a todo app",
            session_id="test_session"
        )
        state["prd_content"] = "# Old PRD"
        state["prd_iteration"] = 1
        state["prd_feedback"] = "Add more details"

        prompt = agent._build_prompt(state)

        assert "Add more details" in prompt
        assert "Old PRD" in prompt

    @patch('src.agents.base.ChatAnthropic')
    def test_parse_response(self, mock_llm, tmp_path):
        """Test parsing LLM response."""
        agent = PMAgent()
        state = create_initial_state(
            requirement="Build a todo app",
            session_id="test_session"
        )

        response = """
# Product Requirements Document

## Overview
This is a test PRD.

## User Stories
As a user, I want to manage todos.

## Functional Requirements
### Core Features
- Add todo items
  - Acceptance Criteria: Users can add todos

## Non-Functional Requirements
- Performance: Fast response times

## Success Metrics
- 1000 users
"""

        # Mock workspace path
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_workspace = tmp_path / "test_session"
            mock_workspace.mkdir(parents=True, exist_ok=True)

            mock_settings.return_value.get_session_workspace.return_value = mock_workspace

            updates = agent._parse_response(response, state)

            assert "prd_content" in updates
            assert "prd_file_path" in updates
            assert updates["prd_iteration"] == 1
            assert "Overview" in updates["prd_content"]

    def test_pm_agent_node(self):
        """Test PM agent node function."""
        state = create_initial_state(
            requirement="Build a simple calculator",
            session_id="test_node"
        )

        with patch('src.agents.pm_agent.PMAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.execute.return_value = {
                "prd_content": "# PRD",
                "prd_file_path": "/path/to/PRD.md"
            }
            mock_agent_class.return_value = mock_agent

            result = pm_agent_node(state)

            mock_agent.execute.assert_called_once()
            assert "prd_content" in result
