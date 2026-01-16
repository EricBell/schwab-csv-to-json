#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processor for handling multiple CSV files.

This module provides functionality to process multiple Schwab CSV files
and merge their output into a single file with source file metadata.
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from pathlib import Path
from dataclasses import dataclass
from collections import OrderedDict
from datetime import datetime


@dataclass
class BatchOptions:
    """Options for batch processing multiple CSV files."""

    include_rolling: bool = False
    """Include Rolling Strategies section in output."""

    section_patterns: Optional[Dict[str, str]] = None
    """Custom section detection patterns."""

    max_rows: Optional[int] = None
    """Maximum rows to process per file (for testing)."""

    qty_unsigned: bool = False
    """Parse quantities as unsigned (absolute values)."""

    verbose: bool = False
    """Enable verbose logging."""

    skip_empty_sections: bool = True
    """Skip sections that have only headers with no data rows."""

    group_by_section: bool = True
    """Group records by section across files and sort by time."""

    filter_triggered_rejected: bool = True
    """Filter out rows with TRIGGERED or REJECTED status."""


@dataclass
class FileProgress:
    """Progress information for a single file being processed."""

    file_path: str
    """Path to the file being processed."""

    file_index: int
    """Index of this file in the batch (0-based)."""

    total_files: int
    """Total number of files in the batch."""

    records_parsed: int
    """Number of records parsed so far from this file."""

    status: str
    """Current status: 'processing', 'completed', 'failed'."""

    error: Optional[str] = None
    """Error message if status is 'failed'."""


# Type alias for progress callback function
ProgressCallback = Callable[[FileProgress], None]


def get_sort_time(record: Dict[str, Any]) -> Optional[datetime]:
    """
    Extract the appropriate time field for sorting.

    Priority: exec_time > time_canceled > time_placed
    Returns None if no time field is available or parseable.
    """
    # Try exec_time first
    exec_time_str = record.get('exec_time')
    if exec_time_str:
        try:
            return datetime.fromisoformat(exec_time_str)
        except (ValueError, TypeError):
            pass

    # Try time_canceled
    time_canceled_str = record.get('time_canceled')
    if time_canceled_str:
        try:
            return datetime.fromisoformat(time_canceled_str)
        except (ValueError, TypeError):
            pass

    # Try time_placed
    time_placed_str = record.get('time_placed')
    if time_placed_str:
        try:
            return datetime.fromisoformat(time_placed_str)
        except (ValueError, TypeError):
            pass

    return None


def group_and_sort_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group records by section and sort by time within each section.

    Args:
        records: List of all records from batch processing

    Returns:
        Reordered list with records grouped by section and sorted by time
    """
    # Separate section headers from data records
    section_headers: Dict[str, Dict[str, Any]] = {}
    data_records_by_section: Dict[str, List[Dict[str, Any]]] = {}

    for record in records:
        section = record.get('section', 'Unknown')
        is_header = 'section_header' in record.get('issues', [])

        if is_header:
            # Keep only the first section header for each section
            if section not in section_headers:
                section_headers[section] = record
        else:
            # Group data records by section
            if section not in data_records_by_section:
                data_records_by_section[section] = []
            data_records_by_section[section].append(record)

    # Sort data records within each section by time
    for section, section_records in data_records_by_section.items():
        section_records.sort(key=lambda r: (
            get_sort_time(r) is None,  # Records with no time go last
            get_sort_time(r) if get_sort_time(r) is not None else datetime.max
        ))

    # Reconstruct output: section header + sorted data records for each section
    result = []

    # Define section order (alphabetical)
    section_order = sorted(section_headers.keys())

    for section in section_order:
        # Add section header first
        if section in section_headers:
            result.append(section_headers[section])

        # Add sorted data records
        if section in data_records_by_section:
            result.extend(data_records_by_section[section])

    return result


@dataclass
class BatchResult:
    """Results from batch processing operation."""

    total_files: int
    """Total number of files processed."""

    successful_files: int
    """Number of files processed successfully."""

    failed_files: int
    """Number of files that failed to process."""

    total_records: int
    """Total number of records parsed across all files."""

    validation_issues: Dict[str, int]
    """Aggregated validation issues across all files."""

    file_errors: Dict[str, str]
    """Map of file path to error message for failed files."""

    sections_skipped: int = 0
    """Number of empty sections skipped during processing."""


def process_multiple_files(
    file_paths: List[str],
    output_path: str,
    options: BatchOptions,
    progress_callback: Optional[ProgressCallback] = None
) -> BatchResult:
    """
    Process multiple CSV files and merge output into a single file.

    This function processes multiple Schwab CSV files sequentially and writes
    all records to a single output file in NDJSON or JSON array format. Each
    record includes a 'source_file' field identifying which file it came from.

    Args:
        file_paths: List of paths to CSV files to process
        output_path: Path to output file (.ndjson or .json)
        options: Batch processing options
        progress_callback: Optional callback for progress updates

    Returns:
        BatchResult with statistics and any errors

    Raises:
        ValueError: If file_paths is empty
        FileNotFoundError: If output directory doesn't exist

    Example:
        >>> options = BatchOptions(verbose=True)
        >>> result = process_multiple_files(
        ...     ['file1.csv', 'file2.csv'],
        ...     'output.ndjson',
        ...     options
        ... )
        >>> print(f"Processed {result.total_records} records")

    Output Format:
        Each record in the output includes all standard fields plus:
        - source_file: str - basename of the source CSV file
        - source_file_index: int - index of the file in the batch
    """
    import json
    from main import validate

    if not file_paths:
        raise ValueError("file_paths cannot be empty")

    total_files = len(file_paths)
    successful_files = 0
    failed_files = 0
    total_records = 0
    total_sections_skipped = 0
    aggregated_validation_issues: Dict[str, int] = {}
    file_errors: Dict[str, str] = {}
    all_records: List[Dict[str, Any]] = []

    # Process each file sequentially
    for file_index, file_path in enumerate(file_paths):
        try:
            # Notify progress: processing
            if progress_callback:
                progress = FileProgress(
                    file_path=file_path,
                    file_index=file_index,
                    total_files=total_files,
                    records_parsed=0,
                    status='processing'
                )
                progress_callback(progress)

            # Process the file
            records, sections_skipped = process_single_file_for_batch(file_path, file_index, options)
            total_sections_skipped += sections_skipped

            # Validate and aggregate issues
            validation_issues = validate(records)
            for issue_type, count in validation_issues.items():
                aggregated_validation_issues[issue_type] = \
                    aggregated_validation_issues.get(issue_type, 0) + count

            # Add to results
            all_records.extend(records)
            total_records += len(records)
            successful_files += 1

            # Notify progress: completed
            if progress_callback:
                progress = FileProgress(
                    file_path=file_path,
                    file_index=file_index,
                    total_files=total_files,
                    records_parsed=len(records),
                    status='completed'
                )
                progress_callback(progress)

        except FileNotFoundError as e:
            failed_files += 1
            file_errors[file_path] = f"File not found: {str(e)}"

            # Notify progress: failed
            if progress_callback:
                progress = FileProgress(
                    file_path=file_path,
                    file_index=file_index,
                    total_files=total_files,
                    records_parsed=0,
                    status='failed',
                    error=file_errors[file_path]
                )
                progress_callback(progress)

        except Exception as e:
            failed_files += 1
            file_errors[file_path] = str(e)

            # Notify progress: failed
            if progress_callback:
                progress = FileProgress(
                    file_path=file_path,
                    file_index=file_index,
                    total_files=total_files,
                    records_parsed=0,
                    status='failed',
                    error=file_errors[file_path]
                )
                progress_callback(progress)

    # Group and sort records if requested
    if options.group_by_section and all_records:
        all_records = group_and_sort_records(all_records)

    # Write output file
    if all_records:
        with open(output_path, 'w', encoding='utf-8') as out:
            for record in all_records:
                out.write(json.dumps(record, ensure_ascii=False) + '\n')

    return BatchResult(
        total_files=total_files,
        successful_files=successful_files,
        failed_files=failed_files,
        total_records=total_records,
        validation_issues=aggregated_validation_issues,
        file_errors=file_errors,
        sections_skipped=total_sections_skipped
    )


def process_single_file_for_batch(
    file_path: str,
    file_index: int,
    options: BatchOptions
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Process a single file for batch processing.

    This is a helper function that processes one CSV file and adds
    source file metadata to each record.

    Args:
        file_path: Path to CSV file
        file_index: Index of this file in the batch
        options: Batch processing options

    Returns:
        Tuple of (list of records with source_file metadata added, sections_skipped count)
    """
    from main import parse_file

    # Parse the file using main.py's parse_file function
    records, sections_skipped = parse_file(
        path=file_path,
        include_rolling=options.include_rolling,
        section_patterns=options.section_patterns,
        max_rows=options.max_rows,
        qty_unsigned=options.qty_unsigned,
        verbose=options.verbose,
        skip_empty_sections=options.skip_empty_sections,
        filter_triggered_rejected=options.filter_triggered_rejected
    )

    # Add source file metadata to each record
    source_filename = Path(file_path).name
    for record in records:
        record['source_file'] = source_filename
        record['source_file_index'] = file_index

    return records, sections_skipped
