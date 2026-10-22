"""Seeded scenario generation and general-bed queue simulation, standard library only."""
import random
from math import exp
from .facility_recommendation import records

def generate_futures(cases, hospitals, settings):
    count, horizon = settings.get('scenario_count', 100), settings.get('horizon_days', 14)
    if type(count) is not int or not 1 <= count <= 500 or type(horizon) is not int or not 1 <= horizon <= 60:
        raise ValueError('scenario_count must be 1..500 and horizon_days 1..60')
    rng = random.Random(settings.get('seed', 42))
    hospitals = records(hospitals)
    days = sorted({str(c['reported_at'])[:10] for c in cases})[-3:]
    rates = {h['hospital_id']: sum(c['hospital_id'] == h['hospital_id'] and str(c['reported_at'])[:10] in days and (c['admitted'] is True or str(c['admitted']).lower() == 'true') for c in cases) / max(len(days), 1) for h in hospitals}
    futures = []
    for index in range(count):
        growth, los = rng.uniform(-0.02, 0.12), rng.uniform(4, 8)
        arrivals = [{hid: int(max(0, rng.gauss(rate * exp(growth * day), (rate * exp(growth * day) + 1) ** .5))) for hid, rate in rates.items()} for day in range(horizon)]
        futures.append(dict(scenario_id=index, growth_rate=growth, length_of_stay_days=los, arrivals=arrivals))
    return futures

def simulate(future, statuses, extra_beds=None, transfer_limits=None):
    statuses = records(statuses)
    extra_beds, transfer_limits = extra_beds or {}, transfer_limits or {}
    capacity, occupancy = {}, {}
    for status in statuses:
        hid = status['hospital_id']
        staffed, occupied = status['staffed_general_beds'], status['occupied_general_beds']
        if type(staffed) is not int or type(occupied) is not int or not 0 <= occupied <= staffed:
            raise ValueError('Simulation requires valid reported staffed capacity and occupancy')
        capacity[hid] = staffed + extra_beds.get(hid, 0)
        occupancy[hid] = float(occupied)
    backlog = {hid: 0.0 for hid in capacity}
    unmet, transfers, daily = 0.0, 0.0, []
    for arrivals in future['arrivals']:
        demand = {hid: occupancy[hid] * (1 - 1 / future['length_of_stay_days']) + backlog[hid] + arrivals.get(hid, 0) for hid in capacity}
        for sender in sorted(capacity):
            remaining = min(max(0, demand[sender] - capacity[sender]), transfer_limits.get(sender, 0))
            for receiver in sorted(capacity):
                if receiver == sender:
                    continue
                moved = min(remaining, max(0, capacity[receiver] - demand[receiver]))
                demand[sender] -= moved
                demand[receiver] += moved
                remaining -= moved
                transfers += moved
        backlog = {hid: max(0, demand[hid] - capacity[hid]) for hid in capacity}
        occupancy = {hid: min(demand[hid], capacity[hid]) for hid in capacity}
        unmet += sum(backlog.values())
        daily.append(dict(occupancy=dict(occupancy), unmet_demand=dict(backlog)))
    return dict(unmet_bed_days=unmet, transferred_patients=transfers, daily=daily)
