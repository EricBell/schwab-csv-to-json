"""Tests for batch processing functionality."""
import pytest
import json
import tempfile
import os
from pathlib import Path
from batch import (
    process_multiple_files,
    process_single_file_for_batch,
    BatchOptions,
    BatchResult,
    FileProgress,
)


class TestBatchProcessing:
    """Test basic batch processing functionality."""

    def test_process_two_files_merged_output(self):
        """Test processing 2 files into merged output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two test CSV files
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST1,10.50\n')

            with open(file2, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,BUY,200,TEST2,20.50\n')

            options = BatchOptions()
            result = process_multiple_files([file1, file2], output, options)

            # Verify result
            assert result.total_files == 2
            assert result.successful_files == 2
            assert result.failed_files == 0
            assert result.total_records > 0

            # Verify output file exists and contains merged data
            assert os.path.exists(output)

            records = []
            with open(output, 'r') as f:
                for line in f:
                    records.append(json.loads(line))

            # Should have records from both files (headers + data)
            assert len(records) >= 2

            # Find data records (not section headers)
            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            assert len(data_records) >= 2

    def test_process_five_files_merged_output(self):
        """Test processing 5+ files into merged output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []
            for i in range(5):
                file_path = os.path.join(tmpdir, f'file{i}.csv')
                files.append(file_path)
                with open(file_path, 'w') as f:
                    f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                    f.write(f',,10/24/25,SELL,{100+i},TEST{i},{10.0+i}\n')

            output = os.path.join(tmpdir, 'output.ndjson')
            options = BatchOptions()
            result = process_multiple_files(files, output, options)

            assert result.total_files == 5
            assert result.successful_files == 5
            assert result.failed_files == 0

            # Verify all files contributed records
            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            assert len(data_records) >= 5

    def test_source_file_field_in_records(self):
        """Test that source_file field is added to each record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'test_file.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.50\n')

            options = BatchOptions()
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # All records should have source_file field
            for record in records:
                assert 'source_file' in record
                assert record['source_file'] == 'test_file.csv'
                assert 'source_file_index' in record
                assert record['source_file_index'] == 0

    def test_source_file_index_increments(self):
        """Test that source_file_index increments for each file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []
            for i in range(3):
                file_path = os.path.join(tmpdir, f'file{i}.csv')
                files.append(file_path)
                with open(file_path, 'w') as f:
                    f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                    f.write(f',,10/24/25,SELL,{100+i},TEST{i},10.0\n')

            output = os.path.join(tmpdir, 'output.ndjson')
            options = BatchOptions()
            process_multiple_files(files, output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Group records by source_file_index
            by_index = {}
            for record in records:
                idx = record['source_file_index']
                if idx not in by_index:
                    by_index[idx] = []
                by_index[idx].append(record)

            # Should have records from all 3 files
            assert 0 in by_index
            assert 1 in by_index
            assert 2 in by_index


class TestErrorHandling:
    """Test error handling in batch processing."""

    def test_error_aggregation_across_files(self):
        """Test that validation errors are aggregated across files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            # File with missing symbol
            with open(file1, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,,10.50\n')  # Missing symbol

            # File with missing qty
            with open(file2, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,BUY,,TEST,20.50\n')  # Missing qty

            options = BatchOptions()
            result = process_multiple_files([file1, file2], output, options)

            # Validation issues should be aggregated
            assert 'missing_symbol' in result.validation_issues
            assert 'missing_qty' in result.validation_issues

    def test_handle_missing_file_path(self):
        """Test handling of non-existent file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, 'output.ndjson')
            missing_file = os.path.join(tmpdir, 'nonexistent.csv')

            options = BatchOptions()
            result = process_multiple_files([missing_file], output, options)

            assert result.total_files == 1
            assert result.successful_files == 0
            assert result.failed_files == 1
            assert missing_file in result.file_errors

    def test_handle_mixed_valid_invalid_files(self):
        """Test processing mix of valid and invalid files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            valid_file = os.path.join(tmpdir, 'valid.csv')
            invalid_file = os.path.join(tmpdir, 'nonexistent.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(valid_file, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.50\n')

            options = BatchOptions()
            result = process_multiple_files([valid_file, invalid_file], output, options)

            assert result.total_files == 2
            assert result.successful_files == 1
            assert result.failed_files == 1
            assert invalid_file in result.file_errors

            # Output should still be created with valid file's data
            assert os.path.exists(output)

    def test_handle_empty_csv_file(self):
        """Test handling of empty CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_file = os.path.join(tmpdir, 'empty.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            # Create empty file
            with open(empty_file, 'w') as f:
                pass

            options = BatchOptions()
            result = process_multiple_files([empty_file], output, options)

            # Should handle gracefully
            assert result.total_files == 1
            # Empty file might be considered successful with 0 records
            assert result.total_records == 0


class TestProgressCallback:
    """Test progress callback functionality."""

    def test_progress_callback_invoked(self):
        """Test that progress callback is invoked for each file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []
            for i in range(3):
                file_path = os.path.join(tmpdir, f'file{i}.csv')
                files.append(file_path)
                with open(file_path, 'w') as f:
                    f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                    f.write(f',,10/24/25,SELL,100,TEST{i},10.0\n')

            output = os.path.join(tmpdir, 'output.ndjson')

            progress_updates = []

            def callback(progress: FileProgress):
                progress_updates.append(progress)

            options = BatchOptions()
            process_multiple_files(files, output, options, progress_callback=callback)

            # Should have received progress updates
            assert len(progress_updates) > 0

            # Should have updates for all 3 files
            file_indices = set(p.file_index for p in progress_updates)
            assert 0 in file_indices
            assert 1 in file_indices
            assert 2 in file_indices

    def test_progress_callback_status_transitions(self):
        """Test that progress callback shows status transitions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.0\n')

            progress_updates = []

            def callback(progress: FileProgress):
                progress_updates.append(progress)

            options = BatchOptions()
            process_multiple_files([file1], output, options, progress_callback=callback)

            # Should see status progression
            statuses = [p.status for p in progress_updates]
            assert 'processing' in statuses or 'completed' in statuses


class TestRecordOrdering:
    """Test that record ordering is preserved."""

    def test_preserve_record_order_within_file(self):
        """Test that records maintain order within each file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,AAA,10.0\n')
                f.write(',,10/24/25,BUY,200,BBB,20.0\n')
                f.write(',,10/24/25,SELL,300,CCC,30.0\n')

            options = BatchOptions()
            process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Filter to data records only
            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]

            # Verify order is preserved
            symbols = [r.get('symbol') for r in data_records if r.get('symbol')]
            assert symbols == ['AAA', 'BBB', 'CCC']

    def test_file_order_preserved_in_output(self):
        """Test that files are processed in the order specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            file3 = os.path.join(tmpdir, 'file3.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            for i, file_path in enumerate([file1, file2, file3], 1):
                with open(file_path, 'w') as f:
                    f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                    f.write(f',,10/24/25,SELL,{i}00,FILE{i},10.0\n')

            options = BatchOptions()
            process_multiple_files([file1, file2, file3], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Get data records in order
            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]

            # Files should appear in order
            symbols = [r.get('symbol') for r in data_records if r.get('symbol')]
            assert symbols == ['FILE1', 'FILE2', 'FILE3']


class TestBatchOptions:
    """Test that batch options are properly applied."""

    def test_include_rolling_option(self):
        """Test that include_rolling option is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write('Rolling Strategies\n')
                f.write('Covered Call Position,New Exp,Call By\n')
                f.write('Position1,10/25/25,Data\n')

            options = BatchOptions(include_rolling=True)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Should have some records
            assert len(records) > 0

    def test_max_rows_option(self):
        """Test that max_rows option limits records per file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                for i in range(10):
                    f.write(f',,10/24/25,SELL,{i},TEST{i},10.0\n')

            options = BatchOptions(max_rows=3)  # Limit to 3 rows
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Should have limited records (header + limited data)
            assert len(records) <= 3


class TestProcessSingleFileForBatch:
    """Test the helper function for processing single files."""

    def test_adds_source_file_metadata(self):
        """Test that source file metadata is added to records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'test.csv')

            with open(file1, 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.0\n')

            options = BatchOptions()
            records = process_single_file_for_batch(file1, 0, options)

            assert len(records) > 0
            for record in records:
                assert 'source_file' in record
                assert record['source_file'] == 'test.csv'
                assert 'source_file_index' in record
                assert record['source_file_index'] == 0
