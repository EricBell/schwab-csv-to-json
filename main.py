#!/usr/bin/env python3
# convert_csv_to_ndjson.py
import csv, json, re
import click

# Configure known section header signatures (case-insensitive substrings)
# Adjust these to the exact headers your Schwab CSV uses.
header_patterns = {
    'Filled Orders': re.compile(r'(?i)exec\s*time.*price.*order\s*type'),
    'Working Orders': re.compile(r'(?i)working\s*orders'),
    'Summary': re.compile(r'(?i)summary'),
    # add other sections as needed
}

# If a header row is itself a CSV header (contains the column names), store it by section
section_headers = {}

def detect_section_from_row(row):
    # row is a list of fields (strings)
    joined = ",".join(field.strip() for field in row if field is not None)
    for sec_name, pat in header_patterns.items():
        if pat.search(joined):
            return sec_name
    # fallback heuristics:
    if any(field and ('Exec Time' in field or 'Price Improvement' in field) for field in row):
        return 'Filled Orders'  # heuristic
    return None

@click.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.argument('output_file', type=click.Path())
def convert_csv_to_ndjson(input_file, output_file):
    """Convert Schwab CSV file to NDJSON format.

    INPUT_FILE: Path to the input CSV file
    OUTPUT_FILE: Path to the output NDJSON file
    """
    with open(input_file, newline='', encoding='utf-8', errors='replace') as fh_in, \
         open(output_file, 'w', encoding='utf-8') as fh_out:

        reader = csv.reader(fh_in)
        current_section = 'Top'   # default before any explicit section
        row_index = 0
        last_known_header = None

        for row in reader:
            row_index += 1
            # Normalize empty fields
            row = [None if (cell is None or cell == '') else cell for cell in row]

            # Try to detect if this row is a section header row
            sec = detect_section_from_row(row)
            if sec:
                current_section = sec
                # store as header row for that section
                last_known_header = row
                section_headers[current_section] = row
                # emit a marker object if you like (optional)
                obj = {
                    "section": current_section,
                    "row_index": row_index,
                    "raw": row,
                    "parsed": None,
                    "original_line_preview": ",".join([c if c else "" for c in row])[:200],
                    "issues": ["section_header"]
                }
                fh_out.write(json.dumps(obj, ensure_ascii=False) + "\n")
                continue

            # If we have a known header for the current section, map it
            parsed = None
            issues = []
            if current_section in section_headers and section_headers[current_section]:
                hdr = section_headers[current_section]
                # Map header -> value by index (safe for different lengths)
                parsed = {}
                for i, h in enumerate(hdr):
                    header_name = h.strip() if h else f"col{i}"
                    if i < len(row):
                        parsed[header_name] = row[i]
                    else:
                        parsed[header_name] = None
                        issues.append(f"missing_field_for_header:{header_name}")
                # If row longer than header, keep extra fields as raw tail
                if len(row) > len(hdr):
                    parsed["_extra"] = row[len(hdr):]
            else:
                # No header known for current_section: leave parsed None
                parsed = None

            # Simple validation for Filled Orders: Exec Time should be present
            if current_section == 'Filled Orders':
                exec_time = None
                # Try some common header keys for exec time
                if parsed:
                    for key in parsed.keys():
                        if key and 'Exec' in key and 'Time' in key:
                            exec_time = parsed.get(key)
                            break
                if not exec_time and len(row) > 0:
                    # fallback: first column
                    exec_time = row[0]
                if not exec_time:
                    issues.append('missing_exec_time')

            obj = {
                "section": current_section,
                "row_index": row_index,
                "raw": row,
                "parsed": parsed,
                "original_line_preview": ",".join([c if c else "" for c in row])[:200],
                "issues": issues
            }
            fh_out.write(json.dumps(obj, ensure_ascii=False) + "\n")

    click.echo(f"Wrote ndjson to {output_file}")

if __name__ == '__main__':
    convert_csv_to_ndjson()