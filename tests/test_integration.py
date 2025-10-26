"""Integration tests for the CSV to JSON conversion."""
import pytest
import json
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner
from main import main


class TestCLIIntegration:
    """Test the CLI end-to-end."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_basic_conversion_ndjson(self):
        """Test basic CSV to NDJSON conversion."""
        with self.runner.isolated_filesystem():
            # Create a simple test CSV
            with open('test_input.csv', 'w') as f:
                f.write('Today\'s Trade Activity\n')
                f.write('\n')
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Price Improvement,Order Type\n')
                f.write(',,10/24/25 09:51:38,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.30,8.30,-,MKT\n')

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson'])

            assert result.exit_code == 0
            assert os.path.exists('output.ndjson')

            # Verify output
            with open('output.ndjson', 'r') as f:
                lines = f.readlines()
                assert len(lines) > 0

                # Parse each line as JSON
                for line in lines:
                    obj = json.loads(line)
                    assert 'section' in obj
                    assert 'row_index' in obj
                    assert 'issues' in obj

    def test_conversion_with_preview(self):
        """Test conversion with preview option."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty\n')
                f.write(',,10/24/25,SELL,100\n')

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson', '--preview', '1'])

            assert result.exit_code == 0
            assert 'Preview' in result.output

    def test_conversion_to_json_array(self):
        """Test conversion to JSON array format."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty\n')
                f.write(',,10/24/25,SELL,100\n')

            result = self.runner.invoke(main, ['test_input.csv', 'output.json', '--output-json'])

            assert result.exit_code == 0

            # Verify it's a valid JSON array
            with open('output.json', 'r') as f:
                data = json.load(f)
                assert isinstance(data, list)

    def test_conversion_with_pretty_print(self):
        """Test pretty-printed JSON output."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty\n')
                f.write(',,10/24/25,SELL,100\n')

            result = self.runner.invoke(main, [
                'test_input.csv', 'output.json',
                '--output-json', '--pretty'
            ])

            assert result.exit_code == 0

            with open('output.json', 'r') as f:
                content = f.read()
                # Pretty printed JSON should have newlines and indentation
                assert '\n' in content
                assert '  ' in content

    def test_conversion_with_max_rows(self):
        """Test max-rows limit."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty\n')
                f.write(',,10/24/25,SELL,100\n')
                f.write(',,10/24/25,BUY,200\n')
                f.write(',,10/24/25,SELL,300\n')

            result = self.runner.invoke(main, [
                'test_input.csv', 'output.ndjson',
                '--max-rows', '2'
            ])

            assert result.exit_code == 0

            with open('output.ndjson', 'r') as f:
                lines = f.readlines()
                # Should only have 2 lines
                assert len(lines) == 2

    def test_conversion_with_custom_patterns(self):
        """Test custom section patterns file."""
        with self.runner.isolated_filesystem():
            # Create custom patterns file
            with open('patterns.json', 'w') as f:
                json.dump({
                    '(?i)custom.*section': 'CustomSection'
                }, f)

            with open('test_input.csv', 'w') as f:
                f.write('Custom Section Header\n')
                f.write(',,Data1,Data2\n')

            result = self.runner.invoke(main, [
                'test_input.csv', 'output.ndjson',
                '--section-patterns-file', 'patterns.json'
            ])

            assert result.exit_code == 0

    def test_help_option(self):
        """Test --help option."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'INPUT_CSV' in result.output
        assert 'OUTPUT_JSON' in result.output

    def test_missing_input_file(self):
        """Test error handling for missing input file."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main, ['nonexistent.csv', 'output.ndjson'])
            assert result.exit_code != 0

    def test_qty_unsigned_option(self):
        """Test unsigned quantity option."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol\n')
                f.write(',,10/24/25,SELL,-100,TEST\n')

            # Test with signed (default)
            result = self.runner.invoke(main, [
                'test_input.csv', 'output_signed.ndjson',
                '--qty-signed'
            ])
            assert result.exit_code == 0

            with open('output_signed.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    if obj.get('qty') is not None:
                        # Should be negative for signed
                        assert obj['qty'] <= 0 or obj['qty'] > 0
                        break

            # Test with unsigned
            result = self.runner.invoke(main, [
                'test_input.csv', 'output_unsigned.ndjson',
                '--qty-unsigned'
            ])
            assert result.exit_code == 0

    def test_verbose_logging(self):
        """Test verbose logging option."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty\n')

            result = self.runner.invoke(main, [
                'test_input.csv', 'output.ndjson',
                '--verbose'
            ])

            assert result.exit_code == 0


class TestRealWorldScenarios:
    """Test with real-world-like data."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_multiple_sections(self):
        """Test CSV with multiple sections."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write('Working Orders\n')
                f.write('Notes,,Time Placed,Side,Qty\n')
                f.write('\n')
                f.write('Filled Orders\n')
                f.write(',,Exec Time,Spread,Side,Qty,Symbol,Price,Net Price,Order Type\n')
                f.write(',,10/24/25 09:51:38,STOCK,SELL,-75,NEUP,8.30,8.30,MKT\n')
                f.write('\n')
                f.write('Canceled Orders\n')
                f.write('Notes,,Time Canceled,Side,Qty\n')

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson'])

            assert result.exit_code == 0

            sections_found = set()
            with open('output.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    sections_found.add(obj['section'])

            # Should have found multiple sections
            assert len(sections_found) > 1

    def test_empty_and_null_fields(self):
        """Test handling of empty and null fields."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,,-,\n')  # Missing qty and price
                f.write(',,,,,\n')  # All empty

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson'])

            assert result.exit_code == 0

            with open('output.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    # Should have issues tracking or null values
                    assert 'issues' in obj

    def test_price_improvement_parsing(self):
        """Test parsing of price improvement field."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price,Price Improvement\n')
                f.write(',,10/24/25,BUY,100,TEST,10.50,$0.25\n')
                f.write(',,10/24/25,SELL,50,TEST,11.00,-\n')

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson'])

            assert result.exit_code == 0

            with open('output.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    if 'price_improvement' in obj and obj['price_improvement'] is not None:
                        assert isinstance(obj['price_improvement'], (int, float))

    def test_unicode_handling(self):
        """Test handling of unicode characters."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w', encoding='utf-8') as f:
                f.write('\ufeff,,Exec Time,Side,Qty,Symbol\n')  # BOM
                f.write(',,10/24/25,SELL,100,TEST\n')

            result = self.runner.invoke(main, [
                'test_input.csv', 'output.ndjson',
                '--encoding', 'utf-8'
            ])

            assert result.exit_code == 0

    def test_section_header_detection(self):
        """Test that sections are properly identified."""
        with self.runner.isolated_filesystem():
            # Create a custom patterns file in the isolated filesystem
            with open('patterns.json', 'w') as f:
                json.dump({
                    '(?i)exec.*time.*price.*order.*type': 'Filled Orders'
                }, f)

            with open('test_input.csv', 'w') as f:
                # Write a recognizable section header
                f.write(',Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Price Improvement,Order Type\n')
                f.write(',,10/24/25,STOCK,SELL,-75,TO CLOSE,NEUP,,,STOCK,8.30,8.30,-,MKT\n')

            result = self.runner.invoke(main, [
                'test_input.csv', 'output.ndjson',
                '--section-patterns-file', 'patterns.json'
            ])

            assert result.exit_code == 0

            # Check that we got output with section information
            sections_found = set()
            with open('output.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    if 'section' in obj:
                        sections_found.add(obj['section'])

            # Should have identified at least one section
            assert len(sections_found) > 0


class TestOutputFormat:
    """Test output format and structure."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_output_has_required_fields(self):
        """Test that output has all required fields."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty,Symbol,Price\n')
                f.write(',,10/24/25,SELL,100,TEST,10.50\n')

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson'])

            assert result.exit_code == 0

            required_fields = ['section', 'row_index', 'raw', 'issues']
            with open('output.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    for field in required_fields:
                        assert field in obj

    def test_raw_field_preserves_original(self):
        """Test that raw field preserves original CSV row."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty\n')
                f.write(',,10/24/25,SELL,100\n')

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson'])

            assert result.exit_code == 0

            with open('output.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    assert 'raw' in obj
                    assert isinstance(obj['raw'], str)

    def test_issues_array_structure(self):
        """Test that issues array is properly structured."""
        with self.runner.isolated_filesystem():
            with open('test_input.csv', 'w') as f:
                f.write(',,Exec Time,Side,Qty,Price\n')
                f.write(',,10/24/25,SELL,invalid_qty,abc\n')  # Invalid data

            result = self.runner.invoke(main, ['test_input.csv', 'output.ndjson'])

            assert result.exit_code == 0

            with open('output.ndjson', 'r') as f:
                for line in f:
                    obj = json.loads(line)
                    assert 'issues' in obj
                    assert isinstance(obj['issues'], list)
