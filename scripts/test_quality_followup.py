#!/usr/bin/env python3
"""Isolated adversarial checks of the quality campaign gate."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import build
from quality_followup import apply, CAMPAIGN, STANDARDS

class QualityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('quality_followup.apply'):
            cls.members = build.load_memberships(True)[1]
        cls.source = build.ROOT / CAMPAIGN
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=build.ROOT)
        self.root = Path(self.temp.name); self.base = self.root / CAMPAIGN
        self.base.mkdir(parents=True)
        for name in ('campaign.json','baseline.json','CONTRACT.md'): shutil.copy2(self.source/name, self.base/name)
        self.manifest = build.read(self.base/'campaign.json'); self.baseline = build.read(self.base/'baseline.json')
        byid = {v['id']:v for v in self.baseline}; self.q = self.quality()
        shutil.copytree(self.source/'assignments', self.base/'assignments')
        auditpaths = {}; reviewpaths = {}
        for n,(batch,ids) in enumerate(self.manifest['batches'].items()):
            path = 'audits/'+batch+'.json'
            self.write(path, {'checked_on':'2026-11-16','batch':batch,'agent_task':f'/test/audit{n}','notes':'test','records':[{'id':i,'source_record_ids':byid[i]['source_record_ids'],'audit_note':'test','quality':self.q} for i in ids]})
            auditpaths.update({i:str(CAMPAIGN/path) for i in ids})
        for n,(path,ids) in enumerate(self.manifest['reviews'].items()):
            self.write(path, {'checked_on':'2026-11-16','agent_task':f'/test/review{n}','reviewed_ids':ids,'notes':'test','findings':[{'id':i,'verdict':'confirm','reasoning':'test','sources':[]} for i in ids]})
            reviewpaths.update({i:str(CAMPAIGN/path) for i in ids})
        self.write('decisions.json', {'checked_on':'2026-11-16','performed_by':'/root','decisions':[{'id':v['id'],'source_record_ids':v['source_record_ids'],'quality':self.q,'audit_note':'test','source_urls':['https://example.org'],'audit_file':auditpaths[v['id']],'review_file':reviewpaths[v['id']]} for v in self.baseline]})
    def tearDown(self): self.temp.cleanup()
    def quality(self):
        u='https://example.org'; date='2026-11-16'
        standard={'status':'unclear','source_urls':[],'note':'not established'}
        standards={k:copy.deepcopy(standard) for k in STANDARDS}; standards['board']['names']=[]
        return {'checked_on':date,'status':'needs_verification','summary':'Incomplete','identity':{'issns':[],'publisher':'Publisher','source_urls':[u],'notes':'not matched'},'indexing':[{'name':'DOAJ','category':'open_access_directory','verification':'not_verified','coverage':None,'registry_url':None,'registry_record_id':None,'publisher_url':None,'matched_issns':[],'checked_on':date,'access':'unavailable','source_urls':[],'note':'unavailable'}],'peer_review':{'verification':'unclear','model':'unknown','summary':'unknown','source_urls':[],'notes':'not read'},'editorial_standards':standards,'publication_checks':[],'concerns':[],'evidence':[{'url':u,'checked_on':date,'access':'page','source_type':'journal','note':'read'}],'audit_limits':'incomplete'}
    def write(self,name,obj):
        p=self.base/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj))
    def run_gate(self,members,preview=False):
        receipt=[]; missing=[]; apply(self.root,members,receipt,missing,preview,build.read,build.consolidate,build.exclusion_reasons,build.url); return receipt,missing
    def test_success_preserves_unrelated_fields(self):
        members=copy.deepcopy(self.members); before=copy.deepcopy(members); receipt,missing=self.run_gate(members)
        self.assertFalse(missing); self.assertEqual(sum(x['role'] in {'quality_audit','quality_review'} for x in receipt),20)
        for a,b in zip(before,members):
            for key in a.keys()-{'source_files'}: self.assertEqual(a[key],b[key])
        self.assertTrue(any('quality' in m for m in members))
    def test_baseline_same_id_change(self):
        members=copy.deepcopy(self.members); ident=self.baseline[0]['source_record_ids'][0]; next(m for m in members if m['id']==ident)['route']['conditions'] += ' changed'
        with self.assertRaises(AssertionError): self.run_gate(members)
    def test_coverage(self):
        d=build.read(self.base/'decisions.json'); d['decisions'][0]=copy.deepcopy(d['decisions'][1]); self.write('decisions.json',d)
        with self.assertRaisesRegex(AssertionError,'decision coverage'): self.run_gate(copy.deepcopy(self.members))
    def test_false_registry_confirmation(self):
        d=build.read(self.base/'decisions.json'); d['decisions'][0]['quality']['indexing'][0]['verification']='registry_confirmed'; self.write('decisions.json',d)
        with self.assertRaisesRegex(AssertionError,'Registry confirmation'): self.run_gate(copy.deepcopy(self.members))
    def test_status_gate_and_hold(self):
        d=build.read(self.base/'decisions.json'); d['decisions'][0]['quality']['status']='supported'; self.write('decisions.json',d)
        with self.assertRaises(AssertionError): self.run_gate(copy.deepcopy(self.members))
        v=copy.deepcopy(self.baseline[0]); v['route'].update(eligibility='verified_free',submission_fee='none',publication_fee='none'); v['review']['type']='peer_reviewed'; self.assertTrue(build.recommended(v)); v['quality']={'status':'concerns'}; self.assertTrue(build.recommended_before_quality(v)); self.assertFalse(build.recommended(v))
    def test_supplemental_receipt_and_citation(self):
        ident=self.baseline[0]['id']; rel=str(CAMPAIGN/'completions/test.json')
        self.write('completions/test.json', {'checked_on':'2026-11-16','agent_task':'/test/supplement','batch':'test','records':[{'id':ident,'quality':self.q}]})
        self.write('registry-test.json', {'checked_on':'2026-11-16','agent_task':'/test/registry','records':[{'id':ident}]})
        d=build.read(self.base/'decisions.json'); d['decisions'][0]['supplemental_files']=[rel]; self.write('decisions.json',d)
        members=copy.deepcopy(self.members); receipt,_=self.run_gate(members)
        self.assertTrue(any(x['path']==rel and x['role']=='quality_completion' for x in receipt))
        self.assertTrue(any(x['role']=='quality_registry' for x in receipt))
        self.assertTrue(all(rel in m['source_files'] for m in members if m['id'] in self.baseline[0]['source_record_ids']))
        d['decisions'][1]['supplemental_files']=[rel]; self.write('decisions.json',d)
        with self.assertRaisesRegex(AssertionError,'invalid supplemental evidence'): self.run_gate(copy.deepcopy(self.members))
    def test_supplemental_review_citation(self):
        ident=self.baseline[0]['id']; name='reviews/supplement-source-challenge.json'; rel=str(CAMPAIGN/name)
        review={'checked_on':'2026-11-16','agent_task':'/test/challenge','scope':'sample','records':[{'id':ident,'outcome':'confirm','observations':'Checked','sources':['https://example.org']}]}
        self.write(name,review); d=build.read(self.base/'decisions.json'); d['decisions'][0]['supplemental_files']=[rel]; self.write('decisions.json',d)
        members=copy.deepcopy(self.members); receipt,_=self.run_gate(members)
        self.assertTrue(any(x['path']==rel and x['role']=='quality_supplemental_review' for x in receipt))
        self.assertTrue(all(rel in m['source_files'] for m in members if m['id'] in self.baseline[0]['source_record_ids']))
        review['records'][0]['sources']=['not-a-url']; self.write(name,review)
        with self.assertRaisesRegex(AssertionError,'invalid supplemental review'): self.run_gate(copy.deepcopy(self.members))
    def test_supplemental_duplicate_id_rejected(self):
        ident=self.baseline[0]['id']; self.write('completions/test.json', {'checked_on':'2026-11-16','agent_task':'/test/supplement','batch':'test','records':[{'id':ident,'quality':self.q},{'id':ident,'quality':self.q}]})
        with self.assertRaisesRegex(AssertionError,'supplemental record IDs'): self.run_gate(copy.deepcopy(self.members))
    def test_preview_does_not_apply_partial_decisions(self):
        (self.base/'decisions.json').unlink(); members=copy.deepcopy(self.members); before=copy.deepcopy(members)
        _,missing=self.run_gate(members,True); self.assertTrue(missing); self.assertEqual(members,before)
        with self.assertRaises(SystemExit): self.run_gate(copy.deepcopy(self.members))

if __name__ == '__main__': unittest.main()
