#!/usr/bin/env python3
"""Read baseline plus additional discovery records without changing data."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / 'research/campaigns/2026-11-16-expansion'


def records_for(subfield):
    rows = [r for r in json.loads((CAMPAIGN / 'baseline/memberships.json').read_text()) if r['source_subfield'] == subfield]
    discovery = CAMPAIGN / 'discovery' / (subfield + '.json')
    if discovery.exists():
        rows += json.loads(discovery.read_text())['records']
    ids = [r['id'] for r in rows]
    assert len(ids) == len(set(ids)), 'Duplicate baseline/discovery IDs'
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subfield', required=True)
    parser.add_argument('--names', action='store_true')
    args = parser.parse_args()
    records = records_for(args.subfield)
    if args.names:
        for record in records:
            print(record['id'] + ' | ' + record['name'])
    else:
        print(json.dumps(records, ensure_ascii=False, indent=2))
