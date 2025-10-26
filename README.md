# schwab-csv-to-json

Convert Schwab CSV trade activity reports into flat NDJSON (newline-delimited JSON) or JSON array format.

## Overview

Schwab trade activity CSVs contain multiple logical sections (Filled Orders, Working Orders, Canceled Orders, Rolling Strategies) within a single file, each with its own header row. This tool parses these multi-section CSVs and converts them into a flat, structured JSON format with consistent schema across all sections.

## Features

- **Multi-section parsing**: Automatically detects and processes different sections in Schwab CSVs
- **Flexible output formats**: NDJSON (default) or JSON array
- **Field normalization**: Parses quantities, prices, and timestamps with proper type handling
- **Customizable patterns**: Override default section detection with custom regex patterns
- **Error tracking**: Each record includes an `issues` array tracking parse failures
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

### Basic Usage

```bash
# Convert CSV to NDJSON (default)
uv run python main.py examples/2025-10-24-TradeActivity.csv output.ndjson

# Convert to JSON array with pretty printing
uv run python main.py input.csv output.json --output-json --pretty

# Preview first 10 records
uv run python main.py input.csv output.ndjson --preview 10
```

### Command-Line Options

```bash
uv run python main.py --help
```

Available options:
- `--encoding TEXT`: File encoding for input CSV (default: utf-8)
- `--output-ndjson/--output-json`: Output format (default: NDJSON)
- `--pretty`: Pretty-print JSON arrays
- `--preview N`: Print first N output records to stdout
- `--max-rows N`: Process only first N CSV rows (0 = all)
- `--qty-signed/--qty-unsigned`: Handle quantity signs (default: signed)
- `--verbose`: Enable debug logging
- `--section-patterns-file PATH`: Custom JSON file with section detection patterns

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

Each output record contains:

```json
{
  "section": "Filled Orders",
  "row_index": 8,
  "exec_time": "10/24/25 09:51:38",
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
├── main.py              # Main conversion script
├── tests/               # Test suite
│   ├── test_main.py     # Unit tests
│   └── test_integration.py  # Integration tests
├── examples/            # Sample CSV files
├── patterns.json        # Default section patterns
├── pyproject.toml       # Project dependencies
├── CLAUDE.md           # Developer guidance
└── README.md           # This file
```

## Requirements

- Python 3.11+
- click>=8.3.0

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Contributing

1. Write tests first (TDD approach)
2. Ensure all tests pass: `uv run pytest`
3. Follow the coding guidelines in CLAUDE.md

## Acknowledgments

Built for parsing Schwab trade activity CSV exports.
