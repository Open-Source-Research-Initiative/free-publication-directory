#!/usr/bin/env python3
"""Focused isolated checks for the follow-up gate; never writes canonical data."""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import build
from fee_followup import apply, CAMPAIGN

class FollowupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("fee_followup.apply"), patch("quality_followup.apply"):
            cls.memberships = build.load_memberships(True)[1]
        cls.source = build.ROOT / CAMPAIGN
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(build.ROOT))
        self.root = Path(self.temp.name)
        self.base = self.root / CAMPAIGN
        shutil.copytree(self.source, self.base)
        self.baseline = build.read(self.base / 'baseline.json')
        manifest = build.read(self.base / 'campaign.json')
        self.audit_map = {}
        for batch in manifest['batches']:
            for patch in build.read(self.base / 'audits' / (batch+'.json'))['patches']:
                self.audit_map[patch['id']] = (batch, patch)
        for i, name in enumerate(manifest['review_files']):
            ids = [v['id'] for v in self.baseline[i*37:(i+1)*37]]
            self.write(name, {'checked_on':manifest['checked_on'], 'agent_task':f'/test/reviewer{i}', 'reviewed_ids':ids, 'findings':[{'id':ident,'verdict':'unresolved','reasoning':'Test','sources':[]} for ident in ids]})
        decisions = []
        for i, v in enumerate(self.baseline):
            batch, patch = self.audit_map[v['id']]
            decisions.append({'id':v['id'], 'source_record_ids':v['source_record_ids'], 'route':v['route'], 'cost_checks':{k:{'status':'unverified','source_urls':[],'rationale':'Test'} for k in ('submission','publication','mandatory_costs')}, 'audit_note':'Test', 'source_urls':[v['homepage']], 'audit_file':str(CAMPAIGN / 'audits' / (batch+'.json')), 'review_file':str(CAMPAIGN / manifest['review_files'][i//37])})
        self.write('decisions.json', {'checked_on':manifest['checked_on'], 'performed_by':'/root', 'decisions':decisions})
    def tearDown(self): self.temp.cleanup()
    def write(self, name, value):
        p = self.base / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(value))
    def run_apply(self, members):
        receipt=[]; missing=[]
        apply(self.root, members, receipt, missing, False, build.read, build.consolidate, build.ai_compatible, build.url)
        return receipt
    def test_success_preserves_other_fields(self):
        members = copy.deepcopy(self.memberships); before = copy.deepcopy(members)
        self.run_apply(members)
        for old, new in zip(before, members):
            for key in old.keys() - {'route','source_files'}: self.assertEqual(old[key], new[key])
    def test_changed_baseline(self):
        with (self.base / 'baseline.json').open('a') as f: f.write(' ')
        with self.assertRaisesRegex(AssertionError, 'hash mismatch'): self.run_apply(copy.deepcopy(self.memberships))
    def test_changed_source_cost_data(self):
        members = copy.deepcopy(self.memberships)
        ident = self.baseline[0]['source_record_ids'][0]
        next(m for m in members if m['id'] == ident)['route']['conditions'] += ' Changed source cost condition.'
        with self.assertRaisesRegex(AssertionError, 'baseline cost data changed'): self.run_apply(members)
    def test_decision_coverage(self):
        doc=build.read(self.base / 'decisions.json'); doc['decisions'][0]=copy.deepcopy(doc['decisions'][1]); self.write('decisions.json',doc)
        with self.assertRaisesRegex(AssertionError, 'decision coverage'): self.run_apply(copy.deepcopy(self.memberships))
    def test_review_partition(self):
        doc=build.read(self.base / 'reviews/first-half.json'); doc['reviewed_ids'][0]=doc['reviewed_ids'][1]; self.write('reviews/first-half.json',doc)
        with self.assertRaisesRegex(AssertionError, 'review partition'): self.run_apply(copy.deepcopy(self.memberships))
    def test_uncleared_promotion(self):
        doc=build.read(self.base / 'decisions.json'); doc['decisions'][0]['route']['eligibility']='verified_free'; self.write('decisions.json',doc)
        with self.assertRaisesRegex(AssertionError, 'uncleared'): self.run_apply(copy.deepcopy(self.memberships))

if __name__ == '__main__': unittest.main()
