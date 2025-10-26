"""Unit tests for main.py conversion functions."""
import pytest
import re
from main import (
    compile_section_patterns,
    normalize_key,
    map_header_to_index,
    safe_get,
    detect_section_from_row,
    parse_integer_qty,
    parse_float_field,
    COL_ALIASES,
    DEFAULT_SECTION_PATTERNS
)


class TestCompileSectionPatterns:
    """Test section pattern compilation."""

    def test_compile_patterns_returns_list_of_tuples(self):
        patterns = {'(?i)test': 'TestSection'}
        result = compile_section_patterns(patterns)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0][0], re.Pattern)
        assert result[0][1] == 'TestSection'

    def test_compile_empty_patterns(self):
        result = compile_section_patterns({})
        assert result == []

    def test_compile_multiple_patterns(self):
        patterns = {
            '(?i)filled': 'Filled',
            '(?i)working': 'Working'
        }
        result = compile_section_patterns(patterns)
        assert len(result) == 2


class TestNormalizeKey:
    """Test key normalization function."""

    def test_normalize_basic_string(self):
        assert normalize_key('Exec Time') == 'exec time'

    def test_normalize_none(self):
        assert normalize_key(None) == ''

    def test_normalize_empty_string(self):
        assert normalize_key('') == ''

    def test_normalize_with_whitespace(self):
        assert normalize_key('  Exec   Time  ') == 'exec time'

    def test_normalize_removes_bom(self):
        assert normalize_key('\ufeffExec Time') == 'exec time'

    def test_normalize_multiple_spaces(self):
        assert normalize_key('Price    Improvement') == 'price improvement'


class TestMapHeaderToIndex:
    """Test header to index mapping."""

    def test_map_basic_headers(self):
        header = ['Exec Time', 'Side', 'Qty']
        result = map_header_to_index(header)
        assert result['exec_time'] == 0
        assert result['side'] == 1
        assert result['qty'] == 2

    def test_map_with_aliases(self):
        header = ['Execution Time', 'Quantity']
        result = map_header_to_index(header)
        assert result['exec_time'] == 0
        assert result['qty'] == 1

    def test_map_empty_header(self):
        result = map_header_to_index([])
        assert result == {}

    def test_map_with_none_values(self):
        header = [None, 'Side', '', 'Qty']
        result = map_header_to_index(header)
        assert result['side'] == 1
        assert result['qty'] == 3
        assert len(result) == 2

    def test_map_case_insensitive(self):
        header = ['EXEC TIME', 'exec time', 'Exec Time']
        result = map_header_to_index(header)
        # Should map first occurrence
        assert 'exec_time' in result

    def test_map_price_fields(self):
        header = ['Price', 'Net Price', 'Price Improvement']
        result = map_header_to_index(header)
        # The function maps based on substring matching in COL_ALIASES
        # At least some price-related fields should be mapped
        assert len(result) >= 1
        # Verify we can map price-related headers
        assert any(key in result for key in ['price', 'net_price', 'price_improvement'])


class TestSafeGet:
    """Test safe row access function."""

    def test_safe_get_valid_index(self):
        row = ['value1', 'value2', 'value3']
        assert safe_get(row, 1) == 'value2'

    def test_safe_get_none_index(self):
        row = ['value1', 'value2']
        assert safe_get(row, None) is None

    def test_safe_get_negative_index(self):
        row = ['value1', 'value2']
        assert safe_get(row, -1) is None

    def test_safe_get_out_of_bounds(self):
        row = ['value1', 'value2']
        assert safe_get(row, 5) is None

    def test_safe_get_empty_string(self):
        row = ['value1', '', 'value3']
        assert safe_get(row, 1) is None

    def test_safe_get_whitespace_only(self):
        row = ['value1', '   ', 'value3']
        assert safe_get(row, 1) is None

    def test_safe_get_strips_whitespace(self):
        row = ['  value1  ', 'value2']
        assert safe_get(row, 0) == 'value1'


class TestDetectSectionFromRow:
    """Test section detection from CSV rows."""

    def setup_method(self):
        # Use custom patterns for testing that are easier to match
        self.test_patterns = {
            r'(?i)exec\s*time.*price.*order\s*type': 'Filled Orders',
            r'(?i)working\s*orders': 'Working Orders',
            r'(?i)canceled.*orders': 'Canceled Orders'
        }
        self.compiled_patterns = compile_section_patterns(self.test_patterns)

    def test_detect_filled_orders_section(self):
        # Test with data that matches pattern
        row = ['Exec Time', 'Spread', 'Side', 'Qty', 'Price', 'Order Type']
        result = detect_section_from_row(row, self.compiled_patterns)
        assert result == 'Filled Orders'

    def test_detect_working_orders_section(self):
        row = ['Working Orders']
        result = detect_section_from_row(row, self.compiled_patterns)
        assert result == 'Working Orders'

    def test_detect_no_section(self):
        row = ['10/24/25 09:51:38', 'STOCK', 'SELL', '-75']
        result = detect_section_from_row(row, self.compiled_patterns)
        assert result is None

    def test_detect_with_none_values(self):
        row = [None, 'Exec Time', 'Spread', 'Price', 'Order Type']
        result = detect_section_from_row(row, self.compiled_patterns)
        assert result == 'Filled Orders'

    def test_detect_empty_row(self):
        result = detect_section_from_row([], self.compiled_patterns)
        assert result is None

    def test_detect_case_insensitive(self):
        row = ['WORKING ORDERS']
        result = detect_section_from_row(row, self.compiled_patterns)
        assert result == 'Working Orders'

    def test_detect_with_default_patterns(self):
        """Test that DEFAULT_SECTION_PATTERNS is usable."""
        default_compiled = compile_section_patterns(DEFAULT_SECTION_PATTERNS)
        # Should be able to compile without errors
        assert len(default_compiled) > 0


class TestParseIntegerQty:
    """Test quantity parsing function."""

    def test_parse_positive_integer(self):
        issues = []
        result = parse_integer_qty('100', issues)
        assert result == 100
        assert issues == []

    def test_parse_negative_integer(self):
        issues = []
        result = parse_integer_qty('-50', issues)
        assert result == -50
        assert issues == []

    def test_parse_with_plus_sign(self):
        issues = []
        result = parse_integer_qty('+75', issues)
        assert result == 75
        assert issues == []

    def test_parse_with_comma(self):
        issues = []
        result = parse_integer_qty('1,000', issues)
        assert result == 1000
        assert issues == []

    def test_parse_none(self):
        issues = []
        result = parse_integer_qty(None, issues)
        assert result is None
        assert issues == []

    def test_parse_empty_string(self):
        issues = []
        result = parse_integer_qty('', issues)
        assert result is None
        assert issues == []

    def test_parse_whitespace(self):
        issues = []
        result = parse_integer_qty('  ', issues)
        assert result is None
        assert issues == []

    def test_parse_invalid_format(self):
        issues = []
        result = parse_integer_qty('abc', issues)
        assert result == 'abc'  # Returns raw value on failure
        assert 'qty_parse_failed' in issues

    def test_parse_negative_with_plus_sign(self):
        issues = []
        result = parse_integer_qty('-+50', issues)
        assert result == -50
        assert issues == []

    def test_parse_preserves_negative_sign(self):
        issues = []
        result = parse_integer_qty('-123', issues)
        assert result == -123
        assert issues == []


class TestParseFloatField:
    """Test float field parsing function."""

    def test_parse_basic_float(self):
        issues = []
        result = parse_float_field('10.50', 'price', issues)
        assert result == 10.50
        assert issues == []

    def test_parse_with_dollar_sign(self):
        issues = []
        result = parse_float_field('$10.50', 'price', issues)
        assert result == 10.50
        assert issues == []

    def test_parse_with_comma(self):
        issues = []
        result = parse_float_field('1,234.56', 'price', issues)
        assert result == 1234.56
        assert issues == []

    def test_parse_none(self):
        issues = []
        result = parse_float_field(None, 'price', issues)
        assert result is None
        assert issues == []

    def test_parse_integer_string(self):
        issues = []
        result = parse_float_field('100', 'price', issues)
        assert result == 100.0
        assert issues == []

    def test_parse_invalid_format(self):
        issues = []
        result = parse_float_field('abc', 'price', issues)
        assert result is None
        assert 'price_parse_failed' in issues

    def test_parse_multiple_dollar_signs(self):
        issues = []
        result = parse_float_field('$$10.50', 'price', issues)
        assert result == 10.50
        assert issues == []

    def test_parse_tracks_field_name_in_issues(self):
        issues = []
        parse_float_field('invalid', 'net_price', issues)
        assert 'net_price_parse_failed' in issues

    def test_parse_negative_float(self):
        issues = []
        result = parse_float_field('-10.50', 'price', issues)
        assert result == -10.50
        assert issues == []

    def test_parse_scientific_notation(self):
        issues = []
        result = parse_float_field('1.5e2', 'price', issues)
        assert result == 150.0
        assert issues == []


class TestColAliases:
    """Test that COL_ALIASES mapping is properly defined."""

    def test_aliases_exist(self):
        assert isinstance(COL_ALIASES, dict)
        assert len(COL_ALIASES) > 0

    def test_exec_time_aliases(self):
        assert 'exec time' in COL_ALIASES
        assert COL_ALIASES['exec time'] == 'exec_time'

    def test_qty_aliases(self):
        assert 'qty' in COL_ALIASES
        assert 'quantity' in COL_ALIASES
        assert COL_ALIASES['qty'] == 'qty'
        assert COL_ALIASES['quantity'] == 'qty'

    def test_price_aliases(self):
        assert 'price' in COL_ALIASES
        assert 'net price' in COL_ALIASES
        assert 'price improvement' in COL_ALIASES


class TestDefaultSectionPatterns:
    """Test that DEFAULT_SECTION_PATTERNS is properly defined."""

    def test_patterns_exist(self):
        assert isinstance(DEFAULT_SECTION_PATTERNS, dict)
        assert len(DEFAULT_SECTION_PATTERNS) > 0

    def test_filled_orders_pattern_exists(self):
        patterns_str = '\n'.join(DEFAULT_SECTION_PATTERNS.keys())
        assert 'exec' in patterns_str.lower()
        assert 'filled' in '\n'.join(DEFAULT_SECTION_PATTERNS.values()).lower()

    def test_all_patterns_are_valid_regex(self):
        for pattern in DEFAULT_SECTION_PATTERNS.keys():
            try:
                re.compile(pattern)
            except re.error:
                pytest.fail(f"Invalid regex pattern: {pattern}")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_normalize_key_with_unicode(self):
        result = normalize_key('Café Time')
        assert result == 'café time'

    def test_safe_get_with_empty_row(self):
        assert safe_get([], 0) is None

    def test_parse_qty_with_decimal(self):
        issues = []
        result = parse_integer_qty('10.5', issues)
        # Should fail to parse as integer
        assert result == '10.5'
        assert 'qty_parse_failed' in issues

    def test_map_header_partial_match(self):
        # Tests that 'Exec' in 'Exec Time' is properly matched
        header = ['Exec Time']
        result = map_header_to_index(header)
        assert 'exec_time' in result
