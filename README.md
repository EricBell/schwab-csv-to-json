# schwab-csv-to-json

Convert Schwab CSV trade activity reports into flat NDJSON (newline-delimited JSON) or JSON array format with both CLI and interactive TUI modes.

## Overview

Schwab trade activity CSVs contain multiple logical sections (Filled Orders, Working Orders, Canceled Orders, Rolling Strategies) within a single file, each with its own header row. This tool parses these multi-section CSVs and converts them into a flat, structured JSON format with consistent schema across all sections.

## Features

- **Interactive TUI Mode**: Terminal UI for selecting and batch-processing multiple files
- **Batch Processing**: Process multiple CSV files into a single merged output
- **Multi-section parsing**: Automatically detects and processes different sections in Schwab CSVs
- **Flexible output formats**: NDJSON (default) or JSON array
- **Field normalization**: Parses quantities, prices, and timestamps with proper type handling
- **Source tracking**: Each record includes source file metadata for batch operations
- **Customizable patterns**: Override default section detection with custom regex patterns
- **Error tracking**: Each record includes an `issues` array tracking parse failures
- **Progress tracking**: Real-time progress updates for batch operations
- **Unicode support**: Handles BOM and various encodings
- **Preview mode**: View first N records before processing full file

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management.

```bash
# Clone the repository
git clone https://github.com/yourusername/schwab-csv-to-json.git
cd schwab-csv-to-json

# Install dependencies (uv will create a virtual environment automatically)
uv sync
```

## Usage

### Interactive TUI Mode (Recommended)

Launch the interactive terminal UI for easy multi-file processing:

```bash
# Launch TUI in current directory
uv run python main.py tui

# Launch TUI in specific directory with custom output path
uv run python main.py tui --dir /path/to/csvs --output results.ndjson
```

The TUI provides:
- **File browser**: Navigate directories and select multiple CSV files
- **Progress tracking**: Real-time progress bars for each file
- **Error review**: Interactive table of validation issues
- **Summary stats**: Processing time, record counts, and error breakdown

### CLI Mode

#### Single File Conversion

```bash
# Convert CSV to NDJSON (default)
uv run python main.py convert examples/2025-10-24-TradeActivity.csv output.ndjson

# Convert to JSON array with pretty printing
uv run python main.py convert input.csv output.json --output-json --pretty

# Preview first 10 records
uv run python main.py convert input.csv output.ndjson --preview 10
```

#### Batch Processing (Multiple Files)

```bash
# Process multiple files into merged output
uv run python main.py convert file1.csv file2.csv file3.csv merged_output.ndjson

# With verbose progress
uv run python main.py convert *.csv output.ndjson --verbose

# Batch processing automatically adds source_file metadata to each record
```

### Command-Line Options

```bash
uv run python main.py convert --help
```

Available options:
- `--encoding TEXT`: File encoding for input CSV (default: utf-8)
- `--output-ndjson/--output-json`: Output format (default: NDJSON)
- `--pretty`: Pretty-print JSON arrays
- `--preview N`: Print first N output records to stdout
- `--max-rows N`: Process only first N CSV rows (0 = all)
- `--qty-signed/--qty-unsigned`: Handle quantity signs (default: signed)
- `--verbose, -v`: Enable debug logging with progress updates
- `--section-patterns-file PATH`: Custom JSON file with section detection patterns
- `--include-rolling`: Include Rolling Strategies section

### Custom Section Patterns

Create a JSON file mapping regex patterns to section names:

```json
{
  "(?i)exec.*time.*price.*order.*type": "Filled Orders",
  "(?i)working.*orders": "Working Orders"
}
```

Then use it:

```bash
uv run python main.py input.csv output.ndjson --section-patterns-file patterns.json
```

## Output Format

### Single File Output

Each output record contains:

```json
{
  "section": "Filled Orders",
  "row_index": 8,
  "exec_time": "2025-10-24T09:51:38",
  "side": "SELL",
  "qty": -75,
  "pos_effect": "TO CLOSE",
  "symbol": "NEUP",
  "price": 8.30,
  "net_price": 8.30,
  "price_improvement": null,
  "order_type": "MKT",
  "raw": ",,10/24/25 09:51:38,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.30,8.30,-,MKT",
  "issues": []
}
```

### Batch Processing Output

When processing multiple files, each record includes source metadata:

```json
{
  "section": "Filled Orders",
  "row_index": 8,
  "exec_time": "2025-10-24T09:51:38",
  "side": "SELL",
  "qty": -75,
  "symbol": "NEUP",
  "price": 8.30,
  "source_file": "2025-10-24-TradeActivity.csv",
  "source_file_index": 0,
  "raw": "...",
  "issues": []
}
```

The `source_file` field contains the basename of the CSV file, and `source_file_index` is the 0-based index in the batch.

## Development

### Running Tests

This project uses pytest and follows TDD (Test-Driven Development) methodology.

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_main.py

# Run specific test by name
uv run pytest -k test_parse_qty
```

### Project Structure

```
schwab-csv-to-json/
├── main.py                 # Main CLI entry point with convert/tui commands
├── batch.py                # Batch processing module for multiple files
├── tui.py                  # Textual TUI application (4 screens)
├── tests/                  # Test suite (110 tests, all passing)
│   ├── test_main.py        # Unit tests (76 tests)
│   ├── test_integration.py # Integration tests (19 tests)
│   └── test_batch.py       # Batch processing tests (15 tests)
├── examples/               # Sample CSV files
├── patterns.json           # Default section detection patterns
├── pyproject.toml          # Project dependencies
├── Tasks.md                # Implementation task tracking
├── CLAUDE.md              # Developer guidance
└── README.md              # This file
```

## Requirements

- Python 3.11+
- click>=8.3.0
- textual>=0.47.0 (for TUI mode)
- rich>=13.0.0 (for enhanced terminal output)

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Contributing

1. Write tests first (TDD approach)
2. Ensure all tests pass: `uv run pytest`
3. Follow the coding guidelines in CLAUDE.md

## Acknowledgments

Built for parsing Schwab trade activity CSV exports.
