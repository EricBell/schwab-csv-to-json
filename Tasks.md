# Multi-File TUI Implementation Tasks

This document tracks the implementation of multi-file CSV processing with a Textual-based TUI interface. All tasks follow TDD methodology.

## Phase 1: Fix Broken Tests & Click Migration (TDD Foundation)

### 1.1 Click CLI Migration
- [ ] Replace argparse with Click decorators in main.py
- [ ] Add Click command group structure
- [ ] Migrate `--input`, `--output`, `--include-rolling` to Click options
- [ ] Add new Click options: `--output-json`, `--pretty`, `--preview`, `--max-rows`, `--verbose`
- [ ] Add `--section-patterns-file` option for custom patterns.json
- [ ] Add `--qty-unsigned` option
- [ ] Add `--encoding` option for CSV file encoding
- [ ] Verify Click CLI works with basic test run

### 1.2 Add Missing Helper Functions
- [ ] Implement `compile_section_patterns(patterns_dict)` - compile regex patterns from dict
- [ ] Implement `map_header_to_index(header_row, col_aliases)` - map headers to column indices
- [ ] Implement `safe_get(cells, index, default=None)` - safely get cell value by index
- [ ] Implement `detect_section_from_row(cells, patterns)` - match row against section patterns
- [ ] Implement `parse_integer_qty(value, unsigned=False)` - parse quantity with sign handling
- [ ] Implement `parse_float_field(value)` - parse price/float fields with $ and comma removal
- [ ] Add unit tests for each helper function
- [ ] Verify all helper tests pass

### 1.3 Add Configuration Constants
- [ ] Define `COL_ALIASES` dict mapping header variations to canonical names
- [ ] Define `DEFAULT_SECTION_PATTERNS` dict with regex patterns
- [ ] Integrate patterns.json loading into `compile_section_patterns()`
- [ ] Add tests for pattern compilation
- [ ] Add tests for column alias mapping

### 1.4 Unified Output Schema
- [ ] Update `build_order_record()` to include `row_index` field
- [ ] Update `build_order_record()` to include `raw` CSV line field
- [ ] Update `build_order_record()` to include `issues` array field
- [ ] Update `build_order_record()` to include `section` field
- [ ] Update `build_amendment_record()` with same schema additions
- [ ] Add `section_header` marker in issues array for header rows
- [ ] Write tests for unified schema output

### 1.5 Output Format Support
- [ ] Add NDJSON output formatter (existing behavior)
- [ ] Add JSON array output formatter
- [ ] Add pretty-print support for JSON arrays
- [ ] Add tests for both output formats
- [ ] Add tests for pretty printing

### 1.6 Verify All Tests Pass
- [ ] Run `uv run pytest tests/test_main.py` - all unit tests pass
- [ ] Run `uv run pytest tests/test_integration.py` - all integration tests pass
- [ ] Run `uv run pytest -v` - complete test suite passes
- [ ] Fix any remaining test failures
- [ ] Achieve green test status before proceeding

---

## Phase 2: Add Dependencies

### 2.1 Update pyproject.toml
- [ ] Add `textual>=0.47.0` to dependencies
- [ ] Add `rich>=13.0.0` to dependencies
- [ ] Add `pytest-asyncio>=0.23.0` to dev dependencies
- [ ] Add `pytest-cov>=4.1.0` to dev dependencies
- [ ] Run `uv sync` to install new dependencies
- [ ] Verify textual imports work: `python -c "import textual"`
- [ ] Verify rich imports work: `python -c "import rich"`

---

## Phase 3: Multi-File Batch Processing (TDD)

### 3.1 Design Batch Processor API
- [ ] Write specification for `process_multiple_files()` function signature
- [ ] Define batch processing options dataclass/dict
- [ ] Define progress callback interface
- [ ] Define error aggregation structure
- [ ] Document expected output format with `source_file` metadata

### 3.2 Write Batch Processor Tests
- [ ] Write test for processing 2 files into merged output
- [ ] Write test for processing 5+ files into merged output
- [ ] Write test for `source_file` field in each record
- [ ] Write test for error aggregation across files
- [ ] Write test for progress callback invocation
- [ ] Write test for handling missing/invalid file paths
- [ ] Write test for handling mixed valid/invalid files
- [ ] Write test for handling empty CSV files
- [ ] Write test for preserving record order within each file
- [ ] Write test for file-level metadata in output

### 3.3 Implement Batch Processor
- [ ] Create `batch.py` module
- [ ] Implement `process_multiple_files(paths, output_path, options, progress_callback=None)`
- [ ] Add `source_file` field to each parsed record
- [ ] Implement sequential file processing
- [ ] Implement progress callback invocation (per-file granularity)
- [ ] Implement error aggregation across all files
- [ ] Implement merged NDJSON output writer
- [ ] Implement merged JSON array output writer (when `--output-json` used)
- [ ] Add file-level validation summary
- [ ] Handle partial failures gracefully (continue on error)

### 3.4 Batch Processor Integration
- [ ] Add Click command option for multiple input files
- [ ] Integrate batch processor into main CLI flow
- [ ] Add tests for CLI batch processing invocation
- [ ] Verify batch mode works end-to-end
- [ ] All batch processor tests pass

---

## Phase 4: Textual TUI Implementation

### 4.1 TUI Architecture Design
- [ ] Design app state model (selected files, processing status, errors)
- [ ] Design screen navigation flow
- [ ] Define Textual app structure and screens
- [ ] Design widget layout for each screen
- [ ] Document TUI user interaction flow

### 4.2 File Selection Screen (TDD where possible)
- [ ] Write tests for file selection state management
- [ ] Implement FilePickerScreen with DirectoryTree widget
- [ ] Add multi-select capability for CSV files
- [ ] Add file filter (show only .csv files)
- [ ] Add current selection display
- [ ] Add "Start Processing" action
- [ ] Add "Quit" action
- [ ] Test file selection with example CSVs

### 4.3 Processing Screen
- [ ] Write tests for progress tracking state
- [ ] Implement ProcessingScreen with progress bars
- [ ] Add overall progress bar (files completed / total files)
- [ ] Add per-file progress display with status
- [ ] Add real-time record count display
- [ ] Add real-time error count display
- [ ] Connect to batch processor progress callbacks
- [ ] Add pause/cancel capability (optional)
- [ ] Test progress updates during processing

### 4.4 Error Review Screen
- [ ] Write tests for error aggregation display
- [ ] Implement ErrorReviewScreen with DataTable widget
- [ ] Display errors grouped by file
- [ ] Show columns: File, Row, Section, Issue
- [ ] Add filtering by file
- [ ] Add filtering by issue type
- [ ] Add export errors to CSV capability
- [ ] Add navigation back to summary

### 4.5 Summary Screen
- [ ] Write tests for summary statistics
- [ ] Implement SummaryScreen with stats table
- [ ] Display files processed count
- [ ] Display total records parsed
- [ ] Display total errors found
- [ ] Display processing time
- [ ] Display output file path
- [ ] Add "View Errors" action (navigate to error screen)
- [ ] Add "Process More Files" action (return to file picker)
- [ ] Add "Quit" action

### 4.6 TUI App Integration
- [ ] Create main TuiApp class extending Textual App
- [ ] Implement screen routing and navigation
- [ ] Add CSS/styling for consistent look
- [ ] Implement keyboard shortcuts
- [ ] Add help screen with keyboard commands
- [ ] Connect all screens together
- [ ] Add error handling for TUI crashes

### 4.7 TUI CLI Integration
- [ ] Add `tui` subcommand to Click CLI
- [ ] Add TUI mode entry point: `uv run python main.py tui`
- [ ] Add optional starting directory argument for file picker
- [ ] Add `--output` option for TUI mode (default output location)
- [ ] Test TUI launches correctly
- [ ] Test TUI can be quit cleanly

---

## Phase 5: Integration & Testing

### 5.1 End-to-End TUI Testing
- [ ] Test complete TUI flow: file selection → processing → error review → summary
- [ ] Test with single CSV file
- [ ] Test with multiple CSV files (2-5 files)
- [ ] Test with large CSV files (100+ rows)
- [ ] Test with CSV containing errors/issues
- [ ] Test keyboard navigation works correctly
- [ ] Test quit/exit at each screen
- [ ] Test TUI gracefully handles batch processor errors

### 5.2 CLI Batch Mode Testing
- [ ] Test CLI with multiple files: `main.py file1.csv file2.csv file3.csv -o output.ndjson`
- [ ] Test CLI with glob patterns: `main.py examples/*.csv -o output.ndjson`
- [ ] Test merged NDJSON output format
- [ ] Test merged JSON array output format
- [ ] Test `source_file` metadata present in all records
- [ ] Test error aggregation in CLI mode
- [ ] Test progress display in CLI mode (if added)

### 5.3 Regression Testing
- [ ] Run full pytest suite: `uv run pytest -v`
- [ ] Verify all unit tests pass
- [ ] Verify all integration tests pass
- [ ] Test single-file mode still works (backward compatibility)
- [ ] Test all CLI options work as expected
- [ ] Test custom patterns.json still works
- [ ] Fix any regressions introduced

### 5.4 Documentation Updates
- [ ] Update README with TUI usage instructions
- [ ] Update README with multi-file CLI usage examples
- [ ] Add screenshots/demo of TUI (if possible)
- [ ] Document merged output format with `source_file` field
- [ ] Document error aggregation behavior
- [ ] Update CLAUDE.md with new architecture details

### 5.5 Final Validation
- [ ] Process multiple real Schwab CSV files in TUI
- [ ] Verify output correctness
- [ ] Verify error reporting accuracy
- [ ] Performance test with 10+ files
- [ ] Check memory usage with large batches
- [ ] User acceptance testing

---

## Completion Checklist

- [ ] All tests passing (`uv run pytest`)
- [ ] TUI fully functional
- [ ] CLI batch mode functional
- [ ] Documentation updated
- [ ] No regressions in single-file mode
- [ ] Code follows TDD principles throughout
- [ ] Ready for production use

---

## Notes

- **TDD Discipline**: Every feature addition follows write-test-first methodology
- **Progress Tracking**: Update this file as tasks are completed
- **Blockers**: Document any blockers or issues discovered during implementation below

### Blockers / Issues
<!-- Add any blockers or issues encountered during implementation -->
