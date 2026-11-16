#!/usr/bin/env python3
"""Build the catalog from retained role evidence. Python standard library only."""
import argparse
import copy
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('discovery', 'diamond', 'fees', 'ranking', 'review')
ELIGIBILITY = {'verified_free', 'conditional', 'needs_verification', 'not_free'}
BANDS = ('very_high', 'high', 'moderate', 'unknown', 'not_comparable')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def unique(items):
    return list({json.dumps(item, sort_keys=True): item for item in items}.values())


def slug(name):
    name = re.sub(r'\s*\([^)]*\)', '', name).casefold()
    name = name.replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', '-', name).strip('-')


def url(value):
    return isinstance(value, str) and value.startswith(('https://', 'http://'))


def validate_record(record):
    ident = record.get('id', '<missing>')
    for field in ('id', 'name', 'kind', 'homepage', 'author_guidelines', 'subjects', 'route', 'review', 'difficulty', 'metrics'):
        assert field in record, f'{ident}: missing {field}'
    assert url(record['homepage']), f'{ident}: invalid homepage'
    assert url(record['author_guidelines']), f'{ident}: invalid guidelines'
    assert record['kind'] in {'journal', 'conference', 'preprint_server', 'repository', 'research_blog'}, f'{ident}: invalid venue kind'
    assert record['review']['type'] in {'peer_reviewed', 'editorial', 'moderation', 'none', 'unknown'}, f'{ident}: invalid review type'
    route = record['route']
    assert route['model'] in {'diamond', 'subscription', 'conditional_waiver', 'conditional_agreement', 'free_deposit', 'unknown'}, f'{ident}: invalid route model'
    assert route['eligibility'] in ELIGIBILITY, f'{ident}: invalid eligibility'
    for key in ('submission_fee', 'publication_fee'):
        assert route[key] in {'none', 'charged', 'unknown'}, f'{ident}: invalid {key}'
    if route['eligibility'] == 'verified_free':
        assert route['submission_fee'] == route['publication_fee'] == 'none', f'{ident}: free claim contradicts fees'
        assert route['model'] not in {'conditional_waiver', 'conditional_agreement'}, f'{ident}: conditional route called free'
        evidence = route.get('fee_evidence', [])
        assert any(url(x.get('url')) and x.get('access') == 'page' for x in evidence), f'{ident}: free claim lacks readable fee evidence'
    for evidence in route.get('fee_evidence', []):
        assert url(evidence.get('url')), f'{ident}: invalid evidence URL'
        assert evidence.get('checked_on'), f'{ident}: undated fee evidence'
        assert evidence.get('note'), f'{ident}: unexplained fee evidence'
    assert record['difficulty']['band'] in BANDS, f'{ident}: invalid difficulty'
    if record['difficulty']['band'] not in {'unknown', 'not_comparable'}:
        assert record['difficulty'].get('source_urls'), f'{ident}: difficulty without evidence'
    for metric in record['metrics']:
        assert metric.get('name') and 'value' in metric and url(metric.get('source_url')), f'{ident}: unsupported metric'
        assert 'year' in metric and 'population' in metric, f'{ident}: metric missing period/denominator field'
        if metric['value'] is None:
            assert metric.get('note'), f'{ident}: unknown metric needs an explanation'


def load_memberships(allow_incomplete=False):
    memberships, receipt, missing = [], [], []
    subfields = read(ROOT / 'data/subfields.json')
    for subfield in subfields:
        field = subfield['id']
        records = {}
        for role in ROLES:
            path = ROOT / 'research' / role / f'{field}.json'
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
                continue
            document = read(path)
            assert document['subfield'] == field, f'{path}: wrong subfield'
            receipt.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'role': role, 'subfield': field})
            if role in {'discovery', 'diamond'}:
                for raw in document['records']:
                    record = copy.deepcopy(raw)
                    assert record['id'] not in records, f'{path}: duplicate source ID {record["id"]}'
                    record['subjects'] = unique([field] + record.get('subjects', []))
                    record['source_files'] = [str(path.relative_to(ROOT))]
                    records[record['id']] = record
            else:
                for patch in document.get('patches', []):
                    ident = patch['id']
                    assert ident in records, f'{path}: patch ID not found: {ident}'
                    records[ident].update({k: v for k, v in patch.items() if k != 'id'})
                    records[ident]['source_files'].append(str(path.relative_to(ROOT)))
        for record in records.values():
            record['source_subfield'] = field
            record['completed_roles'] = [x['role'] for x in receipt if x['subfield'] == field]
            memberships.append(record)
    if missing and not allow_incomplete:
        raise SystemExit('Missing required role files:\n' + '\n'.join(missing))
    adjustments = ROOT / 'research/adjudications.json'
    if adjustments.exists():
        for patch in read(adjustments).get('patches', []):
            matched = [r for r in memberships if r['id'] == patch['id'] and (not patch.get('subfield') or r['source_subfield'] == patch['subfield'])]
            assert matched, f'Adjudication ID not found: {patch["id"]}'
            for record in matched:
                record.update({k: v for k, v in patch.items() if k not in {'id', 'subfield'}})
                record['source_files'].append('research/adjudications.json')
        receipt.append({'path': 'research/adjudications.json', 'sha256': hashlib.sha256(adjustments.read_bytes()).hexdigest(), 'role': 'parent_adjudication', 'subfield': None})
    for record in memberships:
        validate_record(record)
    return subfields, memberships, receipt, missing


def consolidate(memberships):
    groups = defaultdict(list)
    for record in memberships:
        groups[slug(record['name'])].append(record)
    venues, conflicts = [], []
    for ident, records in groups.items():
        venue = copy.deepcopy(records[0])
        venue['id'] = ident
        venue['source_record_ids'] = [r['id'] for r in records]
        venue['subjects'] = unique([s for r in records for s in r['subjects']])
        venue['source_files'] = unique([s for r in records for s in r['source_files']])
        venue['difficulty_by_subfield'] = {r['source_subfield']: r['difficulty'] for r in records}
        venue['scope_by_subfield'] = {r['source_subfield']: r.get('scope_notes', '') for r in records}
        venue['metrics'] = unique([m for r in records for m in r['metrics']])
        venue['route']['fee_evidence'] = unique([e for r in records for e in r['route'].get('fee_evidence', [])])
        venue['route']['conditions'] = '\n'.join(dict.fromkeys(r['route'].get('conditions', '') for r in records))
        venue['formats'] = unique([f for r in records for f in r.get('formats', [])])
        venue['checked_on'] = '2026-11-16'
        venue['submission_status'] = 'closed' if any(r.get('submission_status') == 'closed' for r in records) else records[0].get('submission_status', 'unknown')
        statuses = {r['route']['eligibility'] for r in records}
        if len(statuses) > 1:
            # Never let an optimistic duplicate conceal a contradictory cost audit.
            venue['route']['eligibility'] = 'needs_verification'
            venue['audit_note'] = 'Cross-subfield fee assessments differ; resolve before recommending.'
            conflicts.append({'id': ident, 'source_ids': venue['source_record_ids'], 'eligibilities': sorted(statuses)})
        for fee in ('submission_fee', 'publication_fee'):
            values = {r['route'][fee] for r in records}
            venue['route'][fee] = 'charged' if 'charged' in values else ('unknown' if 'unknown' in values else 'none')
        if len(records) > 1:
            venue['difficulty'] = {'band': 'unknown', 'basis': 'Select a subfield to see its separately reviewed difficulty judgment.', 'source_urls': []}
        validate_record(venue)
        venues.append(venue)
    return sorted(venues, key=lambda v: v['name'].casefold()), conflicts


def esc(value):
    return html.escape(str(value), quote=True)


def recommended(venue):
    return venue['route']['eligibility'] == 'verified_free' and venue['review']['type'] == 'peer_reviewed' and venue['submission_status'] != 'closed'


def build(allow_incomplete=False):
    subfields, memberships, receipt, missing = load_memberships(allow_incomplete)
    venues, conflicts = consolidate(memberships)
    summary = {
        'checked_on': '2026-11-16', 'subfields': len(subfields), 'agent_role_files': sum(x['role'] in ROLES for x in receipt),
        'source_listings': len(memberships), 'unique_venues': len(venues),
        'eligibility_counts': dict(Counter(v['route']['eligibility'] for v in venues)),
        'kind_counts': dict(Counter(v['kind'] for v in venues)),
        'verified_free_peer_reviewed_open_for_consideration': sum(recommended(v) for v in venues),
        'venues_with_metrics': sum(any(m['value'] is not None for m in v['metrics']) for v in venues),
        'missing_role_files': missing, 'cross_subfield_fee_conflicts': conflicts,
    }
    coverage = []
    for field in subfields:
        selected = [v for v in venues if field['id'] in v['difficulty_by_subfield']]
        eligible = [v for v in selected if recommended(v)]
        coverage.append({'subfield': field['id'], 'name': field['name'], 'source_listings': sum(r['source_subfield'] == field['id'] for r in memberships), 'unique_venues': len(selected), 'verified_free_peer_reviewed': len(eligible), 'verified_free_with_difficulty_band': sum(v['difficulty_by_subfield'][field['id']]['band'] in {'very_high', 'high', 'moderate'} for v in eligible), 'venues_with_reported_metrics': sum(any(m['value'] is not None for m in v['metrics']) for v in selected)})
    summary['coverage'] = coverage
    write(ROOT / 'data/coverage.json', coverage)
    coverage_lines = ['# Coverage', '', 'Checked November 16, 2026. Subfield totals overlap where a venue fits more than one cluster. Difficulty bands are provisional agent judgments; absence of a band means insufficient comparative evidence.', '', '| Subfield cluster | Venue listings | Verified free peer-reviewed | With a difficulty band | Venues with reported metrics |', '| --- | ---: | ---: | ---: | ---: |']
    for row in coverage:
        coverage_lines.append(f'| [{row["name"]}](docs/subfields/{row["subfield"]}.md) | {row["unique_venues"]} | {row["verified_free_peer_reviewed"]} | {row["verified_free_with_difficulty_band"]} | {row["venues_with_reported_metrics"]} |')
    (ROOT / 'COVERAGE.md').write_text('\n'.join(coverage_lines) + '\n')
    research_notes = ['# Retained research notes and exclusions', '', 'These notes preserve excluded leads, blocked policy pages, source conflicts, scope conditions, and review findings. They are research records; use the canonical directory for current classifications.', '']
    assignments = []
    for field in subfields:
        research_notes += [f'## {field["name"]}', '']
        suffix = 'computational_physical' if field['id'] == 'computational-physical-sciences' else field['id'].replace('-', '_')
        for role in ROLES:
            rel = f'research/{role}/{field["id"]}.json'
            path = ROOT / rel
            assignments.append({'subfield': field['id'], 'role': role, 'task_name': f'/root/{"discover" if role == "discovery" else role}_{suffix}', 'evidence_file': rel, 'evidence_file_present': path.exists()})
            if not path.exists():
                continue
            doc = read(path)
            research_notes += [f'### {role.capitalize()}', '', f'[Role evidence]({rel})', '']
            for key in ('notes', 'findings'):
                value = doc.get(key)
                if value:
                    research_notes += [(value if isinstance(value, str) else '```json\n' + json.dumps(value, ensure_ascii=False, indent=2) + '\n```'), '']
    write(ROOT / 'data/agent-assignments.json', assignments)
    (ROOT / 'RESEARCH_NOTES.md').write_text('\n'.join(research_notes) + '\n')
    write(ROOT / 'data/venues.json', venues)
    write(ROOT / 'data/memberships.json', memberships)
    build_sources = [{'path': p, 'sha256': hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p in ('scripts/build.py', 'scripts/directory.html', 'data/subfields.json')]
    write(ROOT / 'data/build-receipt.json', {'summary': summary, 'inputs': receipt, 'build_sources': build_sources})
    columns = ['id', 'name', 'kind', 'subjects', 'eligibility', 'route_model', 'submission_fee', 'publication_fee', 'review_type', 'submission_status', 'conditions', 'homepage', 'author_guidelines', 'difficulty_by_subfield', 'metrics', 'fee_evidence']
    with (ROOT / 'data/venues.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, columns)
        writer.writeheader()
        for venue in venues:
            route = venue['route']
            row = {k: venue.get(k, '') for k in columns}
            row.update(subjects='; '.join(venue['subjects']), eligibility=route['eligibility'], route_model=route['model'], submission_fee=route['submission_fee'], publication_fee=route['publication_fee'], conditions=route['conditions'], review_type=venue['review']['type'])
            for key in ('difficulty_by_subfield', 'metrics'):
                row[key] = json.dumps(venue[key], ensure_ascii=False)
            row['fee_evidence'] = json.dumps(route['fee_evidence'], ensure_ascii=False)
            writer.writerow(row)
    docs = ROOT / 'docs/subfields'
    docs.mkdir(exist_ok=True)
    index = ['# Verified free peer-reviewed publication routes', '', 'Checked November 16, 2026. Select a subfield for ranked bands, conditions, and evidence. Bands are provisional agent judgments; unknown remains unranked. Closed submissions are omitted. See [methodology](docs/methodology.md).', '']
    for subfield in subfields:
        field = subfield['id']
        selected = [v for v in venues if field in v['difficulty_by_subfield'] and recommended(v)]
        selected.sort(key=lambda v: (BANDS.index(v['difficulty_by_subfield'][field]['band']), v['name'].casefold()))
        index.append(f'- [{subfield["name"]}](docs/subfields/{field}.md) — {len(selected)} verified free peer-reviewed routes')
        lines = [f'# {subfield["name"]}', '', f'Area: {subfield["area"]}. Checked November 16, 2026. These are venue comparisons, not an acceptance prediction. [Methodology](../methodology.md).', '', '## Verified free peer-reviewed routes', '']
        for venue in selected:
            difficulty = venue['difficulty_by_subfield'][field]
            lines += [f'### {venue["name"]}', '', f'**Difficulty:** {difficulty["band"].replace("_", " ")} (provisional agent judgment). {difficulty["basis"]}', '', f'**Route:** {venue["route"]["model"]}; {venue["route"]["oa_status"]}. {venue["route"]["conditions"]}', '', f'**Fit:** {venue["scope_by_subfield"][field]}', '', f'[Author guidance]({venue["author_guidelines"]}) · [Venue]({venue["homepage"]})', '']
            for evidence in venue['route']['fee_evidence']:
                lines += [f'- [Fee evidence]({evidence["url"]}) ({evidence["checked_on"]}, {evidence.get("access", "unknown")}): {evidence["note"]}']
            for metric in venue['metrics']:
                value = metric['value'] if metric['value'] is not None else 'not established'
                lines += [f'- [{metric["name"]}]({metric["source_url"]}): {value}; year/period: {metric.get("year") or "not reported"}; population: {metric.get("population") or "not reported"}. {metric.get("note", "")}']
            if difficulty.get('source_urls'):
                lines += ['- Difficulty evidence: ' + ', '.join(f'[source {n}]({u})' for n, u in enumerate(difficulty['source_urls'], 1))]
            lines += ['']
        if not selected:
            lines += ['No route has yet cleared the complete evidence checks for this cluster.', '']
        lines += ['## Other retained leads', '', '| Venue | Status | Review | Reason or conditions |', '| --- | --- | --- | --- |']
        for venue in venues:
            if field in venue['difficulty_by_subfield'] and not recommended(venue):
                reason = ('Submissions closed. ' if venue['submission_status'] == 'closed' else '') + venue['route']['conditions']
                lines.append(f'| [{venue["name"]}]({venue["author_guidelines"]}) | {venue["route"]["eligibility"]} | {venue["review"]["type"]} | {reason.replace(chr(10), " ").replace("|", ";")} |')
        (docs / f'{field}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (ROOT / 'DIRECTORY.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    template = (ROOT / 'scripts/directory.html').read_text(encoding='utf-8')
    payload = json.dumps({'subfields': subfields, 'venues': venues, 'summary': summary}, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    (ROOT / 'index.html').write_text(template.replace('/*CATALOG_DATA*/null', payload), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-incomplete', action='store_true', help='Preview only; never a complete research receipt.')
    build(parser.parse_args().allow_incomplete)
