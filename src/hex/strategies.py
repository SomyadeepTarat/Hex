"""Compare fixed, feasible actions on identical futures."""
from math import isfinite
from .facility_recommendation import records
from .simulation import simulate

def compare_strategies(futures, statuses, constraints, budget_units):
    if isinstance(budget_units, bool) or not isinstance(budget_units, (int, float)) or not isfinite(budget_units) or budget_units < 0:
        raise ValueError('Budget must be finite and nonnegative')
    if not futures:
        raise ValueError('At least one future is required')
    statuses = records(statuses)
    constraints = {c['hospital_id']: c for c in records(constraints)}
    ids = {s['hospital_id'] for s in statuses}
    if set(constraints) - ids:
        raise ValueError('Constraints reference unknown hospitals')
    for c in constraints.values():
        for field in ('max_additional_staffed_beds', 'transfer_out_limit_per_day'):
            value = c.get(field, 0)
            if type(value) is not int or not 0 <= value <= 500:
                raise ValueError(f'{field} must be an integer in 0..500')
    # One additional staffed bed costs ten illustrative units for this horizon.
    allocation = {hid: 0 for hid in sorted(ids)}
    remaining = int(budget_units // 10)
    # Greedy marginal worst-case improvement; one fixed allocation for all futures.
    def objective(extra):
        values = [simulate(f, statuses, extra)['unmet_bed_days'] for f in futures]
        return max(values), sum(values) / len(values)
    current = objective(allocation)
    while remaining:
        choices = []
        for hid in sorted(ids):
            if allocation[hid] < constraints.get(hid, {}).get('max_additional_staffed_beds', 0):
                candidate = dict(allocation)
                candidate[hid] += 1
                choices.append((objective(candidate), hid, candidate))
        if not choices:
            break
        score, _, candidate = min(choices, key=lambda c: (c[0], c[1]))
        if score >= current:
            break
        allocation, current, remaining = candidate, score, remaining - 1
    transfer_limits = {hid: constraints.get(hid, {}).get('transfer_out_limit_per_day', 0) for hid in ids}
    # Transfers cost one unit each; reserve the entire permitted daily transfer envelope.
    horizon = max(len(f['arrivals']) for f in futures)
    affordable = int(budget_units // max(1, horizon))
    transfer_allocation = {hid: 0 for hid in sorted(ids)}
    while affordable and any(transfer_allocation[h] < transfer_limits[h] for h in ids):
        for hid in sorted(ids):
            if affordable and transfer_allocation[hid] < transfer_limits[hid]:
                transfer_allocation[hid] += 1
                affordable -= 1
    candidates = [('baseline', {}, {}, 0), ('flex_capacity', allocation, {}, sum(allocation.values()) * 10),
                  ('redistribution', {}, transfer_allocation, sum(transfer_allocation.values()) * horizon)]
    output = []
    for name, extra, transfers, cost in candidates:
        runs = [simulate(f, statuses, extra, transfers) for f in futures]
        values = [r['unmet_bed_days'] for r in runs]
        output.append(dict(strategy_id=name, feasible=True, additional_staffed_beds=extra,
                           transfer_out_limit_per_day=transfers, intervention_cost=cost,
                           worst_case_unmet_bed_days=max(values), mean_unmet_bed_days=sum(values) / len(values),
                           fraction_scenarios_without_unmet_demand=sum(v < 1e-9 for v in values) / len(values),
                           forecast=[dict(day=d + 1, mean_occupancy=sum(sum(r['daily'][d]['occupancy'].values()) for r in runs) / len(runs),
                                          worst_unmet_demand=max(sum(r['daily'][d]['unmet_demand'].values()) for r in runs)) for d in range(horizon)]))
    output.sort(key=lambda s: (s['worst_case_unmet_bed_days'], s['mean_unmet_bed_days'], s['intervention_cost'], s['strategy_id']))
    return output
