# Product Requirements Document (PRD)
# Schwab CSV to JSON Converter

**Version:** 1.0
**Last Updated:** 2025-10-25
**Status:** Draft

---

## 1. Overview

### Problem Statement
<!-- Describe the problem this tool solves. What pain points does it address? -->

### Goal
<!-- What is the primary goal of this tool? What should users be able to accomplish? -->

### Non-Goals
<!-- What is explicitly out of scope for this tool? -->

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
<!-- Define expected fields -->

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
```csv
Today's Trade Activity for 7044 (Individual) on 10/24/25 18:45:11

Filled Orders
,,Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Price Improvement,Order Type
,,10/24/25 09:51:38,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.30,8.30,-,MKT
```

### Example Output
<!-- Paste expected JSON output for the sample input -->
```json
{"section": "Filled Orders", "row_index": 8, "exec_time": "10/24/25 09:51:38", "side": "SELL", "qty": -75, "pos_effect": "TO CLOSE", "symbol": "NEUP", "price": 8.30, "net_price": 8.30, "price_improvement": null, "order_type": "MKT", "raw": ",,10/24/25 09:51:38,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.30,8.30,-,MKT", "issues": []}
```

### References
<!-- Links to relevant documentation -->
- Schwab trade activity documentation: [URL if available]
- NDJSON spec: http://ndjson.org/
