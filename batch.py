#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processor for handling multiple CSV files.

This module provides functionality to process multiple Schwab CSV files
and merge their output into a single file with source file metadata.
"""

from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass


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
            records = process_single_file_for_batch(file_path, file_index, options)

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
        file_errors=file_errors
    )


def process_single_file_for_batch(
    file_path: str,
    file_index: int,
    options: BatchOptions
) -> List[Dict[str, Any]]:
    """
    Process a single file for batch processing.

    This is a helper function that processes one CSV file and adds
    source file metadata to each record.

    Args:
        file_path: Path to CSV file
        file_index: Index of this file in the batch
        options: Batch processing options

    Returns:
        List of records with source_file metadata added
    """
    from main import parse_file

    # Parse the file using main.py's parse_file function
    records = parse_file(
        path=file_path,
        include_rolling=options.include_rolling,
        section_patterns=options.section_patterns,
        max_rows=options.max_rows,
        qty_unsigned=options.qty_unsigned,
        verbose=options.verbose
    )

    # Add source file metadata to each record
    source_filename = Path(file_path).name
    for record in records:
        record['source_file'] = source_filename
        record['source_file_index'] = file_index

    return records
