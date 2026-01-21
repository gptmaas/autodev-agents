"""Unit tests for helper functions."""

import pytest
from datetime import datetime

from src.utils.helpers import (
    generate_session_id,
    ensure_directory,
    sanitize_filename,
    truncate_text,
    extract_code_blocks,
    parse_list,
    safe_get,
    merge_dicts,
    format_timestamp,
    chunk_list,
)


class TestHelpers:
    """Test helper utility functions."""

    def test_generate_session_id(self):
        """Test session ID generation."""
        session_id = generate_session_id()

        assert isinstance(session_id, str)
        assert len(session_id) > 10
        # Should contain timestamp and random part
        assert "_" in session_id

    def test_ensure_directory(self, tmp_path):
        """Test directory creation."""
        test_dir = tmp_path / "test" / "nested" / "dir"
        result = ensure_directory(test_dir)

        assert result.exists()
        assert result.is_dir()

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Test invalid characters (each is replaced with _)
        assert sanitize_filename("file<>name?.txt") == "file__name_.txt"
        assert sanitize_filename("file/name\\test.txt") == "file_name_test.txt"

        # Test leading/trailing dots and spaces
        assert sanitize_filename("  .test.  ") == "test"

        # Test length limit
        long_name = "a" * 300
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) == 255

    def test_truncate_text(self):
        """Test text truncation."""
        text = "a" * 100

        # No truncation needed
        assert truncate_text(text, 200) == text

        # Truncation needed
        truncated = truncate_text(text, 50)
        assert len(truncated) == 50
        assert truncated.endswith("...")

    def test_extract_code_blocks(self):
        """Test extracting code blocks from markdown."""
        markdown = """
Some text.

```python
def hello():
    print("Hello, World!")
```

More text.

```javascript
function hello() {
    console.log("Hello");
}
```
"""
        blocks = extract_code_blocks(markdown)
        assert len(blocks) == 2
        assert "def hello()" in blocks[0]
        assert "function hello()" in blocks[1]

        # Test language filter
        python_blocks = extract_code_blocks(markdown, language="python")
        assert len(python_blocks) == 1
        assert "def hello()" in python_blocks[0]

    def test_parse_list(self):
        """Test parsing markdown lists."""
        markdown = """
- Item 1
- Item 2
* Item 3
1. Item 4
2. Item 5
"""
        items = parse_list(markdown)
        assert len(items) == 5
        assert "Item 1" in items
        assert "Item 5" in items

    def test_safe_get(self):
        """Test safe dictionary access."""
        data = {
            "level1": {
                "level2": {
                    "value": "found"
                }
            }
        }

        assert safe_get(data, "level1", "level2", "value") == "found"
        assert safe_get(data, "level1", "level2", "missing") is None
        assert safe_get(data, "level1", "missing", "value") is None
        assert safe_get(data, "missing") is None
        assert safe_get(data, "missing", default="default") == "default"

    def test_merge_dicts(self):
        """Test dictionary merging."""
        base = {
            "a": 1,
            "b": {"x": 10, "y": 20}
        }
        update = {
            "b": {"y": 30, "z": 40},
            "c": 3
        }

        result = merge_dicts(base, update)
        assert result["a"] == 1
        assert result["b"]["x"] == 10
        assert result["b"]["y"] == 30
        assert result["b"]["z"] == 40
        assert result["c"] == 3

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        dt = datetime(2024, 1, 15, 12, 30, 45)
        formatted = format_timestamp(dt)

        assert "2024-01-15" in formatted
        assert "12:30:45" in formatted

    def test_chunk_list(self):
        """Test list chunking."""
        items = list(range(10))

        chunks = chunk_list(items, 3)
        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[1] == [3, 4, 5]
        assert chunks[2] == [6, 7, 8]
        assert chunks[3] == [9]

    def test_chunk_list_exact(self):
        """Test chunking with exact division."""
        items = list(range(9))

        chunks = chunk_list(items, 3)
        assert len(chunks) == 3
        assert all(len(chunk) == 3 for chunk in chunks)
