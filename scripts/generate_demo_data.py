"""Generate separate reproducible case feeds; preserve the starter fixtures."""
import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def generate(seed=42):
    rng = random.Random(seed)
    with (ROOT / 'data/raw/demo_hospitals.csv').open() as handle:
        hospitals = list(csv.DictReader(handle))
    with (ROOT / 'data/raw/demo_zones.csv').open() as handle:
        zones = list(csv.DictReader(handle))
    for zone in zones:
        zone['neighboring_zones'] = zone['neighboring_zones'].split('|')
        zone['population_estimate'] = int(zone['population_estimate'])
    neighbors = {z['zone_id']: z['neighboring_zones'] for z in zones}
    statuses, constraints = [], []
    for hospital in hospitals:
        for field in ('general_beds', 'occupied_general_beds', 'icu_beds', 'occupied_icu_beds', 'staffed_shift_capacity'):
            hospital[field] = int(hospital[field])
        hospital.update(services=['general', 'respiratory'], emergency_service_available=True, neighboring_zones=neighbors[hospital['zone_id']])
        statuses.append(dict(hospital_id=hospital['hospital_id'], staffed_general_beds=hospital['general_beds'], occupied_general_beds=hospital['occupied_general_beds'], accepting_patients=True, reported_at='2026-10-22T06:00:00Z', version=1))
        constraints.append(dict(hospital_id=hospital['hospital_id'], max_additional_staffed_beds=12, transfer_out_limit_per_day=5))
    feeds = {}
    for mode in ('normal', 'surge'):
        rows = []
        for day in range(28):
            for hospital in hospitals:
                count = rng.randint(6, 10) + (max(0, day - 20) * 4 if mode == 'surge' else 0)
                for _ in range(count):
                    respiratory = rng.random() < (0.9 if mode == 'surge' and day >= 21 else 0.5)
                    rows.append(dict(case_id=f'SYN-{mode.upper()}-{len(rows)+1:05}', reported_at=(datetime(2026, 9, 25, 8, tzinfo=timezone.utc) + timedelta(days=day, minutes=rng.randrange(600))).isoformat(), hospital_id=hospital['hospital_id'], zone_id=hospital['zone_id'], age_band=rng.choice(['20-29', '30-39', '50-59', '60-69']), symptoms='fever|cough' if respiratory else 'fatigue|vomiting', severity=rng.choice(['mild', 'moderate', 'severe']), admitted=rng.random() < 0.35))
        feeds[mode] = rows
    return dict(hospitals=hospitals, zones=zones, statuses=statuses, constraints=constraints, settings=dict(scenario_count=100, horizon_days=14, seed=seed, budget_units=100, status_version=1, constraints_version=1)), feeds

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/synthetic/generated')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    context, feeds = generate(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'context.json').write_text(json.dumps(context, indent=2) + '\n')
    for mode, rows in feeds.items():
        with (args.output / f'cases_{mode}.csv').open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(f'Generated normal and surge feeds in {args.output}')

if __name__ == '__main__':
    main()
