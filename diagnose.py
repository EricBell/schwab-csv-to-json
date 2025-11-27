#!/usr/bin/env python3
"""Diagnostic tool to investigate validation issues in output files."""

import json
import click
from pathlib import Path


@click.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--issue-type', '-t', multiple=True, help='Filter by specific issue type(s)')
@click.option('--show-all-fields', '-a', is_flag=True, help='Show all fields (not just relevant ones)')
def diagnose(input_file, issue_type, show_all_fields):
    """
    Diagnose validation issues in processed NDJSON/JSON output.

    Shows records with validation issues for investigation.

    Examples:
        python diagnose.py output.ndjson
        python diagnose.py output.ndjson -t unknown_asset_type
        python diagnose.py output.ndjson -t amend_missing_stop_price -a
    """
    # Load records
    records = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Collect issues
    issue_counts = {}
    records_by_issue = {}

    for record in records:
        # Skip section headers
        if 'section_header' in record.get('issues', []):
            continue

        # Check for validation issues from validate() function
        event_type = record.get('event_type')

        # Amendment issues
        if event_type == 'amend':
            if not record.get('amendment', {}).get('ref'):
                issue = 'amend_missing_ref'
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
                records_by_issue.setdefault(issue, []).append(record)

            if record.get('amendment', {}).get('stop_price') is None:
                issue = 'amend_missing_stop_price'
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
                records_by_issue.setdefault(issue, []).append(record)
            continue

        # Regular record issues
        if not record.get('symbol'):
            issue = 'missing_symbol'
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
            records_by_issue.setdefault(issue, []).append(record)

        if not record.get('side'):
            issue = 'missing_side'
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
            records_by_issue.setdefault(issue, []).append(record)

        if record.get('qty') is None:
            issue = 'missing_qty'
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
            records_by_issue.setdefault(issue, []).append(record)

        asset_type = record.get('asset_type')
        if asset_type == 'OPTION':
            opt = record.get('option') or {}
            if not opt.get('exp_date'):
                issue = 'option_missing_exp'
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
                records_by_issue.setdefault(issue, []).append(record)
            if opt.get('strike') is None:
                issue = 'option_missing_strike'
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
                records_by_issue.setdefault(issue, []).append(record)
            if opt.get('right') not in {'PUT', 'CALL'}:
                issue = 'option_missing_right'
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
                records_by_issue.setdefault(issue, []).append(record)
        elif asset_type is None and event_type != 'amend':
            issue = 'unknown_asset_type'
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
            records_by_issue.setdefault(issue, []).append(record)

    # Display summary
    click.echo("=" * 80)
    click.echo(f"Validation Issue Summary for {Path(input_file).name}")
    click.echo("=" * 80)
    click.echo(f"Total records: {len(records)}")
    click.echo(f"Issue types found: {len(issue_counts)}")
    click.echo()

    if not issue_counts:
        click.echo("✓ No validation issues found!")
        return

    # Show counts
    for issue, count in sorted(issue_counts.items()):
        click.echo(f"  {issue}: {count}")
    click.echo()

    # Filter by issue type if specified
    issues_to_show = list(issue_type) if issue_type else sorted(issue_counts.keys())

    # Display problematic records
    for issue in issues_to_show:
        if issue not in records_by_issue:
            click.echo(f"⚠ No records found for issue type: {issue}")
            continue

        click.echo("=" * 80)
        click.echo(f"Issue: {issue} ({len(records_by_issue[issue])} record(s))")
        click.echo("=" * 80)

        for idx, record in enumerate(records_by_issue[issue], 1):
            click.echo(f"\n--- Record {idx} ---")

            if show_all_fields:
                # Show all fields
                click.echo(json.dumps(record, indent=2, ensure_ascii=False))
            else:
                # Show relevant fields only
                relevant_fields = [
                    'source_file', 'row_index', 'section', 'event_type',
                    'symbol', 'side', 'qty', 'type', 'asset_type',
                    'exec_time', 'time_canceled', 'price', 'order_type',
                    'amendment'
                ]

                filtered = {k: record.get(k) for k in relevant_fields if k in record}
                click.echo(json.dumps(filtered, indent=2, ensure_ascii=False))

                # Show raw CSV line
                if 'raw' in record:
                    click.echo(f"\nRaw CSV: {record['raw'][:120]}...")


if __name__ == '__main__':
    diagnose()
