# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python CLI tool with interactive TUI that converts Schwab CSV trade activity reports into flat NDJSON (newline-delimited JSON) or JSON array format. It supports both single-file and multi-file (batch) processing. Schwab CSVs contain multiple logical sections (Filled Orders, Working Orders, Canceled Orders, Rolling Strategies) within a single file, each with its own header row.

### Modes of Operation

1. **TUI Mode** (`main.py tui`): Interactive terminal UI with enhanced file browser (full filesystem navigation), progress tracking, error review, and summary screens
2. **CLI Batch Mode** (`main.py convert file1.csv file2.csv... output.ndjson`): Process multiple files into merged output
3. **CLI Single Mode** (`main.py convert input.csv output.ndjson`): Traditional single-file conversion

## Architecture

### Core Processing Flow

1. **Section Detection**: The CSV is read sequentially, detecting section boundaries using regex patterns that match header rows
2. **Header Mapping**: When a section header is detected, column positions are mapped to canonical field names using `COL_ALIASES`
3. **Row Parsing**: Data rows are parsed using the current section's header mapping to extract fields like `exec_time`, `side`, `qty`, `symbol`, `price`, etc.
4. **Flat Output**: Each row produces a single JSON object with a consistent schema regardless of section, including metadata like `section`, `row_index`, `raw` CSV, and `issues` array

### Section Detection System

Section detection uses two mechanisms:
- **Pattern matching**: Regex patterns in `DEFAULT_SECTION_PATTERNS` (or custom patterns from `--section-patterns-file`)
- **Column alias mapping**: `COL_ALIASES` maps various header names (e.g., "Exec Time", "Execution Time", "Time") to canonical keys (e.g., "exec_time")

The patterns.json file contains actual header signatures extracted from real Schwab CSVs.

### Field Normalization

- **Quantities**: Parsed as signed integers (keeping negative values for sells) unless `--qty-unsigned` is used
- **Prices**: Parsed as floats with $ and comma removal
- **Missing data**: Represented as `null` in JSON output
- **Parse failures**: Tracked in the `issues` array per record

## Running the Tool

```bash
# Launch interactive TUI (recommended for batch processing)
uv run python main.py tui

# Basic single-file conversion
uv run python main.py convert examples/2025-10-24-TradeActivity.csv output.ndjson

# Batch processing multiple files
uv run python main.py convert file1.csv file2.csv file3.csv merged_output.ndjson --verbose

# With options
uv run python main.py convert input.csv output.ndjson --preview 10 --verbose

# Output as JSON array instead of NDJSON
uv run python main.py convert input.csv output.json --output-json --pretty

# Use custom section patterns
uv run python main.py convert input.csv output.ndjson --section-patterns-file patterns.json
```

## Batch Processing Architecture

The `batch.py` module handles multi-file processing:

- **BatchOptions**: Dataclass containing processing configuration (including skip_empty_sections and group_by_section)
- **FileProgress**: Progress information for each file during processing
- **BatchResult**: Aggregated results including file counts, records, validation issues, errors, and sections_skipped count
- **process_multiple_files()**: Main entry point that processes files sequentially with optional progress callbacks
- **process_single_file_for_batch()**: Helper that processes one file and adds source metadata
- **group_and_sort_records()**: Groups records by section and sorts by time (exec_time > time_canceled > time_placed)
- **get_sort_time()**: Extracts the appropriate time field for sorting with priority handling

Each record in batch output includes:
- `source_file`: Basename of the source CSV file
- `source_file_index`: 0-based index in the batch

### New Batch Features (v1.1)

- **Empty Section Filtering**: Sections with only headers (no data rows) are automatically skipped by default
- **Section Grouping**: Records from multiple files are grouped by section name across all files
- **Time-based Sorting**: Within each section, records are sorted chronologically by timestamp
- **Configurable Behavior**: Both features can be disabled with CLI flags (--include-empty-sections, --preserve-file-order)

## TUI Architecture

The `tui.py` module implements a Textual-based terminal UI with 4 screens:

1. **FileSelectionScreen**: Split-view with directory browser (left) and selected files list (right)
   - **Enhanced Directory Navigation**: Navigate up and down the filesystem hierarchy
     - Breadcrumb path display showing current directory
     - Parent directory navigation via BACKSPACE/↑ keys or collapsing root node
     - Full filesystem exploration (not limited to starting directory)
   - Visual selection indicators with checkboxes (☑)
   - Real-time selection counter
   - Clear multi-select instructions
   - Keyboard shortcuts: ENTER to toggle, 'c' to clear all, 's' to start, BACKSPACE/↑ for parent dir
2. **ProcessingScreen**: Progress bars showing real-time processing status
3. **SummaryScreen**: Statistics display with processing time, record counts, validation issues
4. **ErrorReviewScreen**: DataTable showing detailed validation errors

State management uses the `AppState` dataclass to track selected files, processing status, results, and progress.

## Key Options

- `--preview N`: Print first N records to stdout after conversion
- `--output-json/--output-ndjson`: Toggle between JSON array and NDJSON (default: NDJSON)
- `--pretty`: Pretty-print JSON arrays
- `--section-patterns-file`: Override default section detection patterns
- `--max-rows N`: Process only first N rows (for testing)
- `--skip-empty-sections/--include-empty-sections`: Skip sections with no data rows (default: skip)
- `--group-by-section/--preserve-file-order`: Group records by section and sort by time (default: group)
- `--verbose`: Enable debug logging

## Development Setup

This project uses `uv` for Python dependency management. Python 3.11+ required.

```bash
# Dependencies are managed in pyproject.toml
# Main dependency: click>=8.3.0
```

## Packaging and Distribution

**CRITICAL**: When adding new Python modules to the project, they MUST be added to the `py-modules` list in `pyproject.toml` to ensure they are included in the installed package.

Current required modules in `pyproject.toml`:
```toml
[tool.setuptools]
py-modules = ["main", "batch", "tui", "__version__"]
```

The `__version__.py` module is essential for the CLI tool to display version information. If it's missing from the package, users will get `ModuleNotFoundError` when running the installed tool.

To test packaging locally:
```bash
# Install as a tool
uv tool install .

# Verify it works
schwab-csv-to-json --version

# If you make packaging changes, reinstall
uv tool uninstall schwab-csv-to-json
uv tool install .
```

## Development Methodology

**Use TDD (Test-Driven Development)** when adding new features or fixing bugs:

1. Write failing tests first that describe the desired behavior
2. Implement the minimum code needed to make tests pass
3. Refactor while keeping tests green

Run tests with:
```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_foo.py  # Run specific test file
uv run pytest -v                 # Verbose output
uv run pytest -k test_name       # Run specific test by name
```

### Multi-File TUI Feature Development

**IMPORTANT**: All work on the multi-file TUI feature (adding Textual-based TUI, batch processing, merged output) MUST follow strict TDD methodology. See `Tasks.md` for the complete implementation checklist with all phases and tasks.

Key TDD requirements for this feature:
- Write tests BEFORE implementing each function or feature
- Ensure all existing tests pass before adding new functionality
- Add unit tests for all helper functions
- Add integration tests for batch processing and TUI workflows
- Never skip the red-green-refactor cycle

## Version Management

When making changes, update the version number in both `main.py` (`__version__`) and `pyproject.toml`:

- **Minor version** (e.g., 1.1.0 → 1.2.0): New features or changes to existing features
- **Patch version** (e.g., 1.1.0 → 1.1.1): Bug fixes only

## Important Implementation Details

**Null Handling**: The code normalizes empty CSV cells to `None` early in processing. Always check if values are truthy before calling string methods like `.strip()` or using `in` operator to avoid `NoneType` errors.

**Heuristic Fallback**: If no header mapping exists for a section (lines 224-236 in main.py), the code uses hard-coded column indices based on typical Schwab CSV structure (14+ columns expected).

**Issues Tracking**: Each output record includes an `issues` array that tracks parse failures, missing headers, etc. Section header rows are marked with `["section_header"]`.
