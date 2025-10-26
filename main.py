#!/usr/bin/env python3
"""
convert_to_flat_ndjson_cli.py

Convert a Schwab-style CSV (multiple sections) into a flat NDJSON file.
Produces one JSON object per data row with canonical keys (unified schema for all sections):
  section, row_index, exec_time, time_canceled, time_placed, side, qty, pos_effect,
  symbol, exp, strike, type, spread, price, net_price, price_improvement, order_type,
  tif, status, notes, mark, raw, issues

Usage examples:
  python convert_to_flat_ndjson_cli.py in.csv out.ndjson
  python convert_to_flat_ndjson_cli.py in.csv out.ndjson --pretty
  python convert_to_flat_ndjson_cli.py in.csv out.ndjson --preview 20

See --help for all options.
"""
from __future__ import annotations
import csv
import json
import re
import sys
import logging
from typing import Dict, List, Optional
import click

# Default section detection patterns (regex -> canonical name)
# These match actual header rows from Schwab CSVs
DEFAULT_SECTION_PATTERNS = {
    # Filled Orders: matches header row with exec time, price, net price, price improvement, order type
    r'(?i)^,+exec\s*time.*spread.*side.*qty.*pos\s*effect.*symbol.*price.*net\s*price.*price\s*improvement.*order\s*type': 'Filled Orders',
    # Canceled Orders: matches header row with notes, time canceled, PRICE (uppercase), TIF, status
    r'(?i)^notes,+time\s*canceled.*spread.*side.*qty.*pos\s*effect.*symbol.*price,+tif.*status': 'Canceled Orders',
    # Working Orders: matches header row with notes, time placed, PRICE, TIF, mark, status
    r'(?i)^notes,+time\s*placed.*spread.*side.*qty.*pos\s*effect.*symbol.*price,+tif.*mark.*status': 'Working Orders',
    # Rolling Strategies: matches header row
    r'(?i)^covered\s*call\s*position.*new\s*exp.*call\s*by.*begin.*order\s*price.*active\s*time': 'Rolling Strategies',
    # Fallback patterns for section name rows (less specific)
    r'(?i)^\s*,?\s*filled\s*orders\s*$': 'Filled Orders',
    r'(?i)^\s*,?\s*canceled|cancelled\s*orders\s*$': 'Canceled Orders',
    r'(?i)^\s*,?\s*working\s*orders\s*$': 'Working Orders',
    r'(?i)^\s*,?\s*rolling\s*strategies\s*$': 'Rolling Strategies',
    # Top-of-file metadata
    r'(?i)^\s*,?\s*account|today\'s trade activity': 'Top'
}

# Column alias map -> flat keys (unified schema for all sections)
COL_ALIASES = {
    # Time fields
    'exec time': 'exec_time', 'execution time': 'exec_time', 'time': 'exec_time',
    'time canceled': 'time_canceled', 'time cancelled': 'time_canceled',
    'time placed': 'time_placed',
    # Trade fields
    'side': 'side',
    'qty': 'qty', 'quantity': 'qty',
    'pos effect': 'pos_effect', 'position effect': 'pos_effect',
    'symbol': 'symbol', 'underlying': 'symbol',
    # Option fields
    'exp': 'exp', 'expiration': 'exp',
    'strike': 'strike', 'strike price': 'strike',
    'type': 'type',
    'spread': 'spread',
    # Price fields
    'price': 'price',
    'net price': 'net_price', 'netprice': 'net_price',
    'price improvement': 'price_improvement', 'price_impr': 'price_improvement',
    # Order fields
    'order type': 'order_type', 'ordertype': 'order_type',
    'tif': 'tif', 'time in force': 'tif',
    'status': 'status',
    # Other fields
    'notes': 'notes', 'note': 'notes',
    'mark': 'mark'
}


def compile_section_patterns(patterns: Dict[str, str]):
    return [(re.compile(pat), name) for pat, name in patterns.items()]


def normalize_key(k: Optional[str]) -> str:
    if not k:
        return ""
    k2 = k.strip().lower().replace('\ufeff', '')
    k2 = re.sub(r'\s+', ' ', k2)
    return k2


def map_header_to_index(header_row: List[str]) -> Dict[str, int]:
    """
    Map header row to field indices.
    Sorts aliases by length (longest first) to ensure more specific matches take priority.
    E.g., "time canceled" should match before "time", "net price" before "price".
    """
    mapping: Dict[str, int] = {}
    # Sort aliases by length descending - longer/more specific matches first
    sorted_aliases = sorted(COL_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)

    for i, h in enumerate(header_row):
        nk = normalize_key(h)
        if not nk:
            continue
        for alias, flat in sorted_aliases:
            if alias in nk:
                mapping[flat] = i
                break
    return mapping


def safe_get(row: List[str], idx: Optional[int]) -> Optional[str]:
    """
    Safely get a value from a row by index.
    Returns None for: missing index, out of bounds, empty strings, or special placeholders.
    Special placeholders per PRD: "~" and "-" represent missing values.
    """
    if idx is None:
        return None
    if idx < 0:
        return None
    if idx < len(row):
        v = row[idx].strip()
        # Treat empty, "~", and "-" as null (per PRD)
        if v == "" or v == "~" or v == "-":
            return None
        return v
    return None


def detect_section_from_row(row: List[str], compiled_patterns) -> Optional[str]:
    joined = ",".join([ (c or "").strip() for c in row ])
    for pat, name in compiled_patterns:
        if pat.search(joined):
            return name
    return None


def parse_integer_qty(q_raw: Optional[str], issues: List[str]) -> Optional[int]:
    if q_raw is None:
        return None
    s = q_raw.strip()
    if s == "":
        return None
    # Remove + and commas, keep sign if present
    s_clean = s.replace('+', '').replace(',', '')
    try:
        q = int(s_clean)
        if q_raw.strip().startswith('-'):
            q = -abs(q)
        return q
    except Exception:
        issues.append('qty_parse_failed')
        return q_raw  # return raw if can't parse


def parse_float_field(v: Optional[str], name: str, issues: List[str]) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v.replace(',', '').replace('$', ''))
    except Exception:
        issues.append(f'{name}_parse_failed')
        return None


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('input_csv', type=click.Path(exists=True, dir_okay=False))
@click.argument('output_json', type=click.Path(dir_okay=False))
@click.option('--encoding', default='utf-8', show_default=True, help='File encoding for input CSV')
@click.option('--output-ndjson/--output-json', default=True, help='Write newline-delimited JSON (default) or a single JSON array')
@click.option('--pretty', is_flag=True, help='Pretty-print JSON (only applies to single JSON array mode)')
@click.option('--preview', type=int, default=0, help='Print preview of first N output records to stdout after conversion')
@click.option('--max-rows', type=int, default=0, help='Only process first N CSV records (0 = all)')
@click.option('--qty-signed/--qty-unsigned', default=True, help='Treat qty with sign (True keeps negative for sells)')
@click.option('--verbose', is_flag=True, help='Enable debug logging')
@click.option('--section-patterns-file', type=click.Path(exists=True, dir_okay=False),
              help='Optional JSON file mapping regex->section name to override defaults')
def main(input_csv, output_json, encoding, output_ndjson, pretty, preview, max_rows, qty_signed, verbose, section_patterns_file):
    """
    Convert SECTIONED CSV -> flat NDJSON / JSON.

    INPUT_CSV: path to Schwab CSV
    OUTPUT_JSON: destination NDJSON or JSON file
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    # Load custom section patterns if provided
    section_patterns = DEFAULT_SECTION_PATTERNS.copy()
    if section_patterns_file:
        try:
            with open(section_patterns_file, 'r', encoding='utf-8') as pf:
                custom = json.load(pf)
                if isinstance(custom, dict):
                    section_patterns.update(custom)
                    logging.debug("Loaded custom section patterns from %s", section_patterns_file)
                else:
                    logging.warning("Custom patterns file does not contain a JSON object; ignoring")
        except Exception as e:
            logging.error("Failed to load section patterns file: %s", e)
            sys.exit(1)

    compiled_patterns = compile_section_patterns(section_patterns)

    # State
    current_section = 'Top'
    section_header: Optional[List[str]] = None
    header_map: Dict[str, int] = {}
    row_index = 0
    out_records = []  # used only if output_json (not ndjson)

    # Streaming write for ndjson
    fout = open(output_json, 'w', encoding='utf-8')

    try:
        with open(input_csv, newline='', encoding=encoding, errors='replace') as fh:
            reader = csv.reader(fh)
            for row in reader:
                row_index += 1
                if max_rows and row_index > max_rows:
                    break

                # Detect section header row
                sec = detect_section_from_row(row, compiled_patterns)
                if sec:
                    current_section = sec
                    section_header = [c for c in row]
                    header_map = map_header_to_index(section_header)
                    # Emit optional marker for header row as a JSON object (section header flagged)
                    obj_hdr = {
                        "section": current_section,
                        "row_index": row_index,
                        # Time fields
                        "exec_time": None,
                        "time_canceled": None,
                        "time_placed": None,
                        # Trade fields
                        "side": None,
                        "qty": None,
                        "pos_effect": None,
                        "symbol": None,
                        # Option fields
                        "exp": None,
                        "strike": None,
                        "type": None,
                        "spread": None,
                        # Price fields
                        "price": None,
                        "net_price": None,
                        "price_improvement": None,
                        # Order fields
                        "order_type": None,
                        "tif": None,
                        "status": None,
                        # Other fields
                        "notes": None,
                        "mark": None,
                        "raw": ",".join([c if c is not None else "" for c in row]),
                        "issues": ["section_header"]
                    }
                    # Write header marker
                    if output_ndjson:
                        fout.write(json.dumps(obj_hdr, ensure_ascii=False) + "\n")
                    else:
                        out_records.append(obj_hdr)
                    continue

                # Map fields based on header_map if available (unified schema)
                issues: List[str] = []

                # Initialize all fields to None
                exec_time = time_canceled = time_placed = None
                side = qty_raw = pos_effect = symbol = None
                exp = strike = type_field = spread = None
                price = net_price = price_improvement = None
                order_type = tif = status = None
                notes = mark = None

                if header_map:
                    # Time fields
                    exec_time = safe_get(row, header_map.get('exec_time'))
                    time_canceled = safe_get(row, header_map.get('time_canceled'))
                    time_placed = safe_get(row, header_map.get('time_placed'))
                    # Trade fields
                    side = safe_get(row, header_map.get('side'))
                    qty_raw = safe_get(row, header_map.get('qty'))
                    pos_effect = safe_get(row, header_map.get('pos_effect'))
                    symbol = safe_get(row, header_map.get('symbol'))
                    # Option fields
                    exp = safe_get(row, header_map.get('exp'))
                    strike = safe_get(row, header_map.get('strike'))
                    type_field = safe_get(row, header_map.get('type'))
                    spread = safe_get(row, header_map.get('spread'))
                    # Price fields
                    price = safe_get(row, header_map.get('price'))
                    net_price = safe_get(row, header_map.get('net_price'))
                    price_improvement = safe_get(row, header_map.get('price_improvement'))
                    # Order fields
                    order_type = safe_get(row, header_map.get('order_type'))
                    tif = safe_get(row, header_map.get('tif'))
                    status = safe_get(row, header_map.get('status'))
                    # Other fields
                    notes = safe_get(row, header_map.get('notes'))
                    mark = safe_get(row, header_map.get('mark'))
                else:
                    # Heuristic fallback when no header for this section has been captured
                    if len(row) >= 14:
                        exec_time = row[0].strip() or None
                        side = row[2].strip() if len(row) > 2 else None
                        qty_raw = row[3].strip() if len(row) > 3 else None
                        pos_effect = row[4].strip() if len(row) > 4 else None
                        symbol = row[5].strip() if len(row) > 5 else None
                        price = row[10].strip() if len(row) > 10 else None
                        net_price = row[11].strip() if len(row) > 11 else None
                        price_improvement = row[12].strip() if len(row) > 12 else None
                        order_type = row[13].strip() if len(row) > 13 else None
                    else:
                        issues.append('no_header_map')

                # Parse qty
                if qty_signed:
                    qty = parse_integer_qty(qty_raw, issues)
                else:
                    # unsigned: return absolute integer if parseable
                    qty_val = parse_integer_qty(qty_raw, issues)
                    if isinstance(qty_val, int):
                        qty = abs(qty_val)
                    else:
                        qty = qty_val  # raw fallback

                # Parse numeric prices
                price_f = parse_float_field(price, 'price', issues)
                net_price_f = parse_float_field(net_price, 'net_price', issues)
                price_impr_f = parse_float_field(price_improvement, 'price_improvement', issues)

                # If exec_time missing, fallback to first column
                if not exec_time and len(row) > 0:
                    candidate = row[0].strip()
                    if candidate:
                        exec_time = candidate

                obj = {
                    "section": current_section,
                    "row_index": row_index,
                    # Time fields
                    "exec_time": exec_time,
                    "time_canceled": time_canceled,
                    "time_placed": time_placed,
                    # Trade fields
                    "side": side,
                    "qty": qty,
                    "pos_effect": pos_effect,
                    "symbol": symbol,
                    # Option fields
                    "exp": exp,
                    "strike": strike,
                    "type": type_field,
                    "spread": spread,
                    # Price fields
                    "price": price_f,
                    "net_price": net_price_f,
                    "price_improvement": price_impr_f,
                    # Order fields
                    "order_type": order_type,
                    "tif": tif,
                    "status": status,
                    # Other fields
                    "notes": notes,
                    "mark": mark,
                    "raw": ",".join([c if c is not None else "" for c in row]),
                    "issues": issues
                }

                # Output
                if output_ndjson:
                    fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
                else:
                    out_records.append(obj)

    finally:
        fout.close()

    # If user requested a single JSON array output, write it (overwrite)
    if not output_ndjson:
        with open(output_json, 'w', encoding='utf-8') as f_arr:
            if pretty:
                json.dump(out_records, f_arr, ensure_ascii=False, indent=2)
            else:
                json.dump(out_records, f_arr, ensure_ascii=False)

    # Preview if requested
    if preview > 0:
        click.echo("\nPreview of first {} output records:\n".format(preview))
        # read back file and print first preview lines
        with open(output_json, 'r', encoding='utf-8') as fpr:
            count = 0
            for line in fpr:
                click.echo(line.rstrip())
                count += 1
                if count >= preview:
                    break

    # Print counts per section (quick pass)
    section_counts: Dict[str, int] = {}
    with open(output_json, 'r', encoding='utf-8') as fcnt:
        for line in fcnt:
            try:
                obj = json.loads(line)
                sec = obj.get('section', 'Unknown') if isinstance(obj, dict) else 'Unknown'
                section_counts[sec] = section_counts.get(sec, 0) + 1
            except Exception:
                continue

    click.echo("\nDone. Wrote: {}".format(output_json))
    click.echo("Processed rows: {}".format(row_index))
    click.echo("Records per section (approx):")
    for sec, cnt in section_counts.items():
        click.echo(f"  {sec}: {cnt}")

if __name__ == '__main__':
    main()