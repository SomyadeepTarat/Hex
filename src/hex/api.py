"""FastAPI endpoints for the fictional HEX demo."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.hex import db

app = FastAPI(title="HEX demo API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


class LoginInput(BaseModel):
    username: str
    password: str


class StatusInput(BaseModel):
    staffed_general_beds: int = Field(ge=0, le=10000)
    occupied_general_beds: int = Field(ge=0, le=10000)
    accepting_patients: bool


class ConstraintInput(BaseModel):
    max_additional_staffed_beds: int = Field(ge=0, le=10000)
    transfer_out_limit_per_day: int = Field(ge=0, le=10000)


class RecommendationInput(BaseModel):
    symptoms: list[str] = Field(default_factory=list, max_length=30)
    zone_id: str | None = None


def actor(authorization: str | None = Header(default=None)):
    token = authorization.removeprefix("Bearer ") if authorization else None
    user = db.get_actor(token)
    if not user:
        raise HTTPException(401, "Authentication required")
    return dict(user)


def require(*roles):
    def check(user=Depends(actor)):
        if user["role"] not in roles:
            raise HTTPException(403, "Role is not allowed to perform this action")
        return user
    return check


def hospital_rows():
    with db.connect() as conn:
        rows = conn.execute("""SELECT h.*,s.staffed_general_beds,s.occupied_general_beds,
            s.accepting_patients,s.reported_at,s.version AS status_version
            FROM hospitals h LEFT JOIN reported_status s USING(hospital_id) ORDER BY h.hospital_id""").fetchall()
    return [{**dict(row), "services": json.loads(row["services"]),
             "accepting_patients": None if row["accepting_patients"] is None else bool(row["accepting_patients"])} for row in rows]


@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": "simulated live data"}


@app.get("/api/public/hospitals")
def public_hospitals():
    return {"hospitals": hospital_rows(), "environment": "Simulated live data"}


@app.post("/api/public/recommendations")
def recommendations(payload: RecommendationInput):
    # Emergency bypass is deliberately conservative and precedes facility ranking.
    symptoms = {s.strip().lower().replace(" ", "_") for s in payload.symptoms}
    emergency = bool(symptoms & {"severe_breathing_difficulty", "cannot_breathe", "chest_pain", "blue_lips"})
    rows = hospital_rows()
    if emergency:
        return {"emergency_guidance_required": True, "guidance": "These symptoms may need urgent emergency attention. Contact local emergency services or seek immediate care; do not wait for this facility finder.", "service_category": "emergency", "suggested_hospital_id": None, "alternatives": [], "limitations": ["This tool cannot assess or diagnose emergencies."]}
    respiratory = bool(symptoms & {"cough", "shortness_of_breath", "breathlessness", "fever"})
    service = "respiratory" if respiratory else "general"
    now = datetime.now(timezone.utc)
    candidates = []
    for row in rows:
        reported = datetime.fromisoformat(row["reported_at"]) if row["reported_at"] else None
        age_minutes = (now - reported.astimezone(timezone.utc)).total_seconds() / 60 if reported else None
        freshness = "unknown" if age_minutes is None else "current" if age_minutes <= 30 else "stale"
        available = None if row["staffed_general_beds"] is None or row["occupied_general_beds"] is None else max(0, row["staffed_general_beds"] - row["occupied_general_beds"])
        reasons = []
        if service in row["services"]: reasons.append(f"Reports {service} services")
        if payload.zone_id and row["zone_id"] == payload.zone_id: reasons.append("Located in your selected zone")
        if row["accepting_patients"]: reasons.append("Currently reports accepting patients")
        if available is not None: reasons.append(f"Reports {available} staffed general beds available")
        candidates.append({"hospital_id": row["hospital_id"], "name": row["name"], "zone_id": row["zone_id"], "match_reasons": reasons, "availability_state": "accepting" if row["accepting_patients"] else "not_accepting" if row["accepting_patients"] is False else "unknown", "available_staffed_beds": available, "reported_at": row["reported_at"], "freshness_state": freshness})
    candidates.sort(key=lambda h: (h["availability_state"] != "accepting", h["freshness_state"] != "current", -len(h["match_reasons"]), -(h["available_staffed_beds"] or 0)))
    available_candidates = [h for h in candidates if h["availability_state"] == "accepting" and h["freshness_state"] == "current"]
    selected = available_candidates[0] if available_candidates else None
    return {"emergency_guidance_required": False, "service_category": service, "suggested_hospital_id": selected["hospital_id"] if selected else None, "suggested_facility": selected, "alternatives": candidates, "limitations": ["Suggestions match reported services and status; they are not a diagnosis or guarantee of a bed or admission.", "Availability is reported by the facility and should be confirmed directly.", "Location uses zones, not route distance."]}


@app.post("/api/auth/login")
def login(payload: LoginInput):
    result = db.authenticate(payload.username, payload.password)
    if not result: raise HTTPException(401, "Invalid username or password")
    return result


@app.post("/api/auth/logout")
def logout(user=Depends(actor), authorization: str | None = Header(default=None)):
    token = authorization.removeprefix("Bearer ")
    import hashlib
    with db.connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(actor)):
    return user


@app.put("/api/hospitals/{hospital_id}/status")
def update_status(hospital_id: str, payload: StatusInput, user=Depends(require("hospital"))):
    if user["hospital_id"] != hospital_id: raise HTTPException(403, "Hospital operators may update only their own hospital")
    if payload.occupied_general_beds > payload.staffed_general_beds: raise HTTPException(422, "Occupied beds cannot exceed staffed beds")
    stamp = db.now()
    with db.connect() as conn:
        old = conn.execute("SELECT * FROM reported_status WHERE hospital_id=?", (hospital_id,)).fetchone()
        if not old: raise HTTPException(404, "Hospital not found")
        version = old["version"] + 1
        new = {**payload.model_dump(), "reported_at": stamp, "version": version}
        conn.execute("UPDATE reported_status SET staffed_general_beds=?,occupied_general_beds=?,accepting_patients=?,reported_at=?,version=? WHERE hospital_id=?", (payload.staffed_general_beds,payload.occupied_general_beds,int(payload.accepting_patients),stamp,version,hospital_id))
        conn.execute("INSERT INTO audit_events(actor_id,actor_role,target,operation,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)", (user["actor_id"],user["role"],hospital_id,"update_reported_status",json.dumps(dict(old)),json.dumps(new),stamp))
    return {"status": new}


@app.put("/api/hospitals/{hospital_id}/constraints")
def update_constraints(hospital_id: str, payload: ConstraintInput, user=Depends(require("hospital"))):
    if user["hospital_id"] != hospital_id: raise HTTPException(403, "Hospital operators may update only their own hospital")
    stamp = db.now()
    with db.connect() as conn:
        old = conn.execute("SELECT * FROM hospital_constraints WHERE hospital_id=?", (hospital_id,)).fetchone()
        if not old: raise HTTPException(404, "Hospital not found")
        version = old["version"] + 1
        new = {**payload.model_dump(), "version": version}
        conn.execute("UPDATE hospital_constraints SET max_additional_staffed_beds=?,transfer_out_limit_per_day=?,version=? WHERE hospital_id=?", (payload.max_additional_staffed_beds,payload.transfer_out_limit_per_day,version,hospital_id))
        conn.execute("INSERT INTO audit_events(actor_id,actor_role,target,operation,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)", (user["actor_id"],user["role"],hospital_id,"update_planning_constraints",json.dumps(dict(old)),json.dumps(new),stamp))
    return {"constraints": new}


@app.get("/api/planning/state")
def planning_state(user=Depends(require("government", "hospital"))):
    with db.connect() as conn:
        constraints = conn.execute("SELECT * FROM hospital_constraints ORDER BY hospital_id").fetchall()
        settings = conn.execute("SELECT * FROM network_settings WHERE id=1").fetchone()
        result = conn.execute("SELECT * FROM plan_results ORDER BY id DESC LIMIT 1").fetchone()
    if user["role"] == "hospital": constraints = [c for c in constraints if c["hospital_id"] == user["hospital_id"]]
    return {"constraints": [dict(c) for c in constraints], "settings": dict(settings), "latest_result": dict(result) if result else None}


@app.put("/api/planning/settings")
def update_settings(payload: dict, user=Depends(require("government"))):
    allowed = {"scenario_count": (1, 10000), "horizon_days": (1, 365), "budget_units": (0, 1000000)}
    if not payload or any(key not in allowed or not isinstance(value, int) or not allowed[key][0] <= value <= allowed[key][1] for key, value in payload.items()):
        raise HTTPException(422, "Unsupported setting or value out of range")
    with db.connect() as conn:
        old = dict(conn.execute("SELECT * FROM network_settings WHERE id=1").fetchone())
        changes = ",".join(f"{key}=?" for key in payload)
        conn.execute(f"UPDATE network_settings SET {changes},version=version+1 WHERE id=1", (*payload.values(),))
        new = dict(conn.execute("SELECT * FROM network_settings WHERE id=1").fetchone())
        conn.execute("INSERT INTO audit_events(actor_id,actor_role,target,operation,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)", (user["actor_id"],user["role"],"network","update_settings",json.dumps(old),json.dumps(new),db.now()))
    return {"settings": new}


@app.get("/api/audit")
def audit(user=Depends(require("government"))):
    with db.connect() as conn: rows = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 100").fetchall()
    return {"events": [dict(row) for row in rows]}


db.init_db()
