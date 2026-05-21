"""
test_logger.py — Unit tests for app/logger.py.

Verifies log file creation, entry format, append behaviour, and that all
four fields (timestamp, user_input, system_output, intent, attempt) appear.
"""

import os
import re
import tempfile
import pytest
from app.logger import log_interaction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def log_file(monkeypatch, tmp_path):
    """Redirect log_interaction to write into a temp file, not project root."""
    path = tmp_path / "test_app.log"
    # Patch open() inside the logger module to use our temp path
    import builtins
    real_open = builtins.open

    def patched_open(file, mode="r", **kwargs):
        if file == "app.log":
            return real_open(str(path), mode, **kwargs)
        return real_open(file, mode, **kwargs)

    monkeypatch.setattr(builtins, "open", patched_open)
    return path


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------

class TestLogInteraction:
    def test_creates_log_file(self, log_file):
        log_interaction(
            user_input="how does slicing work?",
            system_output="Think about the indices.",
            intent="curriculum",
            attempt=1,
        )
        assert log_file.exists()

    def test_log_contains_user_input(self, log_file):
        log_interaction(
            user_input="explain loops",
            system_output="Look at the while loop section.",
            intent="curriculum",
            attempt=1,
        )
        content = log_file.read_text()
        assert "explain loops" in content

    def test_log_contains_system_output(self, log_file):
        log_interaction(
            user_input="q",
            system_output="Look at Week 3.",
            intent="curriculum",
            attempt=1,
        )
        assert "Look at Week 3." in log_file.read_text()

    def test_log_contains_intent(self, log_file):
        log_interaction(
            user_input="q",
            system_output="r",
            intent="answer_seeking",
            attempt=2,
        )
        assert "answer_seeking" in log_file.read_text()

    def test_log_contains_attempt(self, log_file):
        log_interaction(
            user_input="q",
            system_output="r",
            intent="curriculum",
            attempt=3,
        )
        assert "ATTEMPT: 3" in log_file.read_text()

    def test_log_contains_timestamp(self, log_file):
        log_interaction(
            user_input="q",
            system_output="r",
            intent="curriculum",
            attempt=1,
        )
        content = log_file.read_text()
        # Timestamp looks like [2026-05-21 14:32:01]
        assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", content)

    def test_separator_line_present(self, log_file):
        log_interaction(
            user_input="q", system_output="r", intent="curriculum", attempt=1
        )
        assert "-" * 10 in log_file.read_text()


# ---------------------------------------------------------------------------
# Append behaviour
# ---------------------------------------------------------------------------

class TestLogAppend:
    def test_multiple_calls_append_not_overwrite(self, log_file):
        log_interaction("first question", "first reply", "curriculum", 1)
        log_interaction("second question", "second reply", "curriculum", 1)

        content = log_file.read_text()
        assert "first question" in content
        assert "second question" in content

    def test_entry_count_matches_call_count(self, log_file):
        for i in range(5):
            log_interaction(f"question {i}", f"reply {i}", "curriculum", 1)

        content = log_file.read_text()
        assert content.count("USER INPUT:") == 5


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestLogEdgeCases:
    def test_handles_multiline_output(self, log_file):
        multi = "Line one.\nLine two.\nLine three."
        log_interaction("q", multi, "curriculum", 1)
        assert "Line one." in log_file.read_text()
        assert "Line three." in log_file.read_text()

    def test_handles_unicode_input(self, log_file):
        log_interaction("¿cómo funciona?", "I only help with Python.", "off_topic", 1)
        assert "¿cómo funciona?" in log_file.read_text()

    def test_handles_empty_strings(self, log_file):
        log_interaction("", "", "curriculum", 1)
        assert log_file.exists()  # Should not crash
        