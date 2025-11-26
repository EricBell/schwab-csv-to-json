"""
Tests for TUI functionality, focusing on starting_dir parameter handling.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from tui import FileSelectionScreen, SchwabTUI, normalize_starting_dir
from dataclasses import dataclass


@dataclass
class AppState:
    """Mock AppState for testing."""
    output_path: str = "output.ndjson"


class TestStartingDirParameter:
    """Tests for starting_dir parameter handling."""

    def test_file_selection_screen_accepts_starting_dir(self):
        """FileSelectionScreen should accept starting_dir parameter."""
        app_state = AppState()
        screen = FileSelectionScreen(app_state, starting_dir="/tmp")
        assert screen.starting_dir == "/tmp"

    def test_file_selection_screen_defaults_to_current_dir(self):
        """FileSelectionScreen should default to current directory."""
        app_state = AppState()
        screen = FileSelectionScreen(app_state)
        assert screen.starting_dir == "."

    def test_schwab_tui_stores_starting_dir(self):
        """SchwabTUI should store the starting_dir parameter."""
        tui = SchwabTUI(starting_dir="/tmp")
        assert tui.starting_dir == "/tmp"

    def test_schwab_tui_defaults_starting_dir(self):
        """SchwabTUI should default starting_dir to current directory (normalized to absolute)."""
        tui = SchwabTUI()
        # Should be normalized to absolute path of current directory
        assert Path(tui.starting_dir).is_absolute()
        assert Path(tui.starting_dir).exists()


class TestPathNormalization:
    """Tests for path normalization and validation."""

    def test_normalize_absolute_path(self, tmp_path):
        """Absolute paths should be validated and returned if valid."""
        result = normalize_starting_dir(str(tmp_path))
        assert result == str(tmp_path)

    def test_normalize_relative_path(self, tmp_path, monkeypatch):
        """Relative paths should be resolved to absolute paths."""
        # Create a subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Change to parent directory
        monkeypatch.chdir(tmp_path)

        result = normalize_starting_dir("subdir")
        assert Path(result).is_absolute()
        assert Path(result).exists()

    def test_normalize_home_expansion(self, tmp_path, monkeypatch):
        """Tilde (~) should be expanded to user home directory."""
        # Create a test directory in the actual home
        home = Path.home()
        test_dir = home / "test_schwab_tui_temp"
        test_dir.mkdir(exist_ok=True)

        try:
            result = normalize_starting_dir("~/test_schwab_tui_temp")
            # Should expand ~ and return the absolute path
            assert result == str(test_dir)
            assert Path(result).is_absolute()
        finally:
            # Clean up
            if test_dir.exists():
                test_dir.rmdir()

    def test_normalize_nonexistent_path_returns_current_dir(self):
        """Non-existent paths should fall back to current directory."""
        result = normalize_starting_dir("/this/path/does/not/exist/at/all")
        assert result == "."

    def test_normalize_file_instead_of_directory_returns_current_dir(self, tmp_path):
        """If path is a file (not directory), should fall back to current directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = normalize_starting_dir(str(test_file))
        assert result == "."

    def test_normalize_empty_string_returns_current_dir(self):
        """Empty string should return current directory."""
        result = normalize_starting_dir("")
        assert result == "."

    def test_normalize_none_returns_current_dir(self):
        """None should return current directory."""
        result = normalize_starting_dir(None)
        assert result == "."


class TestWSLPaths:
    """Tests for WSL-specific path handling."""

    def test_wsl_mnt_c_path_passthrough(self):
        """WSL /mnt/c/ paths should be passed through if they exist."""
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('pathlib.Path.is_dir') as mock_isdir:
            mock_exists.return_value = True
            mock_isdir.return_value = True

            result = normalize_starting_dir("/mnt/c/Users/TestUser/Documents")
            assert result == "/mnt/c/Users/TestUser/Documents"

    def test_wsl_mnt_c_nonexistent_falls_back(self):
        """Non-existent WSL paths should fall back to current directory."""
        result = normalize_starting_dir("/mnt/c/NonExistent/Path")
        assert result == "."
