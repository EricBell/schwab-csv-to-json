# Product Requirements Document (PRD)
# Schwab CSV to JSON Converter

**Version:** 1.0
**Last Updated:** 2025-10-25
**Status:** Draft

---

## 1. Overview

### Problem Statement

Schwab's trade activity CSV exports are difficult to work with programmatically because:

1. **Multi-section format**: A single CSV file contains multiple logical sections (Filled Orders, Working Orders, Canceled Orders, Rolling Strategies), each with its own header row. Standard CSV parsers treat these as malformed data.

2. **Inconsistent structure**: Different sections have different columns, making it impossible to use generic CSV-to-JSON converters without losing information or creating errors.

3. **Data quality issues**: The CSV contains:
   - Empty/placeholder rows between sections
   - Missing values represented as "-" or "~"
   - Leading empty columns (commas with no data)
   - Inconsistent field formatting (quantities with +/- signs, prices with/without $)

4. **Analysis friction**: Users need to:
   - Manually identify section boundaries
   - Write custom parsers for each section type
   - Handle edge cases (empty fields, malformed rows)
   - Track which rows failed to parse

This makes it time-consuming to analyze trade history, calculate P&L, or feed data into other tools.

### Goal

Create a **zero-configuration CLI tool** that converts Schwab trade activity CSV files into clean, structured JSON (NDJSON or JSON array) with:

- Automatic section detection
- Normalized field names across all sections
- Proper type conversion (strings → numbers where appropriate)
- Complete data preservation (raw CSV always included)
- Clear error tracking (which fields failed to parse)

Users should be able to run one command and get analysis-ready JSON output.

### Non-Goals

- **Not a trading platform**: Does not execute trades or connect to Schwab APIs
- **Not a tax calculator**: Does not calculate cost basis, wash sales, or tax lots
- **Not a portfolio tracker**: Does not maintain state across multiple CSV files
- **Not a data validator**: Does not validate if the trades are correct/valid, only parses what's present
- **Not a GUI application**: Command-line only (no web interface or desktop app)

---

## 2. Background & Context

### Current Situation
<!-- Describe the current state. What do users do today without this tool? -->

### Schwab CSV Format
<!-- Describe the structure of Schwab CSV files:
- What sections exist? (e.g., Filled Orders, Working Orders, Canceled Orders)
- How are sections delimited?
- What does a typical header row look like?
- What are the key fields in each section?
-->

### Use Cases
<!-- Who will use this tool and for what purposes?
1. Use case 1: ...
2. Use case 2: ...
-->

---

## 3. Requirements

### 3.1 Functional Requirements

#### Input Processing
<!-- What should the tool accept as input? -->
- [ ] Accept Schwab CSV trade activity files as input
- [ ] Support various CSV encodings (UTF-8, UTF-8 with BOM, etc.)
- [ ] Handle malformed or incomplete CSV rows gracefully

#### Section Detection & Parsing
<!-- How should the tool identify and process different sections? -->
- [ ] Automatically detect section boundaries (Filled Orders, Working Orders, etc.)
- [ ] Map column headers to standardized field names
- [ ] Support custom section detection patterns

#### Data Transformation
<!-- How should data be normalized and transformed? -->
- [ ] Parse quantities as integers (with proper sign handling)
- [ ] Parse prices as floats (removing $, commas)
- [ ] Parse dates/timestamps in Schwab's format (e.g., "10/24/25 09:51:38")
- [ ] Handle missing/empty fields as null values
- [ ] Track parse errors and validation issues per record

#### Output Generation
<!-- What output formats should be supported? -->
- [ ] Generate NDJSON (newline-delimited JSON) by default
- [ ] Support JSON array output as an option
- [ ] Include all raw CSV data for reference
- [ ] Include metadata: section name, row index, issues

### 3.2 Non-Functional Requirements

#### Performance
<!-- What are the performance expectations? -->
- [ ] Process files with thousands of rows efficiently
- [ ] Memory usage should be reasonable for typical file sizes

#### Usability
<!-- How should the tool be used? -->
- [ ] Command-line interface (CLI)
- [ ] Clear error messages for invalid input
- [ ] Help documentation (--help flag)
- [ ] Preview mode to inspect output before full processing

#### Reliability
<!-- What reliability guarantees should exist? -->
- [ ] Never lose data (preserve raw CSV in output)
- [ ] Gracefully handle edge cases (empty files, malformed data)
- [ ] Validate input files exist before processing

#### Maintainability
<!-- Development and maintenance requirements -->
- [ ] Well-tested with unit and integration tests
- [ ] Follow TDD methodology for new features
- [ ] Clear, documented code

---

## 4. Data Schema

### Input: Schwab CSV Structure

#### Filled Orders Section
<!-- Example header row and expected fields -->
```
Exec Time, Spread, Side, Qty, Pos Effect, Symbol, Exp, Strike, Type, Price, Net Price, Price Improvement, Order Type
```

Expected fields:
- **Exec Time**: Execution timestamp (e.g., "10/24/25 09:51:38")
- **Side**: BUY or SELL
- **Qty**: Quantity (integer, may be signed)
- **Symbol**: Stock/option symbol
- **Price**: Execution price
- **Net Price**: Net price after fees
- **Price Improvement**: Price improvement amount (if any)
- **Order Type**: MKT, LMT, STP, etc.

<!-- Add other sections as needed -->

#### Working Orders Section
<!-- Define expected fields -->

#### Canceled Orders Section
```
Notes,,Time Canceled,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,,(Order Type),TIF,Status
```

Expected fields:
- **Notes**: Free-form text field (typically empty in exports)
- **Time Canceled**: Cancellation timestamp (e.g., "10/24/25 09:51:36")
- **Spread**: Order spread type (STOCK, VERTICAL, IRON CONDOR, etc.)
- **Side**: BUY or SELL
- **Qty**: Quantity (integer, may be signed with +/-)
- **Pos Effect**: Position effect (TO OPEN, TO CLOSE)
- **Symbol**: Stock/option symbol
- **Exp**: Option expiration date (empty for stocks)
- **Strike**: Option strike price (empty for stocks)
- **Type**: Instrument type (STOCK, CALL, PUT, etc.)
- **PRICE**: Limit or stop price (uppercase in header; "~" for market orders without limit)
- **(Order Type)**: Order type (MKT, LMT, STP) - **Note: This column is unlabeled in the CSV header (appears as empty field)**
- **TIF**: Time In Force (DAY, GTC, GTD, STD, etc.)
- **Status**: Order status (always "CANCELED" in this section)

**Key Differences from Filled Orders:**
- Uses "Time Canceled" instead of "Exec Time"
- Missing "Net Price" and "Price Improvement" (orders weren't executed)
- Has "TIF" (Time In Force) field
- Has "Status" field to indicate cancellation
- Order Type column is unlabeled in header

**Data Quality Notes:**
- The "~" character represents market orders without limit prices
- Some canceled orders span multiple CSV rows (e.g., stop-market orders may show the stop trigger price on a continuation row)
- Multi-row orders: Lines 22-23, 24-25, 26-27 in example show this pattern where the second row contains additional stop price information
- Continuation rows have most fields empty except PRICE, Order Type, and TIF fields

### Output: JSON Schema

```json
{
  "section": "string",           // Section name (e.g., "Filled Orders")
  "row_index": "integer",        // Line number in CSV (1-indexed)
  "exec_time": "string|null",    // Execution timestamp
  "side": "string|null",         // BUY or SELL
  "qty": "integer|null",         // Quantity (signed)
  "pos_effect": "string|null",   // Position effect (TO OPEN, TO CLOSE)
  "symbol": "string|null",       // Symbol
  "price": "float|null",         // Price
  "net_price": "float|null",     // Net price
  "price_improvement": "float|null",  // Price improvement
  "order_type": "string|null",   // Order type
  "raw": "string",               // Original CSV row (comma-joined)
  "issues": ["string"]           // Array of issue codes (e.g., ["qty_parse_failed"])
}
```

---

## 5. User Interface

### CLI Commands

#### Basic Usage
```bash
python main.py <input.csv> <output.json>
```

#### Options
<!-- Define all CLI flags and their behavior -->

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--encoding` | string | utf-8 | Input CSV encoding |
| `--output-ndjson` | flag | true | Output as NDJSON |
| `--output-json` | flag | false | Output as JSON array |
| `--pretty` | flag | false | Pretty-print JSON |
| `--preview N` | int | 0 | Show first N records |
| `--max-rows N` | int | 0 | Process only N rows |
| `--verbose` | flag | false | Debug logging |
| `--section-patterns-file` | path | - | Custom section patterns |

### Error Messages
<!-- Define what error messages should look like -->

---

## 6. Edge Cases & Error Handling

### Edge Cases to Handle
<!-- List specific edge cases and how they should be handled -->

1. **Empty CSV file**:
   - Behavior: <!-- Create empty output file? Error? -->

2. **CSV with no recognizable sections**:
   - Behavior: <!-- Treat entire file as "Top" section? -->

3. **Rows with more/fewer columns than header**:
   - Behavior: <!-- Map available columns, track as issue -->

4. **Invalid data in numeric fields** (e.g., "abc" in qty field):
   - Behavior: <!-- Preserve raw value, add to issues array -->

5. **Multiple sections with same name**:
   - Behavior: <!-- Process all with same section name? -->

6. **Multi-row orders in Canceled Orders section**:
   - Example: A stop-market order may have two CSV rows: first with order details, second with stop trigger price
   - Behavior: <!-- Should we merge these into a single JSON record? Treat as separate records? Add a flag indicating continuation row? -->

### Error Conditions
<!-- What should cause the program to fail vs. warn? -->

**Should fail (exit non-zero):**
- Input file doesn't exist
- Input file is not readable
- Output directory doesn't exist
- Invalid section patterns file

**Should warn but continue:**
- Malformed CSV rows
- Parse failures for individual fields
- Missing expected columns

---

## 7. Success Metrics

### How do we measure success?
<!-- What indicates this tool is working well? -->

- [ ] Successfully parses 100% of valid Schwab CSV exports
- [ ] Zero data loss (all raw data preserved)
- [ ] Parse errors are tracked and reported (issues array)
- [ ] Users can easily customize section detection

---

## 8. Future Enhancements

### Potential Future Features
<!-- Features that are out of scope now but might be added later -->

1. **Date normalization**: Convert Schwab date format to ISO-8601
2. **CSV output option**: Convert to normalized CSV (instead of JSON)
3. **Multi-file processing**: Process entire directory of CSVs
4. **Summary statistics**: Generate summary report (total trades, P&L, etc.)
5. **Validation rules**: Custom validation rules per section
6. **Streaming mode**: Process very large files with constant memory

---

## 9. Open Questions

<!-- Questions that need to be answered to finalize requirements -->

1. Question: Should quantities be signed (negative for sells) or unsigned with separate direction field?
   - Current behavior: Signed by default with `--qty-unsigned` option
   - Decision needed: Is this the right default?

2. Question: How should we handle multi-leg option strategies?
   - Current behavior: Each leg is a separate record
   - Alternative: Group related legs together?

3. Question: What should happen with the "Rolling Strategies" section?
   - Current behavior: Parsed like other sections
   - Requirement clarity needed: Does this section have different semantics?

---

## 10. Appendix

### Example Input
<!-- Paste a small sample of actual Schwab CSV -->

**Filled Orders Example:**
```csv
Today's Trade Activity for 7044 (Individual) on 10/24/25 18:45:11

Filled Orders
,,Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Price Improvement,Order Type
,,10/24/25 09:51:38,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.30,8.30,-,MKT
```

**Canceled Orders Example:**
```csv
Canceled Orders
Notes,,Time Canceled,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,,TIF,Status
,,10/24/25 09:51:36,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.51,LMT,DAY,CANCELED
,,10/24/25 09:50:58,STOCK,BUY,+25,TO OPEN,NEUP,,,STOCK,~,MKT,DAY,CANCELED
,,,,,,,,,,,8.47,STP,STD,
```

**Note:** The last two rows show a multi-row order where the second row (line 3) contains the stop trigger price (8.47) for the market order in the previous row (line 2).

### Example Output
<!-- Paste expected JSON output for the sample input -->
```json
{"section": "Filled Orders", "row_index": 8, "exec_time": "10/24/25 09:51:38", "side": "SELL", "qty": -75, "pos_effect": "TO CLOSE", "symbol": "NEUP", "price": 8.30, "net_price": 8.30, "price_improvement": null, "order_type": "MKT", "raw": ",,10/24/25 09:51:38,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.30,8.30,-,MKT", "issues": []}
```

### References
<!-- Links to relevant documentation -->
- Schwab trade activity documentation: [URL if available]
- NDJSON spec: http://ndjson.org/
