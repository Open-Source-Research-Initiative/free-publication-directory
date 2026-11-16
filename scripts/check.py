#!/usr/bin/env python3
"""Check expansion evidence completeness, conservative gates and export freshness."""
import csv
import hashlib
import json
import re
from urllib.parse import urlsplit
from build import ROOT, ROLES, consolidate, exclusion_reasons, load_memberships, recommended, validate_record


def check():
    subfields, memberships, inputs, missing = load_memberships()
    assert not missing
    receipt = json.loads((ROOT / 'data/build-receipt.json').read_text())
    assert not receipt.get('preview') and receipt['inputs'] == inputs, 'Evidence receipt stale or incomplete.'
    for source in receipt['build_sources']:
        assert hashlib.sha256((ROOT / source['path']).read_bytes()).hexdigest() == source['sha256'], f'{source["path"]}: rebuild required'
    assignments = json.loads((ROOT / 'data/agent-assignments.json').read_text())
    assert len(assignments) == len({x['task_name'] for x in assignments}) == len(ROLES) * len(subfields)
    assert {(x['subfield'],x['role']) for x in assignments} == {(f['id'],r) for f in subfields for r in ROLES}
    for x in assignments:
        doc = json.loads((ROOT / x['evidence_file']).read_text())
        assert x['task_name'] == doc['agent_task'] and x['role'] == doc['role']
    assert len({r['id'] for r in memberships}) == len(memberships), 'Source IDs must be globally unique.'
    for r in memberships:
        assert set(r['completed_roles']) == set(ROLES)
        validate_record(r)
    candidates, conflicts = consolidate(memberships)
    venues = [v for v in candidates if not exclusion_reasons(v)]
    excluded = [{'id':v['id'],'name':v['name'],'reasons':exclusion_reasons(v),'source_record_ids':v['source_record_ids'],'source_files':v['source_files']} for v in candidates if exclusion_reasons(v)]
    for name, value in [('venues',venues),('candidates',candidates),('excluded-venues',excluded),('memberships',memberships)]:
        assert value == json.loads((ROOT / 'data' / (name+'.json')).read_text()), f'{name} stale'
    assert receipt['summary']['cross_subfield_fee_conflicts'] == conflicts
    with (ROOT / 'data/venues.csv').open(newline='', encoding='utf-8') as h:
        rows = list(csv.DictReader(h))
    assert [r['id'] for r in rows] == [v['id'] for v in venues]
    for row, venue in zip(rows, venues):
        for key in ('subfields','subjects','formats','scope_by_subfield','geography','ai_policy','quality','metrics','source_record_ids','source_files'):
            assert json.loads(row[key]) == venue.get(key, ''), f'CSV mismatch: {venue["id"]} {key}'
        for key in ('submission_fee', 'publication_fee', 'conditions', 'eligibility'):
            assert row[key] == venue['route'].get(key, ''), f'CSV mismatch: {venue["id"]} {key}'
        assert json.loads(row['fee_evidence']) == venue['route'].get('fee_evidence', [])
        assert json.loads(row['review_sources']) == venue['review'].get('source_urls', [])
    text = (ROOT / 'index.html').read_text(encoding='utf-8')
    assert '/*CATALOG_DATA*/null' not in text
    payload = json.dumps({'subfields':subfields,'venues':venues,'summary':receipt['summary']},ensure_ascii=False).replace('<','\\u003c').replace('&','\\u0026')
    assert payload in text, 'Browser catalog stale'
    for v in candidates:
        assert 'difficulty' not in v and 'difficulty_by_subfield' not in v
        for value in [v['homepage'],v['author_guidelines']] + [e['url'] for e in v['route'].get('fee_evidence',[])] + [m['source_url'] for m in v['metrics']]:
            parts=urlsplit(value)
            assert parts.scheme in {'http','https'} and parts.hostname and not parts.username and not parts.password
        if recommended(v): assert v in venues
    # Validate links in generated guides and static browser navigation.
    guides = [ROOT / 'DIRECTORY.md', ROOT / 'COVERAGE.md', ROOT / 'RESEARCH_NOTES.md'] + list((ROOT / 'docs/subfields').glob('*.md'))
    for path in guides:
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if target.startswith(('http:', 'https:', 'mailto:', '#')): continue
            assert (path.parent / target.split('#')[0]).exists(), f'{path}: broken link {target}'
    for target in re.findall(r'href="([^"{}]+)"', text):
        if target.startswith(('http:', 'https:', 'mailto:', '#')) or '${' in target: continue
        assert (ROOT / target.split('#')[0]).exists(), f'Browser: broken link {target}'
    qa_path = ROOT / 'research/qa/browser-check.json'
    if qa_path.exists():
        qa=json.loads(qa_path.read_text())
        assert qa['status']=='pass' and qa.get('catalog_sha256') == hashlib.sha256((ROOT / 'data/venues.json').read_bytes()).hexdigest() and qa.get('html_sha256') == hashlib.sha256((ROOT / 'index.html').read_bytes()).hexdigest(), 'Browser QA stale or failed'
    result={'status':'pass','subfields':len(subfields),'role_files':len(assignments),'source_listings':len(memberships),'unique_candidates':len(candidates),'unique_venues':len(venues),'excluded_candidates':len(excluded),'verified_free_peer_reviewed':sum(recommended(v) for v in venues),'cross_subfield_conflicts_held':len(conflicts),'limits':'Checks data and evidence completeness, gates, hashes and exports; does not establish source truth or human scientific approval.'}
    (ROOT / 'data/validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__': check()
