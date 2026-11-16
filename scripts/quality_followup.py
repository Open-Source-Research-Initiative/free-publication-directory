"""Validate and apply the bounded quality evidence campaign."""
import copy
import hashlib
from pathlib import Path

CAMPAIGN = Path('research/campaigns/2026-11-16-quality')
STANDARDS = ('board', 'ownership', 'ethics', 'corrections_retractions', 'conflicts_of_interest', 'complaints_appeals', 'archiving', 'licensing')
ACCESS = {'page', 'search_snippet', 'blocked', 'unavailable'}


def validate_quality(q, date, url):
    assert isinstance(q, dict) and q.get('checked_on') == date and q.get('status') in {'supported', 'needs_verification', 'concerns'}
    assert q.get('summary') and q.get('audit_limits')
    def urls(xs): return isinstance(xs, list) and all(url(x) for x in xs)
    identity = q['identity']
    assert isinstance(identity.get('issns'), list) and identity.get('publisher') and urls(identity.get('source_urls')) and identity.get('notes')
    evidence = q['evidence']; assert isinstance(evidence, list) and evidence
    for e in evidence:
        assert url(e.get('url')) and e.get('checked_on') == date and e.get('access') in ACCESS and e.get('source_type') in {'journal','publisher','index_registry','institution','other_official'} and e.get('note')
    readable = {e['url'] for e in evidence if e['access'] == 'page'}
    registry = {e['url'] for e in evidence if e['access'] == 'page' and e['source_type'] == 'index_registry'}
    indexing = q['indexing']; assert isinstance(indexing, list) and indexing
    for i in indexing:
        assert i.get('name') and i.get('category') in {'citation_index','bibliographic_database','open_access_directory','discovery_service','identifier_registry','preservation_service','ethics_membership'}
        assert i.get('verification') in {'registry_confirmed','publisher_claim_only','not_verified','not_listed','discontinued'} and i.get('checked_on') == date and i.get('access') in ACCESS and i.get('note')
        assert all(k in i for k in ('coverage','registry_url','registry_record_id','publisher_url','matched_issns')) and isinstance(i['matched_issns'], list) and urls(i.get('source_urls'))
        for key in ('registry_url','publisher_url'):
            assert i[key] is None or url(i[key])
        if i['verification'] == 'registry_confirmed':
            assert i['access'] == 'page' and i['registry_url'] in registry and i['registry_url'] in i['source_urls'] and i['matched_issns'] and set(i['matched_issns']) <= set(identity['issns']), 'Registry confirmation requires readable authority and matched identity'
        if i['verification'] in {'not_listed','discontinued'}:
            assert i['access'] == 'page' and i['registry_url'] in registry and i['matched_issns'] and set(i['matched_issns']) <= set(identity['issns'])
    peer = q['peer_review']; assert peer.get('verification') in {'documented','unclear','not_peer_reviewed'} and peer.get('model') in {'double_anonymous','single_anonymous','open','editorial','unknown','mixed'} and peer.get('summary') and peer.get('notes') and urls(peer.get('source_urls'))
    standards = q['editorial_standards']; assert set(standards) == set(STANDARDS)
    for key in STANDARDS:
        s = standards[key]; assert s.get('status') in {'documented','unclear','concern'} and urls(s.get('source_urls')) and s.get('note')
        if key == 'board':
            assert isinstance(s.get('names'), list) and all(n.get('name') and n.get('role') and isinstance(n.get('affiliation'), str) for n in s['names'])
    samples = q['publication_checks']; assert isinstance(samples, list)
    for p in samples:
        assert p.get('title') and url(p.get('url')) and p.get('checked_on') == date and p.get('observations') and urls(p.get('source_urls')) and 'doi' in p and 'published_on' in p
    concerns = q['concerns']; assert isinstance(concerns, list)
    for c in concerns:
        assert c.get('code') and c.get('severity') in {'low','medium','high'} and c.get('summary') and c.get('rationale') and urls(c.get('evidence_urls')) and c['evidence_urls']
        if c['severity'] in {'medium','high'}: assert set(c['evidence_urls']) <= readable, 'Concern requires readable evidence'
    serious = any(c['severity'] in {'medium','high'} for c in concerns)
    assert (q['status'] == 'concerns') == serious, 'Quality status does not match concerns'
    if q['status'] == 'supported':
        assert peer['verification'] == 'documented' and peer['source_urls'] and set(peer['source_urls']) <= readable
        for key in ('board','ownership','ethics','corrections_retractions'):
            assert standards[key]['status'] == 'documented' and standards[key]['source_urls'] and set(standards[key]['source_urls']) <= readable
        assert standards['board']['names'] and samples and any(p['url'] in readable or bool(set(p['source_urls']) & readable) for p in samples), 'Supported requires named board and readable sample'


def apply(root, memberships, receipt, missing, allow_incomplete, read, consolidate, exclusion_reasons, url):
    base = root / CAMPAIGN
    if not base.exists(): return
    local_missing = []
    def required(path, role):
        if not path.is_file():
            rel = str(path.relative_to(root)); missing.append(rel); local_missing.append(rel); return None
        receipt.append({'path':str(path.relative_to(root)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'role':role, 'subfield':None})
        return path
    def doc(path, role):
        p = required(path, role); return read(p) if p else None
    manifest = doc(base/'campaign.json', 'quality_campaign')
    required(base/'CONTRACT.md', 'quality_contract')
    baseline = doc(base/'baseline.json', 'quality_baseline')
    if manifest is None or baseline is None:
        if not allow_incomplete: raise SystemExit('Missing quality inputs: ' + ', '.join(local_missing))
        return
    assert hashlib.sha256((base/'baseline.json').read_bytes()).hexdigest() == manifest['baseline_sha256'], 'Quality baseline hash mismatch'
    ids = [v['id'] for v in baseline]; assert len(ids) == len(set(ids)) == manifest['target_count'] == 146
    current = {v['id']:v for v in consolidate(memberships)[0] if not exclusion_reasons(v)}
    assert set(current) == set(ids), 'Quality baseline IDs changed'
    for v in baseline:
        assert current[v['id']] == v, f"{v['id']}: quality baseline data changed"
    by_id = {v['id']:v for v in baseline}
    # Supplements are optional until a decision cites them. Receipt every present
    # file so changes to the evidence set invalidate a generated snapshot.
    supplemental = {}
    groups = [('registry-*.json', 'quality_registry'), ('completions/*.json', 'quality_completion'), ('completion-assignments/*.json', 'quality_completion_assignment'), ('reviews/supplement-*.json', 'quality_supplemental_review')]
    for pattern, role in groups:
        for path in sorted(base.glob(pattern)):
            data = doc(path, role)
            rel = str(path.relative_to(root))
            if role == 'quality_completion_assignment':
                assert isinstance(data, dict) and data.get('batch') and isinstance(data.get('records'), list)
                continue
            assert data.get('checked_on') == manifest['checked_on'] and isinstance(data.get('agent_task'), str) and data['agent_task'].strip()
            records = data.get('records'); assert isinstance(records, list)
            record_ids = [r['id'] for r in records]
            assert len(record_ids) == len(set(record_ids)) and set(record_ids) <= set(ids), f'{rel}: invalid supplemental record IDs'
            if role == 'quality_supplemental_review':
                assert data.get('scope'), f'{rel}: missing review scope'
                for record in records:
                    assert record.get('outcome') and record.get('observations') and isinstance(record.get('sources'), list) and all(url(source) for source in record['sources']), f'{rel}: {record["id"]}: invalid supplemental review'
            if role == 'quality_completion':
                assert data.get('batch')
                for record in records:
                    try:
                        validate_quality(record['quality'], manifest['checked_on'], url)
                    except (AssertionError, KeyError, TypeError) as error:
                        raise AssertionError(f'{rel}: {record["id"]}: invalid quality: {error}') from error
            supplemental[rel] = set(record_ids)
    batches = manifest['batches']; assigned = [x for group in batches.values() for x in group]
    assert len(batches) == 16 and len(assigned) == len(set(assigned)) == 146 and set(assigned) == set(ids), 'Invalid quality audit partition'
    audits, reviews, tasks = {}, {}, []
    for batch, expected in batches.items():
        assignment = doc(base/'assignments'/(batch+'.json'), 'quality_assignment')
        if assignment is not None:
            assert assignment['batch'] == batch and assignment['venues'] == [by_id[i] for i in expected], f'{batch}: invalid assignment'
        d = doc(base/'audits'/(batch+'.json'), 'quality_audit')
        if d is None: continue
        assert d['batch'] == batch and d['checked_on'] == manifest['checked_on'] and isinstance(d.get('notes'), str)
        task = d.get('agent_task'); assert isinstance(task,str) and task.strip(); tasks.append(task)
        records = d['records']; actual = [r['id'] for r in records]
        assert len(actual) == len(set(actual)) and set(actual) == set(expected), f'{batch}: invalid audit coverage'
        for r in records:
            assert sorted(r['source_record_ids']) == sorted(by_id[r['id']]['source_record_ids']) and r.get('audit_note')
            validate_quality(r['quality'], manifest['checked_on'], url)
            audits[r['id']] = str(CAMPAIGN/'audits'/(batch+'.json'))
    partitions = manifest['reviews']; all_reviewed = [x for group in partitions.values() for x in group]
    assert len(partitions) == 4 and len(all_reviewed) == len(set(all_reviewed)) == 146 and set(all_reviewed) == set(ids), 'Invalid quality review partition'
    for name, expected in partitions.items():
        d = doc(base/name, 'quality_review')
        if d is None: continue
        assert d['checked_on'] == manifest['checked_on'] and isinstance(d.get('notes'), str)
        task = d.get('agent_task'); assert isinstance(task,str) and task.strip(); tasks.append(task)
        reviewed = d['reviewed_ids']; findings = d['findings']; fids = [f['id'] for f in findings]
        assert len(reviewed) == len(set(reviewed)) and set(reviewed) == set(expected) and len(fids) == len(set(fids)) and set(fids) == set(expected), f'{name}: invalid review coverage'
        for f in findings:
            assert f.get('verdict') in {'confirm','correct','unresolved'} and f.get('reasoning') and isinstance(f.get('sources'),list)
            for s in f['sources']: assert url(s.get('url')) and s.get('access') in ACCESS and s.get('note')
            if f['verdict'] == 'correct': validate_quality(f['quality'], manifest['checked_on'], url)
            reviews[f['id']] = str(CAMPAIGN/name)
    decisions = doc(base/'decisions.json', 'quality_decisions')
    assert len(tasks) == len(set(tasks)) and '/root' not in tasks, 'Quality tasks must be distinct'
    if local_missing:
        if not allow_incomplete: raise SystemExit('Missing quality inputs: ' + ', '.join(local_missing))
        return
    assert len(tasks) == 20 and decisions['checked_on'] == manifest['checked_on'] and decisions['performed_by'] == '/root'
    entries = decisions['decisions']; dids = [d['id'] for d in entries]
    assert len(dids) == len(set(dids)) == 146 and set(dids) == set(ids), 'Invalid quality decision coverage'
    for d in entries:
        ident = d['id']; assert sorted(d['source_record_ids']) == sorted(by_id[ident]['source_record_ids']) and d['audit_file'] == audits[ident] and d['review_file'] == reviews[ident]
        assert d.get('audit_note') and isinstance(d.get('source_urls'),list) and d['source_urls'] and all(url(x) for x in d['source_urls'])
        validate_quality(d['quality'], manifest['checked_on'], url)
        supplements = d.get('supplemental_files', [])
        assert isinstance(supplements, list) and len(supplements) == len(set(supplements))
        for path in supplements:
            assert isinstance(path, str) and path in supplemental and ident in supplemental[path], f'{ident}: invalid supplemental evidence path or record: {path}'
        correction = d.get('review_correction')
        if correction:
            assert correction.get('type') in {'peer_reviewed','editorial','moderation','none','unknown'} and correction.get('reason') and correction.get('source_urls') and all(url(x) for x in correction['source_urls'])
        matching = [m for m in memberships if m['id'] in d['source_record_ids']]
        assert len(matching) == len(d['source_record_ids'])
        for m in matching:
            m['quality'] = copy.deepcopy(d['quality'])
            if correction:
                m['review']['type'] = correction['type']; m['review']['source_urls'] = list(dict.fromkeys(m['review'].get('source_urls', []) + correction['source_urls']))
            m['source_files'].extend([audits[ident], reviews[ident], str(CAMPAIGN/'decisions.json')] + supplements)
