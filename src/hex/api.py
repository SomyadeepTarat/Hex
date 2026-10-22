"""Unified HEX demo: public finder + hospital workspace, one central database."""
import csv
import json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from . import db, planning
from .facility_recommendation import recommend_facilities
from .constraint_parser import parse_constraint_message

app = FastAPI(title='HEX central hospital system')

@app.middleware('http')
async def fresh_local_interfaces(request, call_next):
    response = await call_next(request)
    if request.url.path == '/' or request.url.path.startswith(('/find-care', '/hospital')):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    return response

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Login(Input):
    username: str
    password: str
class Status(Input):
    staffed_general_beds: int = Field(ge=0, le=10000, strict=True)
    occupied_general_beds: int = Field(ge=0, le=10000, strict=True)
    accepting_patients: bool
class Constraints(Input):
    max_additional_staffed_beds: int = Field(ge=0, le=500, strict=True)
    transfer_out_limit_per_day: int = Field(ge=0, le=500, strict=True)
class Settings(Input):
    budget_units: int = Field(ge=0, le=100000, strict=True)
    scenario_count: int = Field(ge=1, le=500, strict=True)
    horizon_days: int = Field(ge=1, le=60, strict=True)
class Search(Input):
    symptoms: list[str] = Field(min_length=1, max_length=30)
    zone_id: str | None = None
class Message(Input):
    message: str = Field(min_length=1, max_length=1000)


def actor(authorization: str | None = Header(default=None)):
    user = db.get_actor(authorization.removeprefix('Bearer ') if authorization else None)
    if not user:
        raise HTTPException(401, 'Sign in to the hospital workspace')
    return dict(user)

def operator(user=Depends(actor)):
    if user['role'] not in ('hospital', 'government'):
        raise HTTPException(403, 'Hospital workspace access required')
    return user

def own(user, hid):
    if user['role'] != 'government' and user['hospital_id'] != hid:
        raise HTTPException(403, 'You can update only your own hospital')

def audit(conn, user, target, operation, before, after):
    conn.execute('INSERT INTO audit_events(actor_id,actor_role,target,operation,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)', (user['actor_id'], user['role'], target, operation, json.dumps(before), json.dumps(after), db.now()))

def hospital_rows():
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute('SELECT h.*,s.staffed_general_beds,s.occupied_general_beds,s.accepting_patients,s.reported_at,s.version FROM hospitals h LEFT JOIN reported_status s USING(hospital_id) ORDER BY hospital_id')]
    with db.ZONES_CSV.open() as handle:
        zones = list(csv.DictReader(handle))
    for row in rows:
        row['services'] = json.loads(row['services'])
        row['accepting_patients'] = bool(row['accepting_patients']) if row['accepting_patients'] is not None else None
        row['neighboring_zones'] = next(z['neighboring_zones'].split('|') for z in zones if z['zone_id'] == row['zone_id'])
    return rows, zones

@app.on_event('startup')
def startup():
    db.init_db()
    db.seed_cases()
    planning.request_run()

@app.get('/api/health')
def health():
    return dict(status='ok', environment='Synthetic demo')

@app.get('/api/public/hospitals')
def public_hospitals():
    hospitals, zones = hospital_rows()
    return dict(hospitals=hospitals, zones=zones, environment='Synthetic demo')

@app.post('/api/public/recommendations')
def recommendations(payload: Search):
    hospitals, zones = hospital_rows()
    if payload.zone_id and payload.zone_id not in {z['zone_id'] for z in zones}:
        raise HTTPException(422, 'Unknown zone')
    aliases = {'breathlessness': 'shortness_of_breath', 'nausea': 'vomiting', 'cannot_breathe': 'severe_breathing_difficulty', 'chest_pain': 'severe_chest_pain', 'blue_lips': 'severe_breathing_difficulty'}
    symptoms = [aliases.get(s.strip().lower().replace(' ', '_'), s.strip().lower().replace(' ', '_')) for s in payload.symptoms]
    result = recommend_facilities(symptoms, payload.zone_id, hospitals, hospitals, datetime.now(timezone.utc))
    for h in result['alternatives']:
        source = next(r for r in hospitals if r['hospital_id'] == h['hospital_id'])
        h.update(name=source['name'], zone_id=source['zone_id'])
    result['suggested_facility'] = next((h for h in result['alternatives'] if h['hospital_id'] == result['suggested_hospital_id']), None)
    return result

@app.post('/api/auth/login')
def login(payload: Login):
    result = db.authenticate(payload.username, payload.password)
    if not result:
        raise HTTPException(401, 'Invalid username or password')
    return result

@app.get('/api/auth/me')
def me(user=Depends(operator)):
    return user

@app.post('/api/auth/logout')
def logout(user=Depends(actor), authorization: str = Header()):
    import hashlib
    with db.connect() as conn:
        conn.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(authorization.removeprefix('Bearer ').encode()).hexdigest(),))
    return dict(ok=True)

@app.put('/api/hospitals/{hid}/status')
def update_status(hid: str, payload: Status, user=Depends(operator)):
    own(user, hid)
    if payload.occupied_general_beds > payload.staffed_general_beds:
        raise HTTPException(422, 'Occupied beds cannot exceed staffed beds')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM reported_status WHERE hospital_id=?', (hid,)).fetchone()
        if not old:
            raise HTTPException(404, 'Hospital not found')
        new = dict(**payload.model_dump(), reported_at=db.now(), version=old['version'] + 1)
        conn.execute('UPDATE reported_status SET staffed_general_beds=?,occupied_general_beds=?,accepting_patients=?,reported_at=?,version=? WHERE hospital_id=?', (payload.staffed_general_beds, payload.occupied_general_beds, int(payload.accepting_patients), new['reported_at'], new['version'], hid))
        audit(conn, user, hid, 'report_status', dict(old), new)
    planning.request_run()
    return dict(status=new)

@app.put('/api/hospitals/{hid}/constraints')
def update_constraints(hid: str, payload: Constraints, user=Depends(operator)):
    own(user, hid)
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM hospital_constraints WHERE hospital_id=?', (hid,)).fetchone()
        if not old:
            raise HTTPException(404, 'Hospital not found')
        conn.execute('UPDATE hospital_constraints SET max_additional_staffed_beds=?,transfer_out_limit_per_day=?,version=version+1 WHERE hospital_id=?', (*payload.model_dump().values(), hid))
        audit(conn, user, hid, 'planning_constraints', dict(old), payload.model_dump())
    planning.request_run()
    return dict(ok=True)

@app.put('/api/planning/settings')
def update_settings(payload: Settings, user=Depends(operator)):
    if user['role'] != 'government':
        raise HTTPException(403, 'Network administrator required')
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = dict(conn.execute('SELECT * FROM network_settings WHERE id=1').fetchone())
        conn.execute('UPDATE network_settings SET budget_units=?,scenario_count=?,horizon_days=?,version=version+1 WHERE id=1', tuple(payload.model_dump().values()))
        audit(conn, user, 'network', 'network_settings', old, payload.model_dump())
    planning.request_run()
    return dict(ok=True)

@app.get('/api/planning/state')
def state(user=Depends(operator)):
    result = planning.state()
    with db.connect() as conn:
        result['constraints'] = [dict(r) for r in conn.execute('SELECT * FROM hospital_constraints') if user['role'] == 'government' or r['hospital_id'] == user['hospital_id']]
        result['settings'] = dict(conn.execute('SELECT * FROM network_settings WHERE id=1').fetchone())
        result['case_count'] = conn.execute('SELECT COUNT(*) FROM case_signals').fetchone()[0]
    return result

@app.post('/api/planning/run')
def run(user=Depends(operator)):
    planning.request_run()
    return dict(updating=True)

@app.post('/api/chat/proposals')
def proposal(payload: Message, user=Depends(operator)):
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current = dict(hospitals=[dict(r) for r in conn.execute('SELECT h.hospital_id,h.name,c.max_additional_staffed_beds,c.transfer_out_limit_per_day FROM hospitals h JOIN hospital_constraints c USING(hospital_id)')], settings=dict(conn.execute('SELECT * FROM network_settings WHERE id=1').fetchone()))
        result = parse_constraint_message(payload.message, user, current)
        if result['action'] == 'propose_change':
            pid = str(uuid4())
            conn.execute('INSERT INTO proposals(proposal_id,actor_id,payload,status_version,constraints_version) VALUES(?,?,?,?,?)', (pid, user['actor_id'], json.dumps(result), *planning.versions(conn)))
            result['proposal_id'] = pid
        elif result['action'] == 'show_constraints':
            result['current_constraints'] = [h for h in current['hospitals'] if user['role'] == 'government' or h['hospital_id'] == user['hospital_id']]
    return result

@app.post('/api/chat/proposals/{pid}/apply')
def apply(pid: str, user=Depends(operator)):
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM proposals WHERE proposal_id=? AND actor_id=?', (pid, user['actor_id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Proposal not found')
        if row['applied'] or (row['status_version'], row['constraints_version']) != planning.versions(conn):
            raise HTTPException(409, 'Proposal is stale or already applied. Request a new preview.')
        p = json.loads(row['payload'])
        own(user, p['target'])
        fields = {'budget_units', 'scenario_count', 'max_additional_staffed_beds', 'transfer_out_limit_per_day'}
        if p['field'] not in fields:
            raise HTTPException(422, 'Unsupported field')
        if p['target'] == 'network':
            if user['role'] != 'government' or p['field'] not in {'budget_units', 'scenario_count'}:
                raise HTTPException(403, 'Network administrator required')
            conn.execute(f"UPDATE network_settings SET {p['field']}=?,version=version+1 WHERE id=1", (p['new_value'],))
        else:
            if p['field'] not in {'max_additional_staffed_beds', 'transfer_out_limit_per_day'}:
                raise HTTPException(422, 'Unsupported hospital field')
            conn.execute(f"UPDATE hospital_constraints SET {p['field']}=?,version=version+1 WHERE hospital_id=?", (p['new_value'], p['target']))
        conn.execute('UPDATE proposals SET applied=1 WHERE proposal_id=?', (pid,))
        audit(conn, user, p['target'], 'apply_proposal', {p['field']: p['old_value']}, {p['field']: p['new_value']})
    planning.request_run()
    return dict(ok=True)

@app.get('/api/audit')
def events(user=Depends(operator)):
    with db.connect() as conn:
        rows = conn.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT 100').fetchall()
    return dict(events=[dict(r) for r in rows if user['role'] == 'government' or r['target'] == user['hospital_id']])

@app.post('/api/demo/feed/{mode}')
def demo_feed(mode: str, user=Depends(operator)):
    if user['role'] != 'government':
        raise HTTPException(403, 'Network administrator required for replacing the network case feed')
    if mode not in {'normal', 'surge'}:
        raise HTTPException(422, 'Choose normal or surge')
    with (db.ROOT / f'data/synthetic/generated/cases_{mode}.csv').open() as handle:
        cases = list(csv.DictReader(handle))
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old_count = conn.execute('SELECT COUNT(*) FROM case_signals').fetchone()[0]
        conn.execute('DELETE FROM case_signals')
        conn.executemany('INSERT INTO case_signals VALUES(?,?)', [(r['case_id'], json.dumps(r)) for r in cases])
        conn.execute('UPDATE network_settings SET version=version+1 WHERE id=1')
        audit(conn, user, 'network', 'synthetic_feed', {'case_count': old_count}, {'mode': mode, 'case_count': len(cases)})
    planning.request_run()
    return dict(ok=True, case_count=len(cases), mode=mode)

@app.get('/api/ml/evaluation')
def ml_evaluation(user=Depends(operator)):
    path = db.ROOT / 'models/evaluation.json'
    return json.loads(path.read_text()) if path.exists() else dict(available=False)

@app.get('/')
def home():
    return RedirectResponse('/find-care/')

@app.get('/src/hex/dashboard/')
def old_dashboard():
    return RedirectResponse('/hospital/')

app.mount('/find-care', StaticFiles(directory=str(db.ROOT / 'src/hex/public'), html=True), name='public')
app.mount('/hospital', StaticFiles(directory=str(db.ROOT / 'src/hex/workspace'), html=True), name='hospital')
