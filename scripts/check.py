#!/usr/bin/env python3
"""Check actual research completeness, fee gates, freshness and generated exports."""
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from build import ROOT, ROLES, consolidate, load_memberships, recommended, validate_record


def check():
    subfields, memberships, inputs, missing = load_memberships()
    assert not missing
    receipt = json.loads((ROOT / 'data/build-receipt.json').read_text())
    assert receipt['inputs'] == inputs, 'Evidence receipt stale; rebuild after research changes.'
    for source in receipt['build_sources']:
        assert hashlib.sha256((ROOT / source['path']).read_bytes()).hexdigest() == source['sha256'], f'{source["path"]}: build source changed; rebuild.'
    assert len([i for i in inputs if i['role'] in ROLES]) == 5 * len(subfields), 'Five role files required per subfield.'
    assignments = json.loads((ROOT / 'data/agent-assignments.json').read_text())
    assert len(assignments) == len({a['task_name'] for a in assignments}) == 5 * len(subfields), 'Five distinct agent assignments required per subfield.'
    assert all(a['evidence_file_present'] and (ROOT / a['evidence_file']).is_file() for a in assignments), 'Missing assignment evidence.'
    assert len({r['id'] for r in memberships}) == len(memberships), 'Source IDs must be globally unique.'
    for record in memberships:
        assert set(record['completed_roles']) == set(ROLES), f'{record["id"]}: incomplete review'
        validate_record(record)
    venues, conflicts = consolidate(memberships)
    assert venues == json.loads((ROOT / 'data/venues.json').read_text()), 'Canonical data stale.'
    assert memberships == json.loads((ROOT / 'data/memberships.json').read_text()), 'Membership data stale.'
    assert receipt['summary']['cross_subfield_fee_conflicts'] == conflicts
    with (ROOT / 'data/venues.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert [r['id'] for r in rows] == [v['id'] for v in venues], 'CSV disagrees with JSON.'
    html = (ROOT / 'index.html').read_text()
    assert '/*CATALOG_DATA*/null' not in html, 'HTML not built.'
    assert 'id="peer" type="checkbox" checked' in html, 'Default must restrict to peer-reviewed venues.'
    assert "v.submission_status!=='closed'" in html, 'Closed submissions must be hidden by default.'
    assert 'Choose a research subfield to compare' in html, 'No cross-field prestige ladder.'
    for venue in venues:
        for value in [venue['homepage'], venue['author_guidelines']] + [e['url'] for e in venue['route']['fee_evidence']] + [m['source_url'] for m in venue['metrics']]:
            parts = urlsplit(value)
            assert parts.scheme in {'http', 'https'} and parts.hostname
            assert not parts.username and not parts.password, 'Do not store URL credentials.'
        if recommended(venue):
            assert venue['route']['eligibility'] == 'verified_free'
            assert venue['route']['submission_fee'] == venue['route']['publication_fee'] == 'none'
            assert venue['review']['type'] == 'peer_reviewed'
            assert venue['submission_status'] != 'closed'
    for field in subfields:
        path = ROOT / 'docs/subfields' / f'{field["id"]}.md'
        assert path.is_file() and path.stat().st_size > 100
    browser_report = ROOT / 'research/qa/browser-check.json'
    if browser_report.exists():
        qa = json.loads(browser_report.read_text())
        assert qa['status'] == 'pass'
        assert qa.get('catalog_sha256') == hashlib.sha256((ROOT / 'data/venues.json').read_bytes()).hexdigest(), 'Browser QA catalog is stale.'
        assert qa.get('html_sha256') == hashlib.sha256((ROOT / 'index.html').read_bytes()).hexdigest(), 'Browser QA HTML is stale.'
    # Check all retained local links in the standalone repository, including generated field pages.
    checked_links = 0
    for path in ROOT.rglob('*.md'):
        if '.git' in path.parts:
            continue
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if target.startswith(('http:', 'https:', 'mailto:', '#')):
                continue
            local = target.split('#')[0]
            assert (path.parent / local).exists(), f'{path.relative_to(ROOT)}: broken local link {target}'
            checked_links += 1
    result = {'status': 'pass', 'subfields': len(subfields), 'role_files': 5 * len(subfields), 'source_listings': len(memberships), 'unique_venues': len(venues), 'verified_free_peer_reviewed': sum(recommended(v) for v in venues), 'local_markdown_links_checked': checked_links, 'cross_subfield_conflicts_held': len(conflicts), 'limits': 'Checks evidence-file completeness, data invariants, hashes, exports and local links. Does not establish source truth, ongoing venue policies or human scientific approval.'}
    (ROOT / 'data/validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    check()
