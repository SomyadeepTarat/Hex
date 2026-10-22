"""Exercise ASGI endpoints with isolated SQLite, without an external test client."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.hex import api, db, planning

async def request(method, path, body=None, token=None):
    messages = []
    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {'type':'http.request', 'body':json.dumps(body).encode() if body is not None else b'', 'more_body':False}
        await asyncio.sleep(0)
        return {'type':'http.disconnect'}
    async def send(message):
        messages.append(message)
    headers = [(b'content-type', b'application/json')]
    if token:
        headers.append((b'authorization', f'Bearer {token}'.encode()))
    scope = dict(type='http', asgi={'version':'3.0'}, http_version='1.1', method=method, scheme='http', path=path, raw_path=path.encode(), query_string=b'', root_path='', headers=headers, client=('test',123), server=('test',80))
    await api.app(scope, receive, send)
    status = next(m['status'] for m in messages if m['type']=='http.response.start')
    raw = b''.join(m.get('body', b'') for m in messages if m['type']=='http.response.body')
    return status, json.loads(raw) if raw else None

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / 'test.db'
        db.init_db()
        db.seed_cases()
        self.schedule = patch.object(planning, 'request_run')
        self.schedule.start()
        self.hospital = self.call('POST','/api/auth/login', {'username':'operator-hosp01','password':'demo-hospital'})[1]['token']
        self.admin = self.call('POST','/api/auth/login', {'username':'coordinator','password':'demo-government'})[1]['token']
    def tearDown(self):
        self.schedule.stop()
        db.DB_PATH = self.old
        self.temp.cleanup()
    def call(self, method, path, body=None, token=None):
        return asyncio.run(request(method,path,body,token))
    def test_permissions(self):
        self.assertEqual(self.call('POST','/api/planning/run')[0],401)
        self.assertEqual(self.call('GET','/api/audit')[0],401)
        data=dict(staffed_general_beds=120,occupied_general_beds=100,accepting_patients=True)
        self.assertEqual(self.call('PUT','/api/hospitals/HOSP-02/status',data,self.hospital)[0],403)
        data['occupied_general_beds']=121
        self.assertEqual(self.call('PUT','/api/hospitals/HOSP-01/status',data,self.hospital)[0],422)
        self.assertEqual(self.call('PUT','/api/planning/settings',dict(budget_units=20,scenario_count=10,horizon_days=7),self.hospital)[0],403)
    def test_live_recommendations_and_planned_capacity(self):
        query=dict(symptoms=['cough'],zone_id='ZONE-03')
        before=self.call('POST','/api/public/recommendations',query)[1]
        self.assertEqual(before['suggested_hospital_id'],'HOSP-01')
        self.call('PUT','/api/hospitals/HOSP-01/constraints',dict(max_additional_staffed_beds=12,transfer_out_limit_per_day=3),self.hospital)
        after=self.call('POST','/api/public/recommendations',query)[1]
        self.assertEqual(before,after)
        self.call('PUT','/api/hospitals/HOSP-01/status',dict(staffed_general_beds=120,occupied_general_beds=110,accepting_patients=False),self.hospital)
        after=self.call('POST','/api/public/recommendations',query)[1]
        self.assertNotEqual(after['suggested_hospital_id'],'HOSP-01')
        self.assertEqual(self.call('GET','/api/planning/state',token=self.hospital)[1]['case_count'],len(planning.snapshot()['cases']))
    def test_proposal_preview_apply_audit_and_staleness(self):
        payload=dict(message='Set HOSP-01 maximum additional staffed beds to 12.')
        p=self.call('POST','/api/chat/proposals',payload,self.hospital)[1]
        self.assertEqual(p['old_value'],0)
        with db.connect() as conn:
            self.assertEqual(conn.execute('SELECT max_additional_staffed_beds FROM hospital_constraints WHERE hospital_id="HOSP-01"').fetchone()[0],0)
        self.assertEqual(self.call('POST',f"/api/chat/proposals/{p['proposal_id']}/apply",token=self.admin)[0],404)
        self.assertEqual(self.call('POST',f"/api/chat/proposals/{p['proposal_id']}/apply",token=self.hospital)[0],200)
        self.assertEqual(self.call('POST',f"/api/chat/proposals/{p['proposal_id']}/apply",token=self.hospital)[0],409)
        self.assertEqual(self.call('GET','/api/audit',token=self.hospital)[1]['events'][0]['operation'],'apply_proposal')
        p=self.call('POST','/api/chat/proposals',payload,self.hospital)[1]
        self.call('PUT','/api/hospitals/HOSP-01/constraints',dict(max_additional_staffed_beds=3,transfer_out_limit_per_day=0),self.hospital)
        self.assertEqual(self.call('POST',f"/api/chat/proposals/{p['proposal_id']}/apply",token=self.hospital)[0],409)
    def test_versioned_recomputation_and_failure_isolation(self):
        planning.worker()
        state=planning.state()
        self.assertIsNotNone(state['result'])
        self.assertFalse(state['outdated'])
        original=api.planning.run_analysis
        def superseded(**kwargs):
            result=original(**kwargs)
            with db.connect() as conn:
                conn.execute('UPDATE network_settings SET version=version+1')
            return result
        with patch.object(planning,'run_analysis',side_effect=superseded):
            planning.worker()
        self.assertTrue(planning.state()['outdated'])
        with patch.object(planning,'run_analysis',side_effect=ValueError('forced failure')):
            planning.worker()
        self.assertEqual(self.call('GET','/api/public/hospitals')[0],200)
        self.assertEqual(planning.state()['error'],'forced failure')
        planning.worker()
    def test_synthetic_feed_role_and_emergency(self):
        self.assertEqual(self.call('POST','/api/demo/feed/normal',token=self.hospital)[0],403)
        self.assertEqual(self.call('POST','/api/demo/feed/normal',token=self.admin)[0],200)
        result=self.call('POST','/api/public/recommendations',dict(symptoms=['severe_breathing_difficulty']))[1]
        self.assertTrue(result['emergency_guidance_required'])

if __name__=='__main__':unittest.main()
