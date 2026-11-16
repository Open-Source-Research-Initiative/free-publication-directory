#!/usr/bin/env python3
"""Build the expansion catalog from retained, independently assigned evidence."""
import argparse
import copy
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / 'research/campaigns/2026-11-16-expansion'
ROLES = ('discovery', 'fees', 'geography', 'ai-policy', 'metrics-review')
ELIGIBILITY = {'verified_free', 'conditional', 'needs_verification', 'not_free'}
ISO2 = set('AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split())
IDENTITY_ALIASES = {
    'cybersecurity-privacy-security-information-applications': 'security-and-information-applications-um',
    'human-computer-interaction-security-and-information-applications': 'security-and-information-applications-um',
    'public-health-pan-american-journal': 'paho-pan-american-journal',
    'health-systems-pan-american-journal-of-public-health': 'paho-pan-american-journal',
}
ALIAS_EVIDENCE = {
    'security-and-information-applications-um': {
        'basis': 'Both Universiti Malaya journal pages identify Security and Information Applications at the JSIA journal path.',
        'source_urls': ['https://borneojournal.um.edu.my/index.php/JSIA', 'https://mojes.um.edu.my/index.php/JSIA/index'],
        'expected_names': ['Security and Information Applications'],
        'expected_homepages': ['https://borneojournal.um.edu.my/index.php/JSIA', 'https://mojes.um.edu.my/index.php/JSIA/index'],
    },
    'paho-pan-american-journal': {
        'basis': 'PAHO identifies the same flagship journal in English and Spanish on its journal website; both records point to the identical English homepage.',
        'source_urls': ['https://journal.paho.org/en', 'https://journal.paho.org/es'],
        'expected_names': ['Revista Panamericana de Salud Pública / Pan American Journal of Public Health', 'Pan American Journal of Public Health / Revista Panamericana de Salud Pública'],
        'expected_homepages': ['https://journal.paho.org/en'],
    },
}
REGIONS = {'North America', 'South America', 'Europe', 'Asia', 'Africa', 'Oceania', 'Unknown'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def unique(items):
    return list({json.dumps(item, sort_keys=True, ensure_ascii=False): item for item in items}.values())


def slug(name):
    name = re.sub(r'\s*\([^)]*\)', '', name).casefold().replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', '-', name).strip('-')


def url(value):
    if not isinstance(value, str) or value != value.strip() or any(c.isspace() for c in value):
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme in {'http', 'https'} and bool(parts.hostname) and not parts.username and not parts.password
    except ValueError:
        return False


def validate_record(record):
    ident = record.get('id', '<missing>')
    for field in ('id', 'name', 'kind', 'homepage', 'author_guidelines', 'subjects', 'route', 'review', 'metrics'):
        assert field in record, f'{ident}: missing {field}'
    assert url(record['homepage']) and url(record['author_guidelines']), f'{ident}: invalid URL'
    assert record['kind'] in {'journal', 'conference', 'preprint_server', 'repository', 'research_blog'}
    assert record['review']['type'] in {'peer_reviewed', 'editorial', 'moderation', 'none', 'unknown'}
    route = record['route']
    assert route['model'] in {'diamond', 'subscription', 'conditional_waiver', 'conditional_agreement', 'free_deposit', 'unknown'}
    assert route['eligibility'] in ELIGIBILITY
    for key in ('submission_fee', 'publication_fee'):
        assert route[key] in {'none', 'charged', 'unknown'}
    if route['eligibility'] == 'verified_free':
        assert route['submission_fee'] == route['publication_fee'] == 'none'
        assert route['model'] not in {'conditional_waiver', 'conditional_agreement'}
        assert any(url(x.get('url')) and x.get('access') == 'page' for x in route.get('fee_evidence', []))
    for e in route.get('fee_evidence', []):
        assert url(e.get('url')) and e.get('checked_on') and e.get('note'), f'{ident}: invalid fee evidence'
    for metric in record['metrics']:
        assert metric.get('name') and 'value' in metric and url(metric.get('source_url')) and 'year' in metric and 'population' in metric, f'{ident}: invalid metric'
    if 'geography' in record:
        validate_geography(record['geography'], ident)
    ai = record.get('ai_policy', {})
    if ai:
        assert ai.get('compatibility') in {'compatible', 'limited', 'prohibited', 'unclear'}
        assert all(ai.get('permissions', {}).get(k) in {'allowed', 'conditional', 'prohibited', 'not_stated'} for k in ('research', 'analysis_code', 'manuscript_drafting'))
        assert all(url(e.get('url')) for e in ai.get('policy_sources', [])), f'{ident}: invalid AI policy source'
        assert all(url(u) for u in ai.get('disclosure', {}).get('source_urls', [])), f'{ident}: invalid disclosure source'



def validate_geography(geo, ident):
    assert isinstance(geo, dict), f'{ident}: geography must be an object'
    for key in ('venue_countries', 'publisher_countries'):
        assert isinstance(geo.get(key), list), f'{ident}: {key} must be an array'
        for country in geo[key]:
            assert isinstance(country, dict) and country.get('code') in ISO2, f'{ident}: invalid ISO country'
            assert all(isinstance(country.get(k), str) and country[k].strip() for k in ('name', 'basis')), f'{ident}: country missing name or basis'
            assert url(country.get('source_url')), f'{ident}: country missing cited basis'
    for key in ('venue_regions', 'research_focus_regions'):
        assert isinstance(geo.get(key), list) and all(r in REGIONS | ({'International'} if key == 'research_focus_regions' else set()) for r in geo[key]), f'{ident}: invalid regions'
    authors = geo.get('author_eligibility')
    assert isinstance(authors, dict) and authors.get('status') in {'international', 'restricted', 'not_stated', 'unclear'}, f'{ident}: invalid author eligibility'
    assert isinstance(authors.get('description'), str) and authors['description'].strip(), f'{ident}: missing author description'
    assert isinstance(authors.get('source_urls'), list) and all(url(x) for x in authors['source_urls']), f'{ident}: invalid author sources'
    if authors['status'] in {'international', 'restricted'}: assert authors['source_urls'], f'{ident}: author eligibility requires evidence'
    assert isinstance(geo.get('scope_notes'), str) and isinstance(geo.get('checked_on'), str) and geo['checked_on'].strip()
    assert isinstance(geo.get('evidence'), list)
    for e in geo['evidence']:
        assert isinstance(e, dict) and url(e.get('url')) and isinstance(e.get('note'), str) and e['note'].strip() and e.get('access') in {'page', 'search_snippet', 'blocked', 'unavailable'}, f'{ident}: invalid geographic evidence'


def disclosure_complete(ai):
    d = ai.get('disclosure')
    return (isinstance(d, dict) and d.get('status') in {'required', 'required_except_editing', 'recommended', 'not_stated', 'unclear'}
            and isinstance(d.get('instructions'), str) and bool(d['instructions'].strip())
            and isinstance(d.get('source_urls'), list) and bool(d['source_urls']) and all(url(u) for u in d['source_urls']))

def ai_compatible(record):
    ai = record.get('ai_policy') or {}
    return (ai.get('compatibility') == 'compatible' and disclosure_complete(ai)
            and all(ai.get('permissions', {}).get(k) in {'allowed', 'conditional'} for k in ('research', 'analysis_code', 'manuscript_drafting'))
            and any(url(s.get('url')) and s.get('access') == 'page' and isinstance(s.get('applicability'), str) and s['applicability'].strip() for s in ai.get('policy_sources', [])))


def exclusion_reasons(record):
    reasons = []
    if not ai_compatible(record):
        reasons.append('AI workflow permission or applicable readable evidence is incomplete or incompatible')
    route = record['route']
    conditional_route = route['eligibility'] == 'conditional' and route['model'] in {'conditional_waiver', 'conditional_agreement'}
    if route['eligibility'] == 'not_free' or ('charged' in (route['submission_fee'], route['publication_fee']) and not conditional_route):
        reasons.append('Mandatory author fee or no free standard route')
    if record.get('submission_status') in {'closed', 'paused'}:
        reasons.append('Submissions closed or paused')
    return reasons


def load_memberships(allow_incomplete=False):
    campaign = read(CAMPAIGN / 'campaign.json')
    subfields = read(ROOT / 'data/subfields.json')
    assert [x['id'] for x in subfields] == campaign['subfields'], 'Taxonomy differs from campaign'
    assert tuple(campaign['roles']) == ROLES
    receipt, missing, memberships, assignments = [], [], [], []
    def include(path, role, field=None):
        rel = str(path.relative_to(ROOT))
        receipt.append({'path': rel, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'role': role, 'subfield': field})
    include(CAMPAIGN / 'campaign.json', 'campaign')
    include(CAMPAIGN / 'CONTRACT.md', 'contract')
    include(ROOT / 'research/CONTRACT.md', 'historical_contract')
    for path in sorted(CAMPAIGN.glob('release-*.json')):
        include(path, 'release_review')
    for name, digest in campaign['baseline_hashes'].items():
        path = CAMPAIGN / 'baseline' / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Baseline hash mismatch: {name}'
        include(path, 'baseline')
    baseline = read(CAMPAIGN / 'baseline/memberships.json')
    for field in campaign['subfields']:
        records = {}
        for raw in baseline:
            if raw['source_subfield'] == field:
                r = copy.deepcopy(raw)
                r.pop('ai_policy', None)  # Historical shorthand is not campaign evidence.
                r['source_files'] = [str((CAMPAIGN / 'baseline/memberships.json').relative_to(ROOT))]
                records[r['id']] = r
        completed = []
        for role in ROLES:
            path = CAMPAIGN / role / f'{field}.json'
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
                continue
            doc = read(path)
            assert doc['subfield'] == field and doc['role'] == role and doc['checked_on'] == campaign['checked_on'], f'{path}: invalid metadata'
            assert isinstance(doc.get('agent_task'), str) and doc['agent_task'].strip(), f'{path}: missing agent_task'
            assert 'notes' in doc, f'{path}: missing notes'
            include(path, role, field)
            assignments.append({'subfield': field, 'role': role, 'task_name': doc['agent_task'], 'evidence_file': str(path.relative_to(ROOT)), 'evidence_file_present': True})
            completed.append(role)
            if role == 'discovery':
                for raw in doc['records']:
                    r = copy.deepcopy(raw)
                    assert r['id'] not in records, f'{path}: duplicate id {r["id"]}'
                    r['source_files'] = [str(path.relative_to(ROOT))]
                    records[r['id']] = r
            else:
                seen = set()
                for patch in doc['patches']:
                    ident = patch['id']
                    assert ident in records and ident not in seen, f'{path}: unknown or duplicate patch {ident}'
                    seen.add(ident)
                    required = {'fees': 'route', 'geography': 'geography', 'ai-policy': 'ai_policy'}.get(role)
                    if required: assert required in patch, f'{path}: {ident} missing {required}'
                    records[ident].update(copy.deepcopy({k: v for k, v in patch.items() if k not in {'id', 'audit_note'}}))
                    records[ident]['source_files'].append(str(path.relative_to(ROOT)))
                if role != 'metrics-review':
                    assert seen == set(records), f'{path}: missing candidate patches'
        for record in records.values():
            record.pop('difficulty', None)
            record.pop('difficulty_by_subfield', None)
            record['source_subfield'] = field
            record['completed_roles'] = completed[:]
            memberships.append(record)
    if missing and not allow_incomplete:
        raise SystemExit('Missing required role files:\n' + '\n'.join(missing))
    for path in sorted(CAMPAIGN.glob('reconciliation-*.json')):
        include(path, 'reconciliation_evidence')
    adjudications = CAMPAIGN / 'adjudications.json'
    if adjudications.exists():
        doc = read(adjudications)
        assert isinstance(doc.get('patches'), list), 'Adjudications must contain patches'
        for patch in doc['patches']:
            matches = [r for r in memberships if r['id'] == patch.get('id') and (not patch.get('subfield') or r['source_subfield'] == patch['subfield'])]
            assert len(matches) == 1, f'Adjudication must identify exactly one source record: {patch.get("id")}'
            assert isinstance(patch.get('audit_note'), str) and patch['audit_note'].strip(), 'Adjudication needs a rationale'
            assert isinstance(patch.get('source_urls'), list) and patch['source_urls'] and all(url(u) for u in patch['source_urls']), 'Adjudication needs cited evidence'
            changes = {k: v for k, v in patch.items() if k not in {'id', 'subfield', 'audit_note', 'source_urls'}}
            assert changes and set(changes) <= {'route', 'review', 'geography', 'ai_policy', 'metrics', 'submission_status', 'scope_notes'}, 'Invalid adjudicated fields'
            matches[0].update(copy.deepcopy(changes))
            matches[0]['source_files'].append(str(adjudications.relative_to(ROOT)))
        include(adjudications, 'adjudication')
    from fee_followup import apply as apply_fee_followup
    apply_fee_followup(ROOT, memberships, receipt, missing, allow_incomplete, read, consolidate, ai_compatible, url)
    from quality_followup import apply as apply_quality_followup
    apply_quality_followup(ROOT, memberships, receipt, missing, allow_incomplete, read, consolidate, exclusion_reasons, url)
    for record in memberships:
        validate_record(record)
    tasks = [x['task_name'] for x in assignments]
    assert len(tasks) == len(set(tasks)), 'Each assignment must have a distinct actual agent_task'
    return subfields, memberships, receipt, missing



def merge_geography(records):
    variants = [r.get('geography') for r in records if r.get('geography')]
    if not variants:
        return None
    result = copy.deepcopy(variants[0])
    for key in ('venue_countries', 'publisher_countries', 'evidence'):
        result[key] = unique([item for g in variants for item in g.get(key, [])])
    for key in ('venue_regions', 'research_focus_regions'):
        values = unique([item for g in variants for item in g.get(key, [])])
        result[key] = [x for x in values if x != 'Unknown'] if any(x != 'Unknown' for x in values) else values
    authors = [g['author_eligibility'] for g in variants]
    statuses = {a['status'] for a in authors}
    result['author_eligibility'] = {
        'status': next(iter(statuses)) if len(statuses) == 1 else 'unclear',
        'description': ' | '.join(dict.fromkeys(a['description'] for a in authors)),
        'source_urls': unique([u for a in authors for u in a['source_urls']]),
    }
    result['scope_notes'] = ' | '.join(dict.fromkeys(g['scope_notes'] for g in variants if g['scope_notes']))
    return result

def consolidate(memberships):
    # Name plus homepage host prevents merging identically named unrelated venues.
    from urllib.parse import urlsplit
    groups = defaultdict(list)
    for r in memberships:
        alias = IDENTITY_ALIASES.get(r['id'])
        if alias:
            assert r['name'] in ALIAS_EVIDENCE[alias]['expected_names'] and r['homepage'] in ALIAS_EVIDENCE[alias]['expected_homepages'], f'{r["id"]}: identity evidence no longer matches'
        # Preserve parenthetical differences when identifying a journal.
        strict_name = re.sub(r'[^a-z0-9]+', '-', r['name'].casefold()).strip('-')
        groups[('alias', alias) if alias else (strict_name, urlsplit(r['homepage']).hostname or '')].append(r)
    venues, conflicts, ids = [], [], set()
    for (base, host), records in groups.items():
        alias = host if base == 'alias' else None
        base = slug(records[0]['name'])
        ident = base if base not in ids else base + '-' + slug(host)
        assert ident not in ids
        ids.add(ident)
        v = copy.deepcopy(records[0]); v['id'] = ident
        v['source_record_ids'] = [r['id'] for r in records]
        if alias: v['identity_reconciliation'] = copy.deepcopy(ALIAS_EVIDENCE[alias])
        v['subfields'] = unique([r['source_subfield'] for r in records])
        v['scope_by_subfield'] = {r['source_subfield']: r.get('scope_notes', '') for r in records}
        v['subjects'] = unique([s for r in records for s in r.get('subjects', [])])
        v['source_files'] = unique([s for r in records for s in r['source_files']])
        v['metrics'] = unique([m for r in records for m in r['metrics']])
        v['formats'] = unique([f for r in records for f in r.get('formats', [])])
        v['route']['fee_evidence'] = unique([e for r in records for e in r['route'].get('fee_evidence', [])])
        v['route']['conditions'] = '\n'.join(dict.fromkeys(r['route'].get('conditions', '') for r in records))
        v['submission_status'] = next((s for s in ('closed', 'paused') if any(r.get('submission_status') == s for r in records)), records[0].get('submission_status', 'unknown'))
        statuses = {r['route']['eligibility'] for r in records}
        for fee in ('submission_fee', 'publication_fee'):
            values = {r['route'][fee] for r in records}
            v['route'][fee] = 'charged' if 'charged' in values else ('unknown' if 'unknown' in values else 'none')
        if 'not_free' in statuses: v['route']['eligibility'] = 'not_free'
        elif len(statuses) > 1: v['route']['eligibility'] = 'needs_verification'
        if len(statuses) > 1: conflicts.append({'id': ident, 'source_ids': v['source_record_ids'], 'eligibilities': sorted(statuses)})
        # Any contradictory or unreviewed duplicate blocks optimistic compatibility.
        if len({json.dumps(r.get('ai_policy'), sort_keys=True) for r in records}) > 1:
            v['ai_policy_variants'] = unique([r.get('ai_policy') for r in records])
        if not all(ai_compatible(r) for r in records):
            policies = [r.get('ai_policy') for r in records if not ai_compatible(r) and r.get('ai_policy')]
            policy = next((p for status in ('prohibited', 'limited', 'unclear', 'compatible') for p in policies if p.get('compatibility') == status), None)
            v['ai_policy'] = copy.deepcopy(policy or {'compatibility': 'unclear', 'permissions': {'research':'not_stated','analysis_code':'not_stated','manuscript_drafting':'not_stated'}, 'policy_sources': []})
            if v['ai_policy']['compatibility'] == 'compatible': v['ai_policy']['compatibility'] = 'unclear'
        if len({json.dumps(r.get('geography'), sort_keys=True) for r in records}) > 1:
            v['geography_variants'] = unique([r.get('geography') for r in records])
        geo = merge_geography(records)
        if geo is not None: v['geography'] = geo
        if len({r['review']['type'] for r in records}) > 1: v['review']['type'] = 'unknown'
        v.pop('source_subfield', None); v.pop('completed_roles', None)
        validate_record(v); venues.append(v)
    return sorted(venues, key=lambda x: x['name'].casefold()), conflicts


def recommended_before_quality(v):
    return (not exclusion_reasons(v) and v['route']['eligibility'] == 'verified_free' and v['route']['submission_fee'] == v['route']['publication_fee'] == 'none' and v['review']['type'] == 'peer_reviewed')


def recommended(v):
    return recommended_before_quality(v) and v.get('quality', {}).get('status') != 'concerns'


def build(allow_incomplete=False):
    subfields, memberships, receipt, missing = load_memberships(allow_incomplete)
    candidates, conflicts = consolidate(memberships)
    venues = [v for v in candidates if not exclusion_reasons(v)]
    excluded = [{'id': v['id'], 'name': v['name'], 'reasons': exclusion_reasons(v), 'source_record_ids': v['source_record_ids'], 'source_files': v['source_files']} for v in candidates if exclusion_reasons(v)]
    summary = {'checked_on':'2026-11-16', 'subfields':len(subfields), 'agent_role_files':sum(x['role'] in ROLES for x in receipt), 'source_listings':len(memberships), 'unique_candidates':len(candidates), 'unique_venues':len(venues), 'excluded_candidates':len(excluded), 'eligibility_counts':dict(Counter(v['route']['eligibility'] for v in venues)), 'kind_counts':dict(Counter(v['kind'] for v in venues)), 'verified_free_peer_reviewed_open_for_consideration':sum(recommended(v) for v in venues), 'venues_with_metrics':sum(any(m['value'] is not None for m in v['metrics']) for v in venues), 'missing_role_files':missing, 'cross_subfield_fee_conflicts':conflicts}
    summary['verified_free_peer_reviewed_before_quality'] = sum(recommended_before_quality(v) for v in venues)
    followup_inputs = [x for x in receipt if x['role'].startswith('fee_followup_')]
    if followup_inputs:
        manifest = read(ROOT / 'research/campaigns/2026-11-16-cost-followup/campaign.json')
        followup_ids = {ident for group in manifest['batches'].values() for ident in group}
        summary['fee_followup'] = {
            'target_count': len(followup_ids),
            'baseline_recommended_count': manifest['baseline_recommended_count'],
            'current_recommended_count': sum(recommended_before_quality(v) for v in venues),
            'target_verified_free_count': sum(v['route']['eligibility'] == 'verified_free' for v in candidates if v['id'] in followup_ids),
            'complete': not any('2026-11-16-cost-followup/' in path for path in missing),
            'tasks': [{'role': x['role'], 'task_name': read(ROOT / x['path'])['agent_task'], 'evidence_file': x['path']} for x in followup_inputs if x['role'] in {'fee_followup_audit', 'fee_followup_review'}],
        }
    quality_inputs = [x for x in receipt if x['role'].startswith('quality_')]
    if quality_inputs:
        quality_venues = [v for v in venues if 'quality' in v]
        summary['quality_review'] = {
            'target_count': 146,
            'complete': not any('2026-11-16-quality/' in path for path in missing),
            'status_counts': {status: sum(v['quality']['status'] == status for v in quality_venues) for status in ('supported', 'needs_verification', 'concerns')},
            'registry_confirmed_venues': sum(any(i['verification'] == 'registry_confirmed' for i in v['quality']['indexing']) for v in quality_venues),
            'publisher_claim_only_venues': sum(any(i['verification'] == 'publisher_claim_only' for i in v['quality']['indexing']) for v in quality_venues),
            'documented_concern_venues': sum(v['quality']['status'] == 'concerns' for v in quality_venues),
            'supplemental_task_count': len({read(ROOT / x['path'])['agent_task'] for x in quality_inputs if x['role'] in {'quality_completion', 'quality_registry', 'quality_supplemental_review'} and read(ROOT / x['path'])['agent_task'] != '/root'}),
            'supplemental_tasks': [{'role': x['role'], 'task_name': read(ROOT / x['path'])['agent_task'], 'evidence_file': x['path']} for x in quality_inputs if x['role'] in {'quality_completion', 'quality_registry', 'quality_supplemental_review'} and read(ROOT / x['path'])['agent_task'] != '/root'],
            'primary_supplemental_files': [x['path'] for x in quality_inputs if x['role'] in {'quality_completion', 'quality_registry', 'quality_supplemental_review'} and read(ROOT / x['path'])['agent_task'] == '/root'],
            'tasks': [{'role': x['role'], 'task_name': read(ROOT / x['path'])['agent_task'], 'evidence_file': x['path']} for x in quality_inputs if x['role'] in {'quality_audit', 'quality_review'}],
        }
    coverage = []
    for f in subfields:
        selected = [v for v in venues if f['id'] in v['subfields']]
        coverage.append({'subfield':f['id'], 'name':f['name'], 'source_listings':sum(r['source_subfield'] == f['id'] for r in memberships), 'unique_venues':len(selected), 'verified_free_peer_reviewed':sum(recommended(v) for v in selected), 'venues_with_reported_metrics':sum(any(m['value'] is not None for m in v['metrics']) for v in selected)})
    summary['coverage'] = coverage
    out = ROOT / 'preview-expansion' if allow_incomplete else ROOT
    assignments = []
    for entry in receipt:
        if entry['role'] in ROLES:
            doc = read(ROOT / entry['path'])
            assignments.append({'subfield':entry['subfield'], 'role':entry['role'], 'task_name':doc['agent_task'], 'evidence_file':entry['path'], 'evidence_file_present':True})
    for name, value in [('venues',venues),('candidates',candidates),('excluded-venues',excluded),('memberships',memberships),('coverage',coverage),('agent-assignments',assignments)]: write(out / 'data' / (name + '.json'), value)
    sources = ['scripts/build.py','scripts/fee_followup.py','scripts/quality_followup.py','scripts/directory.html','data/subfields.json']
    write(out / 'data/build-receipt.json', {'summary':summary,'inputs':receipt,'build_sources':[{'path':p,'sha256':hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p in sources], 'preview':allow_incomplete})
    columns = ['id','name','kind','publisher','homepage','author_guidelines','submission_url','subfields','subjects','formats','scope_by_subfield','eligibility','route_model','submission_fee','publication_fee','oa_status','other_mandatory_costs','review_type','review_sources','submission_status','conditions','geography','ai_policy','quality','metrics','fee_evidence','source_record_ids','source_files']
    with (out / 'data/venues.csv').open('w', newline='', encoding='utf-8') as h:
        w = csv.DictWriter(h, columns, lineterminator='\n'); w.writeheader()
        for v in venues:
            route=v['route']; row={k:v.get(k,'') for k in columns}
            row.update(eligibility=route['eligibility'],route_model=route['model'],submission_fee=route['submission_fee'],publication_fee=route['publication_fee'],conditions=route.get('conditions',''),oa_status=route.get('oa_status',''),other_mandatory_costs=route.get('other_mandatory_costs',''),review_type=v['review']['type'],review_sources=v['review'].get('source_urls',[]),fee_evidence=route.get('fee_evidence',[]))
            for key in ('subfields','subjects','formats','scope_by_subfield','geography','ai_policy','quality','metrics','fee_evidence','review_sources','source_record_ids','source_files'): row[key]=json.dumps(row[key],ensure_ascii=False)
            w.writerow(row)
    docs = out / 'docs/subfields'
    docs.mkdir(parents=True, exist_ok=True)
    index = ['# Default recommended publication routes', '', 'Checked November 16, 2026. These default recommendations meet the campaign AI workflow and verified author-cost criteria, are peer reviewed, and have no documented medium or high quality concerns. [Methodology](docs/methodology.md).', '']
    coverage_lines = ['# Coverage', '', 'Subfield totals overlap. The main directory includes only AI-compatible, non-paid-only venues with submissions not known closed or paused.', '', '| Subfield | AI-compatible venues | Default recommendations | With reported metrics |', '| --- | ---: | ---: | ---: |']
    for field, cov in zip(subfields, coverage):
        fid = field['id']
        selected = [v for v in venues if fid in v['subfields'] and recommended(v)]
        index.append(f'- [{field["name"]}](docs/subfields/{fid}.md) — {len(selected)} default recommended routes')
        coverage_lines.append(f'| [{field["name"]}](docs/subfields/{fid}.md) | {cov["unique_venues"]} | {cov["verified_free_peer_reviewed"]} | {cov["venues_with_reported_metrics"]} |')
        lines = [f'# {field["name"]}', '', 'Default recommended free peer-reviewed routes with a compatible AI policy and no documented medium or high quality concerns. Check current author instructions before submission.', '']
        for v in selected:
            route = v['route']
            ai = v['ai_policy']
            disclosure = ai['disclosure']
            geo = v.get('geography', {})
            lines += [f'## {v["name"]}', '', f'**Fit:** {v["scope_by_subfield"][fid]}', '',
                      f'**Submission fee:** {route["submission_fee"]}. **Publication fee:** {route["publication_fee"]}.', '',
                      f'**Conditions and other costs:** {route.get("conditions", "")} {route.get("other_mandatory_costs", "")}', '',
                      f'**AI policy:** {ai.get("summary", "")}', '',
                      f'**Disclosure ({disclosure["status"]}):** {disclosure["instructions"]}', '',
                      f'[Author guidance]({v["author_guidelines"]}) · [Venue]({v["homepage"]})', '']
            quality = v.get('quality')
            if quality:
                lines += [f'**Quality evidence ({quality["status"]}):** {quality["summary"]}', '']
                for item in quality['indexing']:
                    links = ', '.join(f'[source]({u})' for u in item['source_urls'])
                    lines.append(f'- {item["name"]}: {item["verification"].replace("_", " ")} — {item["note"]} {links}'.rstrip())
                lines.append('')
            evidence_lines = []
            for key, label in (('venue_countries', 'Venue base'), ('publisher_countries', 'Publisher base')):
                for country in geo.get(key, []):
                    evidence_lines.append(f'- {label}: [{country["name"]}]({country["source_url"]}) — {country["basis"]}.')
            authors = geo.get('author_eligibility', {})
            if authors:
                evidence_lines.append(f'- Author eligibility ({authors["status"]}): {authors["description"]}')
                for source in authors.get('source_urls', []): evidence_lines.append(f'- [Author eligibility source]({source})')
            for e in route.get('fee_evidence', []): evidence_lines.append(f'- [Fee evidence]({e["url"]}): {e["note"]}')
            for e in ai.get('policy_sources', []): evidence_lines.append(f'- [AI policy]({e["url"]}): {e.get("note", "")}')
            for source in disclosure['source_urls']: evidence_lines.append(f'- [Disclosure source]({source})' + (f' — {disclosure["section"]}' if disclosure.get('section') else ''))
            for m in v['metrics']:
                if m['value'] is not None: evidence_lines.append(f'- [{m["name"]}]({m["source_url"]}): {m["value"]}; period: {m.get("year") or "not reported"}; population: {m.get("population") or "not reported"}. {m.get("note", "")}')
            lines.extend(dict.fromkeys(evidence_lines))
            lines.append('')
        if not selected: lines.append('No route has cleared all recommendation checks for this subfield.')
        (docs / (fid + '.md')).write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    (out / 'DIRECTORY.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    (out / 'COVERAGE.md').write_text('\n'.join(coverage_lines)+'\n',encoding='utf-8')
    notes = ['# Retained research notes and exclusions', '', 'Review findings, uncertainties and excluded leads are retained in the linked campaign evidence.', '']
    for a in assignments:
        doc = read(ROOT / a['evidence_file'])
        notes += [f'## {a["subfield"]} — {a["role"]}', '', f'[Evidence]({a["evidence_file"]})', '']
        for key in ('notes', 'findings'):
            value = doc.get(key)
            if value: notes += [value if isinstance(value, str) else '```json\n' + json.dumps(value, ensure_ascii=False, indent=2) + '\n```', '']
    (out / 'RESEARCH_NOTES.md').write_text('\n'.join(notes)+'\n',encoding='utf-8')
    template = (ROOT / 'scripts/directory.html').read_text(encoding='utf-8')
    payload = json.dumps({'subfields':subfields,'venues':venues,'summary':summary},ensure_ascii=False).replace('<','\\u003c').replace('&','\\u0026')
    (out / 'index.html').write_text(template.replace('/*CATALOG_DATA*/null',payload),encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-incomplete', action='store_true', help='Write an explicitly incomplete preview under preview-expansion/.')
    build(parser.parse_args().allow_incomplete)
