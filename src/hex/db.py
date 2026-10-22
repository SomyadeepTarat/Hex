"""SQLite persistence for HEX's local, fictional demonstration environment."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "hex.db"
HOSPITALS_CSV = ROOT / "data" / "raw" / "demo_hospitals.csv"
ZONES_CSV = ROOT / "data" / "raw" / "demo_zones.csv"


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000).hex()


def init_db():
    import csv

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS case_signals (case_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS proposals (proposal_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, payload TEXT NOT NULL,
            status_version INTEGER NOT NULL, constraints_version INTEGER NOT NULL, applied INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS hospital_capabilities (
            hospital_id TEXT PRIMARY KEY REFERENCES hospitals(hospital_id),
            payload TEXT NOT NULL, reported_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS hospitals (
            hospital_id TEXT PRIMARY KEY, name TEXT NOT NULL, zone_id TEXT NOT NULL,
            services TEXT NOT NULL, emergency_service_available INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS reported_status (
            hospital_id TEXT PRIMARY KEY REFERENCES hospitals(hospital_id),
            staffed_general_beds INTEGER, occupied_general_beds INTEGER,
            accepting_patients INTEGER, reported_at TEXT, version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS hospital_constraints (
            hospital_id TEXT PRIMARY KEY REFERENCES hospitals(hospital_id),
            max_additional_staffed_beds INTEGER NOT NULL DEFAULT 0,
            transfer_out_limit_per_day INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS network_settings (
            id INTEGER PRIMARY KEY CHECK(id=1), scenario_count INTEGER NOT NULL,
            horizon_days INTEGER NOT NULL, seed INTEGER NOT NULL, budget_units INTEGER NOT NULL,
            version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS users (
            actor_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
            hospital_id TEXT, salt TEXT NOT NULL, password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(actor_id),
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL, actor_role TEXT NOT NULL,
            target TEXT NOT NULL, operation TEXT NOT NULL, before_json TEXT, after_json TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS plan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, status_version INTEGER NOT NULL,
            constraints_version INTEGER NOT NULL, generated_at TEXT NOT NULL,
            result_json TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1
        );
        """)
        if db.execute("SELECT count(*) FROM hospitals").fetchone()[0] == 0:
            with HOSPITALS_CSV.open(newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    services = ["general", "respiratory", "emergency"]
                    db.execute("INSERT INTO hospitals VALUES (?,?,?,?,?)", (
                        row["hospital_id"], row["name"], row["zone_id"], json.dumps(services), 1))
                    # Initial capacity is a demo assumption from the fictional source file.
                    db.execute("INSERT INTO reported_status VALUES (?,?,?,?,?,1)", (
                        row["hospital_id"], int(row["general_beds"]),
                        int(row["occupied_general_beds"]), 1, now()))
                    db.execute("INSERT INTO hospital_constraints VALUES (?,?,?,1)", (
                        row["hospital_id"], 0, 0))
        if db.execute("SELECT count(*) FROM network_settings").fetchone()[0] == 0:
            db.execute("INSERT INTO network_settings VALUES (1,100,14,42,100,1)")
        demo_users = [
            ("public", "public-demo", "public", None, "demo-public"),
            ("operator_hosp01", "operator-hosp01", "hospital", "HOSP-01", "demo-hospital"),
            ("operator_hosp02", "operator-hosp02", "hospital", "HOSP-02", "demo-hospital"),
            ("operator_hosp03", "operator-hosp03", "hospital", "HOSP-03", "demo-hospital"),
            ("coordinator", "coordinator", "government", None, "demo-government"),
        ]
        for actor_id, username, role, hospital_id, password in demo_users:
            if not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                salt = secrets.token_bytes(16)
                db.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (
                    actor_id, username, role, hospital_id, salt.hex(), _password_hash(password, salt)))

    profiles = json.loads((ROOT / 'data/synthetic/hospital_capabilities.json').read_text())
    with connect() as conn:
        for hid, profile in profiles.items():
            if conn.execute('SELECT 1 FROM hospitals WHERE hospital_id=?', (hid,)).fetchone():
                conn.execute('INSERT OR IGNORE INTO hospital_capabilities(hospital_id,payload,reported_at) VALUES(?,?,?)', (hid, json.dumps(profile), now()))


def authenticate(username: str, password: str):
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or not secrets.compare_digest(_password_hash(password, bytes.fromhex(row["salt"])), row["password_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions VALUES (?,?,?)", (
            hashlib.sha256(token.encode()).hexdigest(), row["actor_id"],
            (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()))
        return {"token": token, "actor_id": row["actor_id"], "role": row["role"], "hospital_id": row["hospital_id"]}


def get_actor(token: str | None):
    if not token:
        return None
    with connect() as db:
        return db.execute("""SELECT u.actor_id,u.username,u.role,u.hospital_id FROM sessions s
            JOIN users u ON u.actor_id=s.actor_id WHERE s.token_hash=? AND s.expires_at>?""",
            (hashlib.sha256(token.encode()).hexdigest(), now())).fetchone()


def seed_cases():
    import csv
    path = ROOT / 'data/synthetic/generated/cases_surge.csv'
    with connect() as conn:
        if conn.execute('SELECT COUNT(*) FROM case_signals').fetchone()[0] == 0:
            with path.open() as handle:
                conn.executemany('INSERT INTO case_signals VALUES(?,?)', [(r['case_id'], json.dumps(r)) for r in csv.DictReader(handle)])
