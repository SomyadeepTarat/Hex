"""Database-free integration entry point for Person 2's API."""
from datetime import datetime, timezone
from uuid import uuid4
from .detection import detect_surge
from .facility_recommendation import records
from .simulation import generate_futures
from .strategies import compare_strategies

def run_analysis(cases, hospitals, zones, statuses, constraints, settings):
    hospitals, zones, statuses, constraints = map(records, (hospitals, zones, statuses, constraints))
    ids = {h['hospital_id'] for h in hospitals}
    if not ids or {s['hospital_id'] for s in statuses} != ids or len(statuses) != len(ids):
        raise ValueError('Exactly one reported status per hospital is required')
    zone_ids = {z['zone_id'] for z in zones}
    if any(h['zone_id'] not in zone_ids for h in hospitals) or any(c['hospital_id'] not in ids or c['zone_id'] not in zone_ids for c in cases):
        raise ValueError('Unknown hospital or zone reference')
    detection = detect_surge(cases)
    from .ml import forecast_cases
    ml, rates = forecast_cases(cases, hospitals)
    futures = generate_futures(cases, hospitals, {**settings, 'admission_rates': rates})
    strategies = compare_strategies(futures, statuses, constraints, settings.get('budget_units', 100))
    return dict(run_id=str(uuid4()), status_version=settings.get('status_version'), constraints_version=settings.get('constraints_version'),
                generated_at=datetime.now(timezone.utc).isoformat(), detection=detection, ml=ml, strategies=strategies,
                recommendation=dict(strategy_id=strategies[0]['strategy_id'], explanation='Best among evaluated feasible plans, ranked by worst-case unmet bed-days, mean unmet bed-days, then cost.'),
                scenarios=dict(count=len(futures), horizon_days=len(futures[0]['arrivals']), seed=settings.get('seed', 42)),
                assumptions=['Synthetic scenarios, not calibrated clinical forecasts.', 'When the trained artifact is available, ridge next-day admission forecasts initialize demand futures; later growth remains an illustrative assumption.', 'General beds only; reported staffed capacity is operational capacity.',
                             'Growth sampled uniformly from -0.02 to 0.12 per day; length of stay from 4 to 8 days.',
                             'Unserved demand waits and contributes unmet bed-days each day; no mortality model.',
                             'Flex beds cost 10 illustrative units per horizon; transfers reserve 1 unit per allowed patient per day.',
                             'Flex allocation uses greedy marginal improvement and stays fixed across futures; no global optimum claim.',
                             'Transfers use a network-wide demo pool; geography and travel times are not modeled.',
                             'Public symptom searches are not hospital case signals.'])
