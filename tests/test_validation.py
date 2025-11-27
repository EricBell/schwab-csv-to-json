#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for file path validation and safety checks."""

import pytest
from pathlib import Path
import tempfile
import os


def test_normalize_path_converts_to_absolute(tmp_path):
    """Test that normalize_path converts relative paths to absolute."""
    from main import normalize_path

    # Change to tmp_path directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Create a test file
        test_file = tmp_path / "test.csv"
        test_file.touch()

        # Test relative path conversion
        result = normalize_path("test.csv")
        assert result.is_absolute()
        assert result == test_file
    finally:
        os.chdir(original_cwd)


def test_normalize_path_resolves_symlinks(tmp_path):
    """Test that normalize_path resolves symbolic links."""
    from main import normalize_path

    # Create a real file and a symlink to it
    real_file = tmp_path / "real.csv"
    real_file.touch()

    symlink = tmp_path / "link.csv"
    symlink.symlink_to(real_file)

    # Both should resolve to the same path
    result_real = normalize_path(str(real_file))
    result_link = normalize_path(str(symlink))

    assert result_real == result_link


def test_validate_output_not_input_detects_collision(tmp_path):
    """Test that validate_output_not_input detects when output would overwrite input."""
    from main import validate_output_not_input

    input1 = tmp_path / "file1.csv"
    input2 = tmp_path / "file2.csv"
    input3 = tmp_path / "file3.csv"

    input_paths = [str(input1), str(input2), str(input3)]
    output_path = str(input3)  # Output same as last input

    error = validate_output_not_input(input_paths, output_path)

    assert error is not None
    assert "overwrite" in error.lower()
    assert "file3.csv" in error


def test_validate_output_not_input_allows_different_file(tmp_path):
    """Test that validate_output_not_input allows output to different file."""
    from main import validate_output_not_input

    input1 = tmp_path / "file1.csv"
    input2 = tmp_path / "file2.csv"
    output = tmp_path / "output.ndjson"

    input_paths = [str(input1), str(input2)]
    output_path = str(output)

    error = validate_output_not_input(input_paths, output_path)

    assert error is None


def test_validate_output_not_input_handles_relative_paths(tmp_path):
    """Test that validation works with relative paths."""
    from main import validate_output_not_input

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Create test files
        (tmp_path / "file1.csv").touch()
        (tmp_path / "file2.csv").touch()

        input_paths = ["file1.csv", "./file2.csv"]
        output_path = "file2.csv"  # Same as second input, different format

        error = validate_output_not_input(input_paths, output_path)

        assert error is not None
    finally:
        os.chdir(original_cwd)


def test_validate_csv_extension_warns_for_csv_output():
    """Test that validate_csv_extension_warning warns for .csv output."""
    from main import validate_csv_extension_warning

    warning = validate_csv_extension_warning("output.csv")

    assert warning is not None
    assert ".csv" in warning


def test_validate_csv_extension_allows_other_extensions():
    """Test that validate_csv_extension_warning allows other extensions."""
    from main import validate_csv_extension_warning

    assert validate_csv_extension_warning("output.ndjson") is None
    assert validate_csv_extension_warning("output.json") is None
    assert validate_csv_extension_warning("output.txt") is None


def test_validate_input_files_exist_detects_missing(tmp_path):
    """Test that validate_input_files_exist detects missing files."""
    from main import validate_input_files_exist

    existing = tmp_path / "exists.csv"
    existing.touch()

    missing1 = tmp_path / "missing1.csv"
    missing2 = tmp_path / "missing2.csv"

    input_paths = [str(existing), str(missing1), str(missing2)]

    errors = validate_input_files_exist(input_paths)

    assert len(errors) == 2
    assert any("missing1.csv" in err for err in errors)
    assert any("missing2.csv" in err for err in errors)


def test_validate_input_files_exist_passes_when_all_exist(tmp_path):
    """Test that validate_input_files_exist passes when all files exist."""
    from main import validate_input_files_exist

    file1 = tmp_path / "file1.csv"
    file2 = tmp_path / "file2.csv"
    file1.touch()
    file2.touch()

    input_paths = [str(file1), str(file2)]

    errors = validate_input_files_exist(input_paths)

    assert len(errors) == 0


def test_validate_output_directory_detects_nonexistent(tmp_path):
    """Test that validate_output_directory detects non-existent directory."""
    from main import validate_output_directory

    output_path = str(tmp_path / "nonexistent" / "output.ndjson")

    error = validate_output_directory(output_path)

    assert error is not None
    assert "directory" in error.lower()


def test_validate_output_directory_allows_existing(tmp_path):
    """Test that validate_output_directory allows existing directory."""
    from main import validate_output_directory

    output_path = str(tmp_path / "output.ndjson")

    error = validate_output_directory(output_path)

    assert error is None


def test_validate_output_directory_allows_current_directory(tmp_path):
    """Test that validate_output_directory allows output in current directory."""
    from main import validate_output_directory

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        error = validate_output_directory("output.ndjson")

        assert error is None
    finally:
        os.chdir(original_cwd)


def test_validate_file_paths_integration_all_checks(tmp_path):
    """Integration test for all validation checks together."""
    from main import validate_file_paths

    # Create test files
    input1 = tmp_path / "file1.csv"
    input2 = tmp_path / "file2.csv"
    input1.touch()
    input2.touch()

    # Valid case - should pass
    errors = validate_file_paths(
        [str(input1), str(input2)],
        str(tmp_path / "output.ndjson"),
        force_overwrite=False
    )
    assert len(errors) == 0

    # Invalid case - output overwrites input
    errors = validate_file_paths(
        [str(input1), str(input2)],
        str(input2),
        force_overwrite=False
    )
    assert len(errors) > 0
    assert any("overwrite" in err.lower() for err in errors)


def test_validate_file_paths_with_force_overwrite(tmp_path):
    """Test that force_overwrite bypasses output collision check."""
    from main import validate_file_paths

    input1 = tmp_path / "file1.csv"
    input1.touch()

    # With force_overwrite, output collision should be ignored
    errors = validate_file_paths(
        [str(input1)],
        str(input1),
        force_overwrite=True
    )

    # Should not have overwrite error, but may have CSV extension warning
    assert not any("overwrite" in err.lower() and "error" in err.lower() for err in errors)


def test_validate_file_paths_missing_input_files(tmp_path):
    """Test that missing input files are detected."""
    from main import validate_file_paths

    missing = tmp_path / "missing.csv"

    errors = validate_file_paths(
        [str(missing)],
        str(tmp_path / "output.ndjson"),
        force_overwrite=False
    )

    assert len(errors) > 0
    assert any("not found" in err.lower() or "does not exist" in err.lower() for err in errors)


def test_validate_file_paths_csv_extension_warning(tmp_path):
    """Test that CSV extension generates a warning."""
    from main import validate_file_paths

    input1 = tmp_path / "file1.csv"
    input1.touch()

    errors = validate_file_paths(
        [str(input1)],
        str(tmp_path / "output.csv"),
        force_overwrite=False
    )

    # Should have at least a warning about .csv extension
    assert len(errors) > 0
    assert any(".csv" in err for err in errors)
