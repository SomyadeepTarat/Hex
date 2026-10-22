"""In-memory demo privacy gate and synthetic case generator.

This is for the fabricated demo input only. It is not a production de-identification
or synthetic-data system and must not be used to process real patient records.
"""

from __future__ import annotations

import csv
import random
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW_CASES = ROOT / "data" / "raw" / "synthetic_cases_with_pii.csv"
RAW_HOSPITALS = ROOT / "data" / "raw" / "demo_hospitals.csv"
RAW_ZONES = ROOT / "data" / "raw" / "demo_zones.csv"
AGE_BANDS = ((0, 9), (10, 19), (20, 29), (30, 39), (40, 49), (50, 59), (60, 69), (70, 79), (80, 120))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _age_band(value: str) -> str:
    age = int(value)
    for low, high in AGE_BANDS:
        if low <= age <= high:
            return f"{low}-{high}"
    raise ValueError("age outside supported range")


def privacy_filter(rows: list[dict[str, str]], hospital_map: dict[str, dict[str, object]]) -> list[dict[str, str]]:
    """Drop patient identifiers and map source facility/zone IDs to simulated IDs."""
    safe = []
    for row in rows:
        safe.append({
            "reported_at": row["reported_at"],
            "hospital_id": hospital_map[row["hospital_id"]]["hospital_id"],
            "zone_id": hospital_map[row["hospital_id"]]["zone_id"],
            "age_band": _age_band(row["age"]),
            "symptoms": row["symptoms"].split("|"),
            "severity": row["severity"],
            "admitted": row["admitted"].strip().lower() == "true",
        })
    return safe


def generate_synthetic_cases(safe_rows: list[dict[str, str]], count: int = 120) -> list[dict[str, object]]:
    """Bootstrap generalized attributes into clearly simulated cases in memory."""
    rng = random.Random(20261022)
    generated = []
    for index in range(count):
        source = safe_rows[rng.randrange(len(safe_rows))]
        generated.append({
            "case_id": f"SIM-{index + 1:04d}",
            "reported_at": source["reported_at"],
            "hospital_id": source["hospital_id"],
            "zone_id": source["zone_id"],
            "age_band": source["age_band"],
            "symptoms": list(source["symptoms"]),
            "severity": source["severity"],
            "admitted": source["admitted"],
            "simulated": True,
        })
    return generated


def transform_facilities() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, dict[str, object]]]:
    """Generalize fictional facility and zone source tables into in-memory demo objects."""
    raw_zones = _read_csv(RAW_ZONES)
    zone_map = {row["zone_id"]: f"SIM-ZONE-{index + 1:02d}" for index, row in enumerate(raw_zones)}
    zones = [{
        "zone_id": zone_map[row["zone_id"]],
        "display_name": f"Demo Zone {index + 1}",
        "population_estimate": int(row["population_estimate"]),
        "simulated": True,
    } for index, row in enumerate(raw_zones)]

    hospitals = []
    hospital_map = {}
    for index, row in enumerate(_read_csv(RAW_HOSPITALS)):
        sim_id = f"SIM-HOSP-{index + 1:02d}"
        zone_id = zone_map[row["zone_id"]]
        hospital_map[row["hospital_id"]] = {"hospital_id": sim_id, "zone_id": zone_id}
        hospitals.append({
            "hospital_id": sim_id,
            "name": f"Demo Hospital {index + 1}",
            "zone_id": zone_id,
            "general_beds": int(row["general_beds"]),
            "occupied_general_beds": int(row["occupied_general_beds"]),
            "icu_beds": int(row["icu_beds"]),
            "occupied_icu_beds": int(row["occupied_icu_beds"]),
            "staffed_shift_capacity": int(row["staffed_shift_capacity"]),
            "simulated": True,
        })
    return hospitals, zones, hospital_map


def build_dashboard_payload() -> dict[str, object]:
    """Read demo input, filter it, and generate an in-memory response."""
    raw_rows = _read_csv(RAW_CASES)
    hospitals, zones, hospital_map = transform_facilities()
    safe_rows = privacy_filter(raw_rows, hospital_map)
    simulated = generate_synthetic_cases(safe_rows)
    symptom_counts: dict[str, int] = {}
    for case in simulated:
        for symptom in case["symptoms"]:
            symptom_counts[symptom] = symptom_counts.get(symptom, 0) + 1
    return {
        "source_records": len(raw_rows),
        "privacy_filtered_records": len(safe_rows),
        "simulated_records": len(simulated),
        "hospitals": hospitals,
        "zones": zones,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "top_symptoms": sorted(symptom_counts.items(), key=lambda item: item[1], reverse=True)[:5],
        "simulated_cases": simulated,
        "notice": "Fabricated demo input; identifiers are discarded before simulation. Not a production privacy system.",
    }
