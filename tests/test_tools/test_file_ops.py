"""Unit tests for file operations."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.tools.file_ops import (
    read_file,
    write_file,
    append_file,
    file_exists,
    parse_markdown_sections,
    parse_tasks_json,
    write_tasks_json,
    get_task_by_id,
    get_ready_tasks,
)


class TestFileOperations:
    """Test file operation functions."""

    def test_write_and_read_file(self):
        """Test writing and reading a file."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            content = "Hello, World!"

            write_file(file_path, content)
            assert file_path.exists()

            read_content = read_file(file_path)
            assert read_content == content

    def test_read_file_not_found(self):
        """Test reading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            read_file("/nonexistent/file.txt")

    def test_append_file(self):
        """Test appending to a file."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            write_file(file_path, "Line 1\n")
            append_file(file_path, "Line 2\n")

            content = read_file(file_path)
            assert content == "Line 1\nLine 2\n"

    def test_file_exists(self):
        """Test file existence check."""
        with TemporaryDirectory() as tmpdir:
            existing_file = Path(tmpdir) / "exists.txt"
            non_existent = Path(tmpdir) / "does_not_exist.txt"

            write_file(existing_file, "content")

            assert file_exists(existing_file) is True
            assert file_exists(non_existent) is False

    def test_parse_markdown_sections(self):
        """Test parsing markdown into sections."""
        markdown = """
# Introduction

This is the intro.

## Overview

Here is the overview.

## Details

More details here.
"""
        sections = parse_markdown_sections(markdown)

        assert "introduction" in sections
        assert "overview" in sections
        assert "details" in sections

    def test_parse_tasks_json(self):
        """Test parsing tasks.json file."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "tasks.json"
            tasks = [
                {
                    "id": "task_001",
                    "title": "Task 1",
                    "description": "First task",
                    "status": "pending",
                    "dependencies": []
                },
                {
                    "id": "task_002",
                    "title": "Task 2",
                    "description": "Second task",
                    "status": "pending",
                    "dependencies": ["task_001"]
                }
            ]

            write_tasks_json(file_path, tasks)
            parsed_tasks = parse_tasks_json(file_path)

            assert len(parsed_tasks) == 2
            assert parsed_tasks[0]["id"] == "task_001"
            assert parsed_tasks[1]["dependencies"] == ["task_001"]

    def test_get_task_by_id(self):
        """Test finding a task by ID."""
        tasks = [
            {"id": "task_001", "title": "Task 1"},
            {"id": "task_002", "title": "Task 2"}
        ]

        task = get_task_by_id(tasks, "task_001")
        assert task is not None
        assert task["title"] == "Task 1"

        task = get_task_by_id(tasks, "task_999")
        assert task is None

    def test_get_ready_tasks(self):
        """Test getting tasks that are ready to execute."""
        tasks = [
            {
                "id": "task_001",
                "title": "Task 1",
                "status": "pending",
                "dependencies": []
            },
            {
                "id": "task_002",
                "title": "Task 2",
                "status": "pending",
                "dependencies": ["task_001"]
            },
            {
                "id": "task_003",
                "title": "Task 3",
                "status": "pending",
                "dependencies": ["task_002"]
            }
        ]

        # No tasks completed
        ready = get_ready_tasks(tasks, [])
        assert len(ready) == 1
        assert ready[0]["id"] == "task_001"

        # task_001 completed
        ready = get_ready_tasks(tasks, ["task_001"])
        assert len(ready) == 1
        assert ready[0]["id"] == "task_002"

        # task_001 and task_002 completed
        ready = get_ready_tasks(tasks, ["task_001", "task_002"])
        assert len(ready) == 1
        assert ready[0]["id"] == "task_003"
