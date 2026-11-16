"""Validate and apply the bounded, independently reviewed cost follow-up."""
import copy
import hashlib
from pathlib import Path

CAMPAIGN = Path('research/campaigns/2026-11-16-cost-followup')


def apply(root, memberships, receipt, missing, allow_incomplete, read, consolidate, ai_compatible, url):
    base = root / CAMPAIGN
    if not base.exists():
        return
    def include(path, role):
        receipt.append({'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'role': role, 'subfield': None})
    def required(path, role):
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
            return None
        include(path, role)
        return read(path)
    manifest = required(base / 'campaign.json', 'fee_followup_campaign')
    contract = base / 'CONTRACT.md'
    if contract.is_file(): include(contract, 'fee_followup_contract')
    else: missing.append(str(contract.relative_to(root)))
    for path in sorted(base.glob('policy-*.json')):
        include(path, 'fee_followup_policy')
    baseline_path = base / 'baseline.json'
    baseline = required(baseline_path, 'fee_followup_baseline')
    if manifest is None or baseline is None:
        if not allow_incomplete: raise SystemExit('Missing required follow-up files: ' + ', '.join(missing))
        return
    assert hashlib.sha256(baseline_path.read_bytes()).hexdigest() == manifest['baseline_sha256'], 'Follow-up baseline hash mismatch'
    ids = [v['id'] for v in baseline]
    assert len(ids) == len(set(ids)) == manifest['target_count'] == 74, 'Invalid follow-up baseline IDs'
    by_id = {v['id']: v for v in baseline}
    candidates, _ = consolidate(memberships)
    current = {v['id']: v for v in candidates if ai_compatible(v) and v['route']['eligibility'] == 'needs_verification'}
    assert set(current) == set(ids), 'Follow-up baseline does not match current unresolved AI-compatible venues'
    for ident in ids:
        assert sorted(current[ident]['source_record_ids']) == sorted(by_id[ident]['source_record_ids']), f'{ident}: baseline source IDs changed'
        assert current[ident]['route'] == by_id[ident]['route'], f'{ident}: baseline cost data changed; recheck follow-up decisions'
    batches = manifest['batches']
    assigned = [ident for group in batches.values() for ident in group]
    assert len(batches) == 8 and len(assigned) == len(set(assigned)) == 74 and set(assigned) == set(ids), 'Invalid batch partition'
    audits, reviews, tasks = {}, {}, []
    for batch, batch_ids in batches.items():
        assignment = required(base / 'assignments' / (batch + '.json'), 'fee_followup_assignment')
        if assignment is not None:
            assert assignment['batch'] == batch and [v['id'] for v in assignment['venues']] == batch_ids, f'{batch}: invalid assignment'
            for v in assignment['venues']:
                assert sorted(v['source_record_ids']) == sorted(by_id[v['id']]['source_record_ids']), f'{batch}: assignment source IDs changed'
        doc = required(base / 'audits' / (batch + '.json'), 'fee_followup_audit')
        if doc is None: continue
        assert doc['batch'] == batch and doc['checked_on'] == manifest['checked_on'] and doc.get('notes') is not None
        task = doc.get('agent_task'); assert isinstance(task, str) and task.strip(); tasks.append(task)
        patches = doc['patches']; pids = [p['id'] for p in patches]
        assert len(pids) == len(set(pids)) and set(pids) == set(batch_ids), f'{batch}: invalid audit coverage'
        for p in patches:
            assert sorted(p['source_record_ids']) == sorted(by_id[p['id']]['source_record_ids']), f'{p["id"]}: audit source IDs changed'
            assert isinstance(p.get('audit_note'), str) and p['audit_note'].strip() and isinstance(p.get('route'), dict), f'{p["id"]}: invalid audit patch'
            assert isinstance(p.get('sources'), list), f'{p["id"]}: invalid audit sources'
            for source in p['sources']:
                assert url(source.get('url')) and source.get('checked_on') and source.get('access') in {'page','search_snippet','blocked','unavailable'} and source.get('applicability') and source.get('note'), f'{p["id"]}: invalid audit source'
            for key, statuses in [('submission', {'free','charged','unverified'}), ('publication', {'free','charged','unverified'}), ('mandatory_costs', {'none_for_route','charged','unverified'})]:
                c = p['cost_checks'][key]
                assert c.get('status') in statuses and isinstance(c.get('source_urls'), list) and all(url(u) for u in c['source_urls']) and c.get('rationale'), f'{p["id"]}: invalid audit cost check'
            audits[p['id']] = (p, str((CAMPAIGN / 'audits' / (batch + '.json'))))
    review_files = manifest['review_files']
    assert review_files == ['reviews/first-half.json', 'reviews/second-half.json']
    for index, name in enumerate(review_files):
        doc = required(base / name, 'fee_followup_review')
        if doc is None: continue
        expected = ids[index * 37:(index + 1) * 37]
        reviewed = doc['reviewed_ids']
        assert len(reviewed) == len(set(reviewed)) == 37 and set(reviewed) == set(expected), f'{name}: invalid review partition'
        findings = doc['findings']
        assert isinstance(findings, list) and len(findings) == 37 and {f['id'] for f in findings} == set(expected), f'{name}: invalid findings coverage'
        for finding in findings:
            assert finding.get('verdict') in {'confirm', 'correct', 'unresolved'} and finding.get('reasoning') and isinstance(finding.get('sources'), list), f'{name}: invalid finding'
            for source in finding['sources']:
                assert url(source.get('url')) and source.get('access') in {'page', 'search_snippet', 'blocked', 'unavailable'} and isinstance(source.get('note'), str) and source['note'].strip(), f'{name}: invalid review source'
            reviews[finding['id']] = str(CAMPAIGN / name)
        task = doc.get('agent_task'); assert isinstance(task, str) and task.strip(); tasks.append(task)
        assert doc['checked_on'] == manifest['checked_on']
    decisions_path = base / 'decisions.json'
    decisions = required(decisions_path, 'fee_followup_decisions')
    assert len(tasks) == len(set(tasks)) and '/root' not in tasks, 'Follow-up reviewers and auditors must be distinct tasks'
    if missing:
        if not allow_incomplete: raise SystemExit('Missing required follow-up files:\n' + '\n'.join(missing))
        return
    assert len(tasks) == 10
    assert decisions['checked_on'] == manifest['checked_on'] and decisions['performed_by'] == '/root'
    entries = decisions['decisions']; dids = [d['id'] for d in entries]
    assert len(dids) == len(set(dids)) == 74 and set(dids) == set(ids), 'Invalid decision coverage'
    for d in entries:
        ident = d['id']; audit, audit_path = audits[ident]
        assert sorted(d['source_record_ids']) == sorted(by_id[ident]['source_record_ids']), f'{ident}: decision source IDs changed'
        assert d['audit_file'] == audit_path and d['review_file'] == reviews[ident], f'{ident}: wrong evidence paths'
        assert isinstance(d.get('audit_note'), str) and d['audit_note'].strip()
        assert isinstance(d.get('source_urls'), list) and d['source_urls'] and all(url(x) for x in d['source_urls'])
        route = d['route']; checks = d['cost_checks']
        assert set(('model','submission_fee','publication_fee','eligibility','oa_status','conditions','other_mandatory_costs','fee_evidence')) <= set(route), f'{ident}: incomplete route'
        sources = audit.get('sources', []) + d.get('adjudication_sources', [])
        for key, allowed in [('submission', {'free','charged','unverified'}), ('publication', {'free','charged','unverified'}), ('mandatory_costs', {'none_for_route','charged','unverified'})]:
            c = checks[key]
            assert c.get('status') in allowed and isinstance(c.get('rationale'), str) and c['rationale'].strip() and isinstance(c.get('source_urls'), list) and all(url(u) for u in c['source_urls']), f'{ident}: invalid {key} check'
            if route['eligibility'] == 'verified_free':
                assert c['status'] == ('none_for_route' if key == 'mandatory_costs' else 'free') and c['source_urls'], f'{ident}: uncleared {key}'
                readable = {s.get('url') for s in sources if s.get('access') == 'page' and s.get('note')}
                assert set(c['source_urls']) <= readable, f'{ident}: {key} lacks readable cited evidence'
        if route['eligibility'] == 'verified_free':
            assert route['submission_fee'] == route['publication_fee'] == 'none' and route['model'] not in {'conditional_waiver','conditional_agreement'}, f'{ident}: invalid promotion'
        matching = [r for r in memberships if r['id'] in d['source_record_ids']]
        assert len(matching) == len(d['source_record_ids']), f'{ident}: membership mismatch'
        for member in matching:
            member['route'] = copy.deepcopy(route)
            member['source_files'].extend([audit_path, reviews[ident], str(CAMPAIGN / 'decisions.json')])
