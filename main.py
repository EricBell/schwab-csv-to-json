#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert Schwab CSV trade activity reports to JSON/NDJSON format."""

import click
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Column alias mapping - maps normalized header names to canonical field names
COL_ALIASES = {
    # exec_time aliases
    'exec time': 'exec_time',
    'execution time': 'exec_time',
    'time': 'exec_time',

    # time_canceled aliases
    'time canceled': 'time_canceled',
    'time cancelled': 'time_canceled',

    # time_placed aliases
    'time placed': 'time_placed',

    # spread
    'spread': 'spread',

    # side
    'side': 'side',

    # qty aliases
    'qty': 'qty',
    'quantity': 'qty',

    # pos_effect aliases
    'pos effect': 'pos_effect',
    'position effect': 'pos_effect',

    # symbol
    'symbol': 'symbol',

    # exp aliases
    'exp': 'exp',
    'expiration': 'exp',

    # strike
    'strike': 'strike',

    # type aliases
    'type': 'type',
    'right': 'type',
    'option type': 'type',

    # price aliases
    'price': 'price',
    'exec price': 'price',
    'limit price': 'price',

    # net_price aliases
    'net price': 'net_price',
    'net price ': 'net_price',

    # price_improvement aliases
    'price improvement': 'price_improvement',
    'price impr': 'price_improvement',

    # order_type aliases
    'order type': 'order_type',
    'ordertype': 'order_type',
    'order type ': 'order_type',

    # tif aliases
    'tif': 'tif',
    'time in force': 'tif',

    # status
    'status': 'status',

    # notes
    'notes': 'notes',

    # mark
    'mark': 'mark',
}

# Default section detection patterns
DEFAULT_SECTION_PATTERNS = {
    # Full header patterns (most specific first)
    r'(?i)^,Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Price Improvement,Order Type': 'Filled Orders',
    r'(?i)^Notes,,Time Canceled,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,,TIF,Status': 'Canceled Orders',

    # Standalone section names
    r'(?i)^Working Orders\s*$': 'Working Orders',
    r'(?i)^Filled Orders\s*$': 'Filled Orders',
    r'(?i)^Canceled Orders\s*$': 'Canceled Orders',
    r'(?i)^Cancelled Orders\s*$': 'Canceled Orders',  # Alternative spelling
    r'(?i)^Rolling Strategies\s*$': 'Rolling Strategies',

    # Section names with leading comma
    r'(?i)^,Working Orders': 'Working Orders',
    r'(?i)^,Rolling Strategies': 'Rolling Strategies',
}

# Regex patterns
AMEND_REF_RE = re.compile(r'^RE\s*#\s*(\d+)', re.IGNORECASE)
MONTH_MAP = {
    'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06',
    'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
}


def compile_section_patterns(patterns: Dict[str, str]) -> List[Tuple[re.Pattern, str]]:
    """
    Compile section pattern dictionary to list of (regex, section_name) tuples.

    Args:
        patterns: Dict mapping regex patterns to section names

    Returns:
        List of (compiled_pattern, section_name) tuples
    """
    result = []
    for pattern_str, section_name in patterns.items():
        compiled = re.compile(pattern_str)
        result.append((compiled, section_name))
    return result


def normalize_key(s: Optional[str]) -> str:
    """
    Normalize header key to lowercase with spaces.

    Args:
        s: Header string to normalize

    Returns:
        Normalized lowercase string with single spaces, BOM removed
    """
    if s is None:
        return ''
    # Remove BOM if present
    s = s.replace('\ufeff', '')
    s = s.strip()
    # Collapse multiple spaces to single space
    s = re.sub(r'\s+', ' ', s)
    return s.lower()


def map_header_to_index(header: List[str], col_aliases: Dict[str, str] = None) -> Dict[str, int]:
    """
    Map header row to dict of {canonical_key: column_index}.

    Args:
        header: List of header column names
        col_aliases: Column aliases dict (defaults to COL_ALIASES)

    Returns:
        Dict mapping canonical keys to column indices
    """
    if col_aliases is None:
        col_aliases = COL_ALIASES

    result = {}

    for idx, header_val in enumerate(header):
        if not header_val or not header_val.strip():
            continue

        normalized = normalize_key(header_val)

        # Look up canonical key from alias
        if normalized in col_aliases:
            canonical_key = col_aliases[normalized]
            # Only map first occurrence
            if canonical_key not in result:
                result[canonical_key] = idx

    return result


def safe_get(cells: List[str], index: Optional[int], default=None) -> Optional[str]:
    """
    Safely get cell value by index, treating null markers as None.

    Args:
        cells: List of cell values
        index: Column index to retrieve
        default: Default value if index invalid

    Returns:
        Cell value or None
    """
    if index is None or index < 0:
        return None
    if index >= len(cells):
        return None

    value = cells[index]
    if not value or not value.strip():
        return None

    value = value.strip()

    # Treat ~ and - as null markers
    if value in ('~', '-'):
        return None

    return value


def detect_section_from_row(cells: List[str], compiled_patterns: List[Tuple[re.Pattern, str]]) -> Optional[str]:
    """
    Detect section name from CSV row using compiled patterns.

    Args:
        cells: CSV row cells
        compiled_patterns: List of (pattern, section_name) tuples

    Returns:
        Section name if matched, else None
    """
    # Convert None values to empty strings for pattern matching
    safe_cells = ['' if cell is None else str(cell) for cell in cells]
    row_str = ','.join(safe_cells)

    for pattern, section_name in compiled_patterns:
        if pattern.search(row_str):
            return section_name

    return None


def parse_integer_qty(value: Optional[str], issues: List[str], unsigned: bool = False):
    """
    Parse quantity as integer with optional sign handling.

    Args:
        value: String value to parse
        issues: List to append parse issues to
        unsigned: If True, return absolute value

    Returns:
        Parsed integer, or raw value on parse failure, or None for empty
    """
    if not value:
        return None

    value = value.strip()
    if value in ('~', '-', ''):
        return None

    # Remove commas and handle -+ signs
    clean_value = value.replace(',', '').replace('-+', '-').replace('+-', '-')

    try:
        float_val = float(clean_value)
        # Check if it's actually an integer value
        if float_val.is_integer():
            num = int(float_val)
            return abs(num) if unsigned else num
        else:
            # Has decimal component, fail
            issues.append('qty_parse_failed')
            return value
    except (ValueError, TypeError):
        issues.append('qty_parse_failed')
        return value  # Return raw value on failure


def parse_float_field(value: Optional[str], field_name: str, issues: List[str]) -> Optional[float]:
    """
    Parse float field with $ and comma removal.

    Args:
        value: String value to parse
        field_name: Field name for error tracking
        issues: List to append parse issues to

    Returns:
        Parsed float or None
    """
    if not value:
        return None

    value = value.strip()
    if value in ('~', '-', ''):
        return None

    # Remove $ and commas
    value = value.replace('$', '').replace(',', '')

    # Handle leading decimal point
    if value.startswith('.') and value != '.':
        value = '0' + value

    try:
        return float(value)
    except (ValueError, TypeError):
        issues.append(f'{field_name}_parse_failed')
        return None


def parse_datetime_maybe(s: Optional[str]) -> Optional[str]:
    """Parse datetime string to ISO format."""
    if not s:
        return None
    s = s.strip()
    fmts = [
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.isoformat()
        except Exception:
            continue
    return None


def parse_exp_date(exp: Optional[str]) -> Optional[str]:
    """Parse option expiration date."""
    if not exp:
        return None
    exp = exp.strip().upper()
    m = re.match(r'^(\d{1,2})\s+([A-Z]{3})\s+(\d{2,4})$', exp)
    if not m:
        try:
            return datetime.strptime(exp, "%Y-%m-%d").date().isoformat()
        except Exception:
            return None
    day, mon3, yr = m.groups()
    mon = MONTH_MAP.get(mon3)
    if not mon:
        return None
    if len(yr) == 2:
        yr = ("20" + yr) if int(yr) <= 69 else ("19" + yr)
    return f"{yr}-{mon}-{int(day):02d}"


def classify_row(cells: List[str]) -> str:
    """
    Classify CSV row as noise, amendment, header, or data.

    Returns:
        'noise', 'amendment', 'header', or 'data'
    """
    if not cells or all((c.strip() == "" for c in cells)):
        return "noise"

    # Check for amendment row
    for c in cells:
        if AMEND_REF_RE.match(c.strip()):
            return "amendment"

    # Check for header row
    normalized = [normalize_key(c) for c in cells]
    joined = ','.join(normalized)

    # Header indicators
    has_time = any(t in joined for t in ['exec time', 'time canceled', 'time placed'])
    has_trade_cols = 'side' in joined and 'qty' in joined

    if has_time and has_trade_cols:
        return "header"

    return "data"


def build_order_record(
    section: str,
    header_map: Dict[str, int],
    cells: List[str],
    row_index: int,
    qty_unsigned: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Build order record from CSV row.

    Args:
        section: Section name
        header_map: Header mapping dict
        cells: CSV row cells
        row_index: Row index in file
        qty_unsigned: If True, quantities are unsigned

    Returns:
        Record dict with unified schema or None
    """
    issues = []

    # Extract fields using header map
    exec_time = safe_get(cells, header_map.get('exec_time'))
    time_canceled = safe_get(cells, header_map.get('time_canceled'))
    spread = safe_get(cells, header_map.get('spread'))
    side = safe_get(cells, header_map.get('side'))
    qty_str = safe_get(cells, header_map.get('qty'))
    pos_effect = safe_get(cells, header_map.get('pos_effect'))
    symbol = safe_get(cells, header_map.get('symbol'))
    exp = safe_get(cells, header_map.get('exp'))
    strike_str = safe_get(cells, header_map.get('strike'))
    type_str = safe_get(cells, header_map.get('type'))
    price_str = safe_get(cells, header_map.get('price'))
    net_price_str = safe_get(cells, header_map.get('net_price'))
    price_impr_str = safe_get(cells, header_map.get('price_improvement'))
    order_type = safe_get(cells, header_map.get('order_type'))
    tif = safe_get(cells, header_map.get('tif'))
    status = safe_get(cells, header_map.get('status'))
    notes = safe_get(cells, header_map.get('notes'))
    mark_str = safe_get(cells, header_map.get('mark'))

    # Normalize string fields
    if side:
        side = side.upper()
    if pos_effect:
        pos_effect = pos_effect.upper()
    if symbol:
        symbol = symbol.upper()
    if type_str:
        type_str = type_str.upper()
    if order_type:
        order_type = order_type.upper()
    if tif:
        tif = tif.upper()
    if status:
        status = status.upper()

    # Skip rows with no meaningful data
    if not side and not qty_str and not symbol and not type_str:
        return None

    # Parse numeric fields
    qty = parse_integer_qty(qty_str, issues, unsigned=qty_unsigned)
    price = parse_float_field(price_str, 'price', issues)
    net_price = parse_float_field(net_price_str, 'net_price', issues)
    price_improvement = parse_float_field(price_impr_str, 'price_improvement', issues)
    strike = parse_float_field(strike_str, 'strike', issues)
    mark = parse_float_field(mark_str, 'mark', issues)

    # Determine asset type
    asset_type = None
    if type_str in {'CALL', 'PUT'}:
        asset_type = 'OPTION'
    elif type_str == 'STOCK':
        asset_type = 'STOCK'
    elif type_str == 'ETF':
        asset_type = 'ETF'

    # Build option object
    option = None
    if asset_type == 'OPTION':
        option = {
            'exp_date': parse_exp_date(exp),
            'strike': strike,
            'right': type_str,
        }

    # Determine event type
    if section == 'Filled Orders':
        event_type = 'fill'
    elif section == 'Canceled Orders':
        event_type = 'cancel'
    elif section == 'Working Orders':
        event_type = 'working'
    else:
        event_type = 'other'

    # Build unified record with ALL fields
    record = {
        'section': section,  # Keep original section name
        'row_index': row_index,
        'raw': ','.join(cells),
        'issues': issues,

        # Time fields
        'exec_time': parse_datetime_maybe(exec_time),
        'time_canceled': parse_datetime_maybe(time_canceled),
        'time_placed': None,  # Not in order records

        # Trade fields
        'side': side,
        'qty': qty,
        'pos_effect': pos_effect,
        'symbol': symbol,

        # Option fields
        'exp': parse_exp_date(exp) if option else None,
        'strike': strike if option else None,
        'type': type_str,
        'spread': spread,

        # Price fields
        'price': price,
        'net_price': net_price,
        'price_improvement': price_improvement,

        # Order fields
        'order_type': order_type,
        'tif': tif,
        'status': status,

        # Other fields
        'notes': notes,
        'mark': mark,

        # Legacy fields (for backward compat)
        'event_type': event_type,
        'asset_type': asset_type,
        'option': option,
    }

    return record


def build_amendment_record(section: str, cells: List[str], row_index: int) -> Dict[str, Any]:
    """Build amendment record from RE # row."""
    issues = []
    ref = None
    stop_price = None
    order_type = None
    tif = None

    for c in cells:
        c_str = c.strip()
        m = AMEND_REF_RE.match(c_str)
        if m:
            ref = m.group(1)
            continue
        if stop_price is None and re.match(r'^\.?-?\d+(?:\.\d+)?$', c_str):
            stop_price = parse_float_field(c_str, 'stop_price', issues)
        if c_str.upper() in {'STP', 'STP LMT', 'LMT', 'MKT'}:
            order_type = c_str.upper()
        if c_str.upper() in {'DAY', 'GTC', 'STD'}:
            tif = c_str.upper()

    record = {
        'section': section,  # Keep original section name
        'row_index': row_index,
        'event_type': 'amend',
        'amendment': {
            'ref': ref,
            'stop_price': stop_price,
            'order_type': order_type,
            'tif': tif,
        },
        'raw': ','.join(cells),
        'issues': issues,
    }

    return record


def parse_file(
    path: str,
    include_rolling: bool = False,
    section_patterns: Dict[str, str] = None,
    max_rows: int = None,
    qty_unsigned: bool = False,
    verbose: bool = False,
    skip_empty_sections: bool = False
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Parse Schwab CSV file to records.

    Args:
        path: Path to CSV file
        include_rolling: Include Rolling Strategies section
        section_patterns: Custom section patterns dict
        max_rows: Max rows to process (for testing)
        qty_unsigned: Parse quantities as unsigned
        verbose: Enable verbose logging
        skip_empty_sections: Skip sections with only headers (no data rows)

    Returns:
        Tuple of (list of record dicts, count of skipped sections)
    """
    results = []
    section = 'Top'
    in_data = False
    current_header_map = None
    row_index = 0
    sections_skipped = 0

    # Buffering for empty section filtering
    buffered_section_header = None
    buffered_column_header = None
    buffered_header_map = None

    if section_patterns is None:
        section_patterns = DEFAULT_SECTION_PATTERNS

    compiled_patterns = compile_section_patterns(section_patterns)

    with open(path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if max_rows and row_index >= max_rows:
                break

            row_index += 1
            cells = [c for c in row]

            if verbose:
                click.echo(f"Row {row_index}: {cells[:3]}...", err=True)

            # Check for section header
            detected_section = detect_section_from_row(cells, compiled_patterns)
            if detected_section:
                # If we had buffered headers, they belong to an empty section
                if skip_empty_sections and buffered_section_header is not None:
                    sections_skipped += 1
                    if verbose:
                        click.echo(f"Skipping empty section: {buffered_section_header['section']}", err=True)

                section = detected_section
                in_data = False
                current_header_map = None
                buffered_header_map = None

                # Create section header record
                section_header_record = {
                    'section': section,  # Keep original section name
                    'row_index': row_index,
                    'raw': ','.join(cells),
                    'issues': ['section_header'],
                    # All other fields as None
                    'exec_time': None, 'time_canceled': None, 'time_placed': None,
                    'side': None, 'qty': None, 'pos_effect': None, 'symbol': None,
                    'exp': None, 'strike': None, 'type': None, 'spread': None,
                    'price': None, 'net_price': None, 'price_improvement': None,
                    'order_type': None, 'tif': None, 'status': None,
                    'notes': None, 'mark': None,
                }

                # Check if this row is ALSO a column header (some patterns match both)
                cls = classify_row(cells)
                if cls == 'header':
                    # This is both a section marker AND a column header
                    header_map = map_header_to_index(cells)

                    if skip_empty_sections:
                        # Buffer both headers
                        buffered_section_header = section_header_record
                        buffered_column_header = section_header_record  # Same record in this case
                        buffered_header_map = header_map
                    else:
                        # Emit immediately
                        results.append(section_header_record)
                        current_header_map = header_map
                        in_data = True
                else:
                    # Section marker only, no column header yet
                    if skip_empty_sections:
                        # Buffer section header
                        buffered_section_header = section_header_record
                        buffered_column_header = None
                        buffered_header_map = None
                    else:
                        # Emit immediately
                        results.append(section_header_record)

                continue

            # Skip Rolling Strategies if not included
            if section == 'Rolling Strategies' and not include_rolling:
                continue

            # Classify row
            cls = classify_row(cells)

            if cls == 'header':
                header_map = map_header_to_index(cells)

                # Create header record
                header_record = {
                    'section': section,  # Keep original section name
                    'row_index': row_index,
                    'raw': ','.join(cells),
                    'issues': ['section_header'],
                    # All other fields as None
                    'exec_time': None, 'time_canceled': None, 'time_placed': None,
                    'side': None, 'qty': None, 'pos_effect': None, 'symbol': None,
                    'exp': None, 'strike': None, 'type': None, 'spread': None,
                    'price': None, 'net_price': None, 'price_improvement': None,
                    'order_type': None, 'tif': None, 'status': None,
                    'notes': None, 'mark': None,
                }

                if skip_empty_sections:
                    # Buffer the column header
                    buffered_column_header = header_record
                    buffered_header_map = header_map
                else:
                    # Emit immediately
                    results.append(header_record)
                    current_header_map = header_map
                    in_data = True

                continue
            elif cls == 'noise':
                continue

            # Check if we have buffered headers to emit (this is a data row)
            if skip_empty_sections and buffered_section_header is not None:
                # Emit buffered section header
                results.append(buffered_section_header)
                buffered_section_header = None

            if skip_empty_sections and buffered_column_header is not None:
                # Emit buffered column header
                results.append(buffered_column_header)
                current_header_map = buffered_header_map
                in_data = True
                buffered_column_header = None
                buffered_header_map = None

            if not in_data or not current_header_map:
                continue

            if cls == 'amendment':
                results.append(build_amendment_record(section, cells, row_index))
                continue

            rec = build_order_record(section, current_header_map, cells, row_index, qty_unsigned)
            if rec:
                results.append(rec)

    # If we still have buffered headers at end of file, they belong to empty section
    if skip_empty_sections and buffered_section_header is not None:
        sections_skipped += 1
        if verbose:
            click.echo(f"Skipping empty section at end: {buffered_section_header['section']}", err=True)

    return results, sections_skipped


def validate(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Validate parsed records and return issue counts.

    Args:
        records: List of parsed records

    Returns:
        Dict of issue_type -> count
    """
    issues = {}

    def bump(k):
        issues[k] = issues.get(k, 0) + 1

    for r in records:
        # Skip section headers
        if 'section_header' in r.get('issues', []):
            continue

        et = r.get('event_type')
        if et == 'amend':
            if not r.get('amendment', {}).get('ref'):
                bump('amend_missing_ref')
            if r.get('amendment', {}).get('stop_price') is None:
                bump('amend_missing_stop_price')
            continue

        if not r.get('symbol'):
            bump('missing_symbol')
        if not r.get('side'):
            bump('missing_side')
        if r.get('qty') is None:
            bump('missing_qty')

        asset_type = r.get('asset_type')
        if asset_type == 'OPTION':
            opt = r.get('option') or {}
            if not opt.get('exp_date'):
                bump('option_missing_exp')
            if opt.get('strike') is None:
                bump('option_missing_strike')
            if opt.get('right') not in {'PUT', 'CALL'}:
                bump('option_missing_right')
        elif asset_type is None and et != 'amend':
            bump('unknown_asset_type')

    return issues


def normalize_path(path_str: str) -> Path:
    """
    Normalize file path to absolute, resolved path.

    Converts relative paths to absolute and resolves symlinks.

    Args:
        path_str: Path string to normalize

    Returns:
        Normalized Path object
    """
    return Path(path_str).resolve()


def validate_output_not_input(input_paths: List[str], output_path: str) -> Optional[str]:
    """
    Validate that output path doesn't overwrite any input file.

    Args:
        input_paths: List of input file paths
        output_path: Output file path

    Returns:
        Error message if collision detected, None if valid
    """
    output_normalized = normalize_path(output_path)
    input_normalized = [normalize_path(p) for p in input_paths]

    for input_path in input_normalized:
        if output_normalized == input_path:
            return (
                f"Error: Output file would overwrite input file\n"
                f"  Output: {output_path}\n"
                f"  Collides with input: {input_path}\n\n"
                f"Suggestion: Specify a different output file name:\n"
                f"  uv run python main.py convert [input files...] output.ndjson"
            )

    return None


def validate_csv_extension_warning(output_path: str) -> Optional[str]:
    """
    Warn if output file has .csv extension.

    Args:
        output_path: Output file path

    Returns:
        Warning message if .csv extension, None otherwise
    """
    if output_path.lower().endswith('.csv'):
        return (
            f"Warning: Output file has .csv extension\n"
            f"  This may cause confusion as the output is JSON/NDJSON format, not CSV.\n"
            f"  Recommended extensions: .ndjson, .json, .jsonl"
        )

    return None


def validate_input_files_exist(input_paths: List[str]) -> List[str]:
    """
    Validate that all input files exist.

    Args:
        input_paths: List of input file paths

    Returns:
        List of error messages for missing files
    """
    errors = []

    for path_str in input_paths:
        path = Path(path_str)
        if not path.exists():
            errors.append(f"Error: Input file does not exist: {path_str}")
        elif not path.is_file():
            errors.append(f"Error: Input path is not a file: {path_str}")

    return errors


def validate_output_directory(output_path: str) -> Optional[str]:
    """
    Validate that output directory exists and is writable.

    Args:
        output_path: Output file path

    Returns:
        Error message if directory invalid, None if valid
    """
    output = Path(output_path)
    parent_dir = output.parent

    # Handle current directory case
    if parent_dir == Path('.'):
        parent_dir = Path.cwd()

    if not parent_dir.exists():
        return (
            f"Error: Output directory does not exist: {parent_dir}\n"
            f"  Create the directory first or specify a different path."
        )

    if not parent_dir.is_dir():
        return f"Error: Output parent path is not a directory: {parent_dir}"

    # Check if directory is writable
    if not os.access(parent_dir, os.W_OK):
        return f"Error: Output directory is not writable: {parent_dir}"

    return None


def validate_file_paths(
    input_paths: List[str],
    output_path: str,
    force_overwrite: bool = False
) -> List[str]:
    """
    Validate all file paths before processing.

    Performs comprehensive validation:
    - Input files exist
    - Output directory exists and is writable
    - Output doesn't overwrite input (unless force_overwrite)
    - Warnings for .csv output extension

    Args:
        input_paths: List of input file paths
        output_path: Output file path
        force_overwrite: If True, skip output collision check

    Returns:
        List of error/warning messages (empty if all valid)
    """
    errors = []

    # Check input files exist
    errors.extend(validate_input_files_exist(input_paths))

    # Check output directory
    dir_error = validate_output_directory(output_path)
    if dir_error:
        errors.append(dir_error)

    # Check output doesn't overwrite input (unless forced)
    if not force_overwrite:
        collision_error = validate_output_not_input(input_paths, output_path)
        if collision_error:
            errors.append(collision_error)

    # Warn about .csv extension
    csv_warning = validate_csv_extension_warning(output_path)
    if csv_warning:
        errors.append(csv_warning)

    return errors


@click.group()
def cli():
    """Schwab CSV to JSON converter with TUI and CLI modes."""
    pass


@cli.command(name='convert')
@click.argument('input_csv', nargs=-1, required=True, type=click.Path(), metavar='INPUT_CSV...')
@click.argument('output_json', type=click.Path(), metavar='OUTPUT_JSON')
@click.option('--include-rolling', is_flag=True, help='Include Rolling Strategies section')
@click.option('--output-json', 'format_json', is_flag=True, help='Output as JSON array instead of NDJSON')
@click.option('--output-ndjson', is_flag=True, default=True, help='Output as NDJSON (default)')
@click.option('--pretty', is_flag=True, help='Pretty-print JSON arrays')
@click.option('--preview', type=int, metavar='N', help='Preview first N records after conversion')
@click.option('--section-patterns-file', type=click.Path(exists=True), help='Custom section patterns JSON file')
@click.option('--max-rows', type=int, metavar='N', help='Process only first N rows (for testing)')
@click.option('--qty-unsigned', is_flag=True, help='Parse quantities as unsigned (absolute values)')
@click.option('--qty-signed', is_flag=True, default=True, help='Parse quantities as signed (keep sign, default)')
@click.option('--skip-empty-sections/--include-empty-sections', default=True,
              help='Skip sections with no data rows (default: skip)')
@click.option('--group-by-section/--preserve-file-order', default=True,
              help='Group records by section across files and sort by time (default: group)')
@click.option('--force-overwrite', is_flag=True, help='Force overwrite without safety checks (use with caution)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--encoding', default='utf-8', help='CSV file encoding (default: utf-8)')
def convert(input_csv, output_json, include_rolling, format_json, output_ndjson, pretty,
         preview, section_patterns_file, max_rows, qty_unsigned, qty_signed,
         skip_empty_sections, group_by_section, force_overwrite, verbose, encoding):
    """
    Convert Schwab CSV trade activity reports to JSON/NDJSON format.

    Supports both single file and multi-file (batch) processing.

    INPUT_CSV: Path(s) to Schwab CSV file(s). Multiple files can be specified.
    OUTPUT_JSON: Path to output file (.ndjson or .json)

    Examples:
        Single file:  main.py input.csv output.ndjson
        Multiple files: main.py file1.csv file2.csv file3.csv output.ndjson
    """
    from batch import process_multiple_files, BatchOptions

    # Convert input_csv tuple to list
    input_files = list(input_csv)

    # Validate file paths before processing
    validation_errors = validate_file_paths(input_files, output_json, force_overwrite)

    if validation_errors:
        # Separate errors from warnings
        fatal_errors = [err for err in validation_errors if err.startswith("Error:")]
        warnings = [err for err in validation_errors if err.startswith("Warning:")]

        # Display all errors and warnings
        for error in fatal_errors:
            click.echo(click.style(error, fg='red', bold=True), err=True)

        for warning in warnings:
            click.echo(click.style(warning, fg='yellow'), err=True)

        # Exit if there are fatal errors
        if fatal_errors:
            click.echo("\nAbort: Cannot proceed due to validation errors.", err=True)
            sys.exit(1)

        # For warnings, ask for confirmation (unless force_overwrite is set)
        if warnings and not force_overwrite:
            if not click.confirm("\nDo you want to proceed anyway?", default=False):
                click.echo("Operation cancelled.", err=True)
                sys.exit(0)

    # Load custom section patterns if provided
    section_patterns = None
    if section_patterns_file:
        with open(section_patterns_file, 'r') as f:
            section_patterns = json.load(f)

    # Determine if we're in batch mode (multiple files)
    is_batch_mode = len(input_files) > 1

    if is_batch_mode:
        # Batch processing mode
        if verbose:
            click.echo(f"Batch processing {len(input_files)} files...", err=True)

        options = BatchOptions(
            include_rolling=include_rolling,
            section_patterns=section_patterns,
            max_rows=max_rows,
            qty_unsigned=qty_unsigned,
            verbose=verbose,
            skip_empty_sections=skip_empty_sections,
            group_by_section=group_by_section
        )

        # Progress callback for verbose mode
        def progress_callback(progress):
            if verbose:
                status_msg = f"[{progress.file_index + 1}/{progress.total_files}] "
                if progress.status == 'processing':
                    click.echo(f"{status_msg}Processing {Path(progress.file_path).name}...", err=True)
                elif progress.status == 'completed':
                    click.echo(f"{status_msg}Completed {Path(progress.file_path).name} ({progress.records_parsed} records)", err=True)
                elif progress.status == 'failed':
                    click.echo(f"{status_msg}Failed {Path(progress.file_path).name}: {progress.error}", err=True)

        result = process_multiple_files(
            input_files,
            output_json,
            options,
            progress_callback=progress_callback if verbose else None
        )

        validation_issues = result.validation_issues

        # Report batch results
        click.echo(f"Batch processing complete:", err=True)
        click.echo(f"  Files processed: {result.successful_files}/{result.total_files}", err=True)
        click.echo(f"  Total records: {result.total_records}", err=True)
        if result.sections_skipped > 0 and verbose:
            click.echo(f"  Sections skipped: {result.sections_skipped}", err=True)
        if result.failed_files > 0:
            click.echo(f"  Failed files: {result.failed_files}", err=True)
            for file_path, error in result.file_errors.items():
                click.echo(f"    - {Path(file_path).name}: {error}", err=True)

        # Load records for preview if requested
        records = []
        if preview:
            with open(output_json, 'r', encoding='utf-8') as f:
                for line in f:
                    records.append(json.loads(line))

    else:
        # Single file mode
        input_file = input_files[0]

        if verbose:
            click.echo(f"Parsing {input_file}...", err=True)

        records, sections_skipped = parse_file(
            input_file,
            include_rolling=include_rolling,
            section_patterns=section_patterns,
            max_rows=max_rows,
            qty_unsigned=qty_unsigned,
            verbose=verbose,
            skip_empty_sections=skip_empty_sections
        )

        # Validate records
        validation_issues = validate(records)

        if sections_skipped > 0 and verbose:
            click.echo(f"Skipped {sections_skipped} empty section(s)", err=True)

        # Write output
        if format_json or output_json.endswith('.json'):
            # JSON array format
            with open(output_json, 'w', encoding='utf-8') as out:
                if pretty:
                    json.dump(records, out, ensure_ascii=False, indent=2)
                else:
                    json.dump(records, out, ensure_ascii=False)
        else:
            # NDJSON format (default)
            with open(output_json, 'w', encoding='utf-8') as out:
                for r in records:
                    out.write(json.dumps(r, ensure_ascii=False) + '\n')

        click.echo(f"Parsed records: {len(records)}", err=True)

    # Print validation summary (for both modes)
    if validation_issues:
        click.echo("Validation issues:", err=True)
        for k, v in sorted(validation_issues.items()):
            click.echo(f"  - {k}: {v}", err=True)
    else:
        click.echo("No validation issues detected.", err=True)

    # Preview records if requested
    if preview:
        click.echo(f"\n=== Preview (first {preview} records) ===")
        for i, rec in enumerate(records[:preview]):
            click.echo(json.dumps(rec, ensure_ascii=False, indent=2))
            if i < preview - 1:
                click.echo()


@cli.command(name='tui')
@click.option('--dir', 'starting_dir', default='.', help='Starting directory for file browser')
@click.option('--output', 'output_path', default='output.ndjson', help='Default output file path')
def tui_command(starting_dir, output_path):
    """
    Launch interactive TUI for batch processing.

    The TUI provides:
    - File selection with directory browser
    - Real-time progress tracking
    - Error review
    - Processing summary

    Example:
        main.py tui
        main.py tui --dir /path/to/csvs --output results.ndjson
    """
    from tui import run_tui
    run_tui(starting_dir=starting_dir, output_path=output_path)


# Backward compatibility: allow calling convert command directly
# This is the same as convert, just with a different name for test compatibility
main = convert


if __name__ == '__main__':
    cli()
