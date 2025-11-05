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
            records, sections_skipped = process_single_file_for_batch(file1, 0, options)

            assert len(records) > 0
            for record in records:
                assert 'source_file' in record
                assert record['source_file'] == 'test.csv'
                assert 'source_file_index' in record
                assert record['source_file_index'] == 0


class TestEmptySectionFiltering:
    """Test filtering of empty sections (header-only sections)."""

    def test_skip_empty_section_header_only(self):
        """Test that sections with only headers are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                # Empty section (header only)
                f.write('Working Orders\n')
                f.write('Notes,,Time Placed,Side,Qty,Symbol\n')
                f.write('\n')  # Empty row
                # Non-empty section (header + data)
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.0\n')

            options = BatchOptions(skip_empty_sections=True)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Should only have records from Filled Orders section
            sections = set(r.get('section') for r in records)
            assert 'Filled Orders' in sections
            assert 'Working Orders' not in sections

    def test_include_section_with_data_rows(self):
        """Test that sections with data rows after header are included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST1,10.0\n')
                f.write(',,10/24/25,BUY,200,TEST2,20.0\n')

            options = BatchOptions(skip_empty_sections=True)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Should have records from Filled Orders
            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            assert len(data_records) >= 2

    def test_include_empty_sections_flag(self):
        """Test that --include-empty-sections flag preserves empty sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                # Empty section
                f.write('Working Orders\n')
                f.write('Notes,,Time Placed,Side,Qty,Symbol\n')
                f.write('\n')
                # Non-empty section
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.0\n')

            options = BatchOptions(skip_empty_sections=False)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Should have section headers from both sections
            sections = set(r.get('section') for r in records)
            assert 'Filled Orders' in sections
            assert 'Working Orders' in sections

    def test_multiple_empty_sections_skipped(self):
        """Test that multiple empty sections are all skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                # Empty section 1
                f.write('Working Orders\n')
                f.write('Notes,,Time Placed,Side,Qty\n')
                f.write('\n')
                # Empty section 2
                f.write('Canceled Orders\n')
                f.write('Notes,,Time Canceled,Side,Qty\n')
                f.write('\n')
                # Non-empty section
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.0\n')

            options = BatchOptions(skip_empty_sections=True)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Should only have Filled Orders
            sections = set(r.get('section') for r in records)
            assert 'Filled Orders' in sections
            assert 'Working Orders' not in sections
            assert 'Canceled Orders' not in sections

    def test_empty_section_stats_tracked(self):
        """Test that skipped empty sections are tracked in statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                # 2 empty sections
                f.write('Working Orders\n')
                f.write('Notes,,Time Placed,Side,Qty\n')
                f.write('\n')
                f.write('Canceled Orders\n')
                f.write('Notes,,Time Canceled,Side,Qty\n')
                f.write('\n')
                # 1 non-empty section
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.0\n')

            options = BatchOptions(skip_empty_sections=True)
            result = process_multiple_files([file1], output, options)

            # Should track skipped sections
            assert hasattr(result, 'sections_skipped')
            assert result.sections_skipped == 2


class TestSectionGrouping:
    """Test grouping records by section across files."""

    def test_group_records_by_section_from_multiple_files(self):
        """Test that records from multiple files are grouped by section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            # File 1: Filled Orders
            with open(file1, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 10:00:00,SELL,100,AAA,10.0\n')

            # File 2: Filled Orders
            with open(file2, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 09:00:00,BUY,200,BBB,20.0\n')

            options = BatchOptions(group_by_section=True)
            result = process_multiple_files([file1, file2], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # All records should be from Filled Orders
            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            sections = [r.get('section') for r in data_records]
            assert all(s == 'Filled Orders' for s in sections)

    def test_section_order_deterministic(self):
        """Test that section order is deterministic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                # Multiple sections in file
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST1,10.0\n')
                f.write('\n')
                f.write('Canceled Orders\n')
                f.write('Notes,,Time Canceled,Side,Qty,Symbol\n')
                f.write(',,10/24/25,BUY,200,TEST2\n')

            options = BatchOptions(group_by_section=True)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Get sections in order
            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            sections = [r.get('section') for r in data_records]

            # Should be grouped (either all Filled first or all Canceled first, but grouped)
            if sections[0] == 'Filled Orders':
                # All Filled Orders should come before Canceled Orders
                first_canceled_idx = next((i for i, s in enumerate(sections) if s == 'Canceled Orders'), len(sections))
                filled_sections = sections[:first_canceled_idx]
                assert all(s == 'Filled Orders' for s in filled_sections)
            else:
                # All Canceled Orders should come before Filled Orders
                first_filled_idx = next((i for i, s in enumerate(sections) if s == 'Filled Orders'), len(sections))
                canceled_sections = sections[:first_filled_idx]
                assert all(s == 'Canceled Orders' for s in canceled_sections)

    def test_preserve_source_file_metadata_after_grouping(self):
        """Test that source file metadata is preserved after grouping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST1,10.0\n')

            with open(file2, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,BUY,200,TEST2,20.0\n')

            options = BatchOptions(group_by_section=True)
            result = process_multiple_files([file1, file2], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]

            # Check that source_file metadata is preserved
            assert any(r['source_file'] == 'file1.csv' for r in data_records)
            assert any(r['source_file'] == 'file2.csv' for r in data_records)
            assert all('source_file_index' in r for r in data_records)

    def test_preserve_file_order_flag(self):
        """Test that --preserve-file-order flag disables grouping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            # File 1: Filled Orders at 10:00
            with open(file1, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 10:00:00,SELL,100,FILE1,10.0\n')

            # File 2: Filled Orders at 09:00
            with open(file2, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 09:00:00,BUY,200,FILE2,20.0\n')

            options = BatchOptions(group_by_section=False)  # Preserve file order
            result = process_multiple_files([file1, file2], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            symbols = [r['symbol'] for r in data_records if r.get('symbol')]

            # Should be in file order (FILE1 before FILE2)
            assert symbols == ['FILE1', 'FILE2']


class TestTimeSorting:
    """Test time-based sorting within sections."""

    def test_sort_records_by_exec_time(self):
        """Test that records within a section are sorted by exec_time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            # File 1: Later time
            with open(file1, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 10:00:00,SELL,100,LATER,10.0\n')

            # File 2: Earlier time
            with open(file2, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 09:00:00,BUY,200,EARLIER,20.0\n')

            options = BatchOptions(group_by_section=True)
            result = process_multiple_files([file1, file2], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            symbols = [r['symbol'] for r in data_records if r.get('symbol')]

            # Should be sorted by time: EARLIER before LATER
            assert symbols == ['EARLIER', 'LATER']

    def test_records_with_no_time_at_end(self):
        """Test that records with no time field appear at end of section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 10:00:00,SELL,100,WITH_TIME,10.0\n')
                # Row with missing time (will be null)
                f.write(',,~,BUY,200,NO_TIME,20.0\n')

            options = BatchOptions(group_by_section=True)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            symbols = [r['symbol'] for r in data_records if r.get('symbol')]

            # Records with time should come first
            assert symbols[0] == 'WITH_TIME'
            # Records without time should be at end
            assert symbols[-1] == 'NO_TIME'

    def test_section_headers_stay_at_beginning(self):
        """Test that section header records stay at beginning of section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            file2 = os.path.join(tmpdir, 'file2.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            # File 1: Later time
            with open(file1, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 10:00:00,SELL,100,LATER,10.0\n')

            # File 2: Earlier time
            with open(file2, 'w') as f:
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 09:00:00,BUY,200,EARLIER,20.0\n')

            options = BatchOptions(group_by_section=True)
            result = process_multiple_files([file1, file2], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # First record should be a section header
            assert records[0].get('section') == 'Filled Orders'
            assert 'section_header' in records[0].get('issues', [])

            # Data records should follow, sorted by time
            data_records = [r for r in records[1:] if 'section_header' not in r.get('issues', [])]
            symbols = [r['symbol'] for r in data_records if r.get('symbol')]
            assert symbols == ['EARLIER', 'LATER']

    def test_mixed_time_fields_handled(self):
        """Test handling of different time fields (exec_time, time_canceled, time_placed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, 'file1.csv')
            output = os.path.join(tmpdir, 'output.ndjson')

            with open(file1, 'w') as f:
                # Mix of different sections with different time fields
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25 12:00:00,SELL,100,FILLED_NOON,10.0\n')
                f.write('\n')
                f.write('Canceled Orders\n')
                f.write('Notes,,Time Canceled,Side,Qty,Symbol\n')
                f.write(',,10/24/25 11:00:00,BUY,200,CANCELED_11AM\n')

            options = BatchOptions(group_by_section=True)
            result = process_multiple_files([file1], output, options)

            with open(output, 'r') as f:
                records = [json.loads(line) for line in f]

            # Should handle both time fields correctly
            data_records = [r for r in records if 'section_header' not in r.get('issues', [])]
            assert len(data_records) >= 2
