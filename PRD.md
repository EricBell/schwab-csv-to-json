# Product Requirements Document (PRD)
# Schwab CSV to JSON Converter

**Version:** 1.1 (Planning)
**Last Updated:** 2025-11-04
**Status:**
- ✅ **v1.0 COMPLETE** - All core requirements implemented (110 tests passing)
- 🔄 **v1.1 IN PLANNING** - Enhanced batch features (Section 10)

**Implementation Summary:**

**Version 1.0 (Complete):**
- ✅ Functional Requirements: 13/13 (100%)
- ✅ Non-Functional Requirements: 11/11 (100%)
- ✅ Success Metrics: 4/4 (100%)
- 🎯 Bonus Features: TUI mode, batch processing (110 tests passing)

**Version 1.1 (Planned):**
- 🔄 Enhanced TUI multi-select UX
- 🔄 Skip empty sections filtering
- 🔄 Section-grouped, time-sorted output

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
- [x] Accept Schwab CSV trade activity files as input
- [x] Support various CSV encodings (UTF-8, UTF-8 with BOM, etc.)
- [x] Handle malformed or incomplete CSV rows gracefully

#### Section Detection & Parsing
<!-- How should the tool identify and process different sections? -->
- [x] Automatically detect section boundaries (Filled Orders, Working Orders, etc.)
- [x] Map column headers to standardized field names
- [x] Support custom section detection patterns

#### Data Transformation
<!-- How should data be normalized and transformed? -->
- [x] Parse quantities as integers (with proper sign handling)
- [x] Parse prices as floats (removing $, commas)
- [x] Parse dates/timestamps in Schwab's format (e.g., "10/24/25 09:51:38")
- [x] Handle missing/empty fields as null values
- [x] Track parse errors and validation issues per record

#### Output Generation
<!-- What output formats should be supported? -->
- [x] Generate NDJSON (newline-delimited JSON) by default
- [x] Support JSON array output as an option
- [x] Include all raw CSV data for reference
- [x] Include metadata: section name, row index, issues

### 3.2 Non-Functional Requirements

#### Performance
<!-- What are the performance expectations? -->
- [x] Process files with thousands of rows efficiently
- [x] Memory usage should be reasonable for typical file sizes

#### Usability
<!-- How should the tool be used? -->
- [x] Command-line interface (CLI)
- [x] Clear error messages for invalid input
- [x] Help documentation (--help flag)
- [x] Preview mode to inspect output before full processing

#### Reliability
<!-- What reliability guarantees should exist? -->
- [x] Never lose data (preserve raw CSV in output)
- [x] Gracefully handle edge cases (empty files, malformed data)
- [x] Validate input files exist before processing

#### Maintainability
<!-- Development and maintenance requirements -->
- [x] Well-tested with unit and integration tests (110 tests passing)
- [x] Follow TDD methodology for new features
- [x] Clear, documented code

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

- [x] Successfully parses 100% of valid Schwab CSV exports
- [x] Zero data loss (all raw data preserved)
- [x] Parse errors are tracked and reported (issues array)
- [x] Users can easily customize section detection

---

## 8. Future Enhancements

### Potential Future Features
<!-- Features that are out of scope now but might be added later -->

1. **Date normalization**: Convert Schwab date format to ISO-8601 ⚠️ _(Partially implemented - parse_datetime_maybe converts to ISO format)_
2. **CSV output option**: Convert to normalized CSV (instead of JSON) ❌ _(Not implemented)_
3. **Multi-file processing**: Process entire directory of CSVs ✅ _(IMPLEMENTED - batch.py module with CLI and TUI support)_
4. **Summary statistics**: Generate summary report (total trades, P&L, etc.) ✅ _(IMPLEMENTED - validation stats, processing time, TUI summary screen)_
5. **Validation rules**: Custom validation rules per section ❌ _(Not implemented)_
6. **Streaming mode**: Process very large files with constant memory ❌ _(Not implemented)_

### Bonus Features Implemented (Beyond Original PRD)

7. **Interactive TUI Mode**: Full terminal UI with 4 screens (file selection, progress tracking, summary, error review) ✅
8. **Batch Processing with Progress**: Real-time progress callbacks and per-file status tracking ✅
9. **Source File Metadata**: Each record includes source_file and source_file_index for batch operations ✅

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

## 10. Phase 2 Requirements (Version 1.1)

**Status:** Planned
**Target Version:** 1.1

This section documents additional requirements identified after the initial implementation (v1.0) was completed.

### 10.1 Enhanced TUI Multi-Select Experience

**Current State:** The TUI supports multi-file selection via DirectoryTree widget, but the UX is not obvious to users.

**Requirement:** Improve visual feedback for multi-file selection in TUI.

**Acceptance Criteria:**
- [ ] TUI displays clear visual indicators when files are selected (checkboxes or markers)
- [ ] Selected file count is prominently displayed and updates in real-time
- [ ] Instructions clearly explain how to select/deselect files
- [ ] Selected files list is visible before starting processing
- [ ] Users can easily deselect individual files

**Implementation Notes:**
- Consider adding checkboxes next to CSV files in tree
- Add "Selected: N files" indicator at top of screen
- Display list of selected files in a panel
- Add keyboard shortcuts for "select all" and "clear selection"

---

### 10.2 Skip Empty Sections

**Current State:** The parser outputs section header rows even when no data rows follow.

**Requirement:** Only include sections in output that contain at least one data row after the header.

**Acceptance Criteria:**
- [ ] Section headers with no following data rows are excluded from output
- [ ] Empty sections do not appear in validation statistics
- [ ] Users are notified (in verbose mode) when sections are skipped
- [ ] Works for both single-file and batch processing modes

**Example:**
```csv
Working Orders
Notes,,Time Placed,Spread,Side,Qty,Symbol...
(no data rows)

Filled Orders
,,Exec Time,Spread,Side,Qty,Symbol...
,,10/24/25 09:51:38,STOCK,SELL,-75,NEUP...
```

**Expected Output:** Only "Filled Orders" section is included; "Working Orders" section is skipped entirely.

**Implementation Notes:**
- Add buffering logic to detect if data rows exist after header
- Track skipped sections count in batch statistics
- Add `--include-empty-sections` flag to preserve old behavior if needed

---

### 10.3 Section-Grouped, Time-Sorted Output

**Current State:** Batch processing outputs records in file order (file1 all records, file2 all records, etc.)

**Requirement:** Group all records by section name across all files, then sort by execution time within each section.

**Acceptance Criteria:**
- [ ] All records from the same section are grouped together (e.g., all "Filled Orders" from all files)
- [ ] Records within each section are sorted by `exec_time` in ascending order
- [ ] Source file metadata (`source_file`, `source_file_index`) is preserved
- [ ] Works for both NDJSON and JSON array output formats
- [ ] Section order is deterministic (e.g., alphabetical or predefined order)

**Example Output Structure:**
```
# All Filled Orders from all files, sorted by exec_time
{"section": "Filled Orders", "exec_time": "2025-10-24T09:30:00", "source_file": "file1.csv", ...}
{"section": "Filled Orders", "exec_time": "2025-10-24T09:45:00", "source_file": "file2.csv", ...}
{"section": "Filled Orders", "exec_time": "2025-10-24T10:00:00", "source_file": "file1.csv", ...}

# Then all Canceled Orders from all files, sorted by time_canceled
{"section": "Canceled Orders", "time_canceled": "2025-10-24T09:35:00", "source_file": "file1.csv", ...}
{"section": "Canceled Orders", "time_canceled": "2025-10-24T09:50:00", "source_file": "file2.csv", ...}
```

**Sort Field Priority:**
- Primary: `exec_time` (for Filled Orders)
- Fallback: `time_canceled` (for Canceled Orders)
- Fallback: `time_placed` (for Working Orders)
- Records with no time field: Sorted to end of section

**Implementation Notes:**
- Post-processing step after batch collection
- Group by `section` field
- Sort within each group by time field
- Preserve section header records at beginning of each section
- Add `--preserve-file-order` flag to disable grouping if needed

---

### 10.4 Configuration Options

New CLI flags to support these features:

| Flag | Default | Description |
|------|---------|-------------|
| `--skip-empty-sections` | true | Skip sections with no data rows |
| `--include-empty-sections` | false | Include section headers even with no data |
| `--group-by-section` | true | Group records by section and sort by time |
| `--preserve-file-order` | false | Keep original file-by-file output order |

---

## 11. Appendix

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
