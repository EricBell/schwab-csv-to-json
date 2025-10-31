# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python CLI tool that converts Schwab CSV trade activity reports into flat NDJSON (newline-delimited JSON) or JSON array format. Schwab CSVs contain multiple logical sections (Filled Orders, Working Orders, Canceled Orders, Rolling Strategies) within a single file, each with its own header row.

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
# Basic usage with uv
uv run python main.py examples/2025-10-24-TradeActivity.csv output.ndjson

# With options
uv run python main.py input.csv output.ndjson --preview 10 --verbose

# Output as JSON array instead of NDJSON
uv run python main.py input.csv output.json --output-json --pretty

# Use custom section patterns
uv run python main.py input.csv output.ndjson --section-patterns-file patterns.json
```

## Key Options

- `--preview N`: Print first N records to stdout after conversion
- `--output-json/--output-ndjson`: Toggle between JSON array and NDJSON (default: NDJSON)
- `--pretty`: Pretty-print JSON arrays
- `--section-patterns-file`: Override default section detection patterns
- `--max-rows N`: Process only first N rows (for testing)
- `--verbose`: Enable debug logging

## Development Setup

This project uses `uv` for Python dependency management. Python 3.11+ required.

```bash
# Dependencies are managed in pyproject.toml
# Main dependency: click>=8.3.0
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

## Important Implementation Details

**Null Handling**: The code normalizes empty CSV cells to `None` early in processing. Always check if values are truthy before calling string methods like `.strip()` or using `in` operator to avoid `NoneType` errors.

**Heuristic Fallback**: If no header mapping exists for a section (lines 224-236 in main.py), the code uses hard-coded column indices based on typical Schwab CSV structure (14+ columns expected).

**Issues Tracking**: Each output record includes an `issues` array that tracks parse failures, missing headers, etc. Section header rows are marked with `["section_header"]`.
