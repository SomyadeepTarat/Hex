"""Single-worker versioned recomputation, independent of public reads."""
import csv
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from . import db
from .pipeline import run_analysis

_executor = ThreadPoolExecutor(max_workers=1)
_lock = threading.Lock()
_running = False
_pending = False
_error = None

def versions(conn):
    status = conn.execute('SELECT COALESCE(SUM(version),0) FROM reported_status').fetchone()[0]
    constraints = conn.execute('SELECT COALESCE(SUM(version),0) FROM hospital_constraints').fetchone()[0]
    settings = conn.execute('SELECT version FROM network_settings WHERE id=1').fetchone()[0]
    return status, constraints + settings

def snapshot():
    with db.connect() as conn:
        conn.execute('BEGIN')
        status_version, constraints_version = versions(conn)
        hospitals = [dict(r) for r in conn.execute('SELECT * FROM hospitals ORDER BY hospital_id')]
        for h in hospitals:
            h['services'] = json.loads(h['services'])
        statuses = [dict(r) for r in conn.execute('SELECT * FROM reported_status')]
        constraints = [dict(r) for r in conn.execute('SELECT * FROM hospital_constraints')]
        settings = dict(conn.execute('SELECT * FROM network_settings WHERE id=1').fetchone())
        cases = [json.loads(r[0]) for r in conn.execute('SELECT payload FROM case_signals ORDER BY case_id')]
    with db.ZONES_CSV.open() as handle:
        zones = list(csv.DictReader(handle))
    settings.update(status_version=status_version, constraints_version=constraints_version)
    return dict(cases=cases, hospitals=hospitals, zones=zones, statuses=statuses, constraints=constraints, settings=settings)

def worker():
    global _running, _pending, _error
    while True:
        with _lock:
            _pending = False
        try:
            result = run_analysis(**snapshot())
            with db.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                current = versions(conn)
                if current == (result['status_version'], result['constraints_version']):
                    conn.execute('UPDATE plan_results SET is_current=0')
                    conn.execute('INSERT INTO plan_results(status_version,constraints_version,generated_at,result_json,is_current) VALUES(?,?,?,?,1)', (*current, result['generated_at'], json.dumps(result)))
            _error = None
        except Exception as exc:
            _error = str(exc)
        with _lock:
            if not _pending:
                _running = False
                return

def request_run():
    global _running, _pending
    with _lock:
        _pending = True
        if not _running:
            _running = True
            _executor.submit(worker)

def state():
    with db.connect() as conn:
        current = versions(conn)
        row = conn.execute('SELECT * FROM plan_results ORDER BY id DESC LIMIT 1').fetchone()
    result = json.loads(row['result_json']) if row else None
    outdated = not row or (row['status_version'], row['constraints_version']) != current
    return dict(result=result, updating=_running, outdated=outdated, error=_error, status_version=current[0], constraints_version=current[1])
