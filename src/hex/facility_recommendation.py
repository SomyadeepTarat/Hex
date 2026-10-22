"""Explainable synthetic-demo facility matching; no diagnostic inference."""
from datetime import datetime, timezone

EMERGENCY = {'severe_breathing_difficulty', 'unconscious', 'severe_chest_pain', 'uncontrolled_bleeding'}
SERVICES = {'cough': 'respiratory', 'shortness_of_breath': 'respiratory', 'fever': 'general', 'fatigue': 'general', 'vomiting': 'general', 'diarrhea': 'general', 'stomach_pain': 'general'}

def records(value):
    return list(value.values()) if isinstance(value, dict) else list(value)

def timestamp(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp strings must include a timezone')
    return parsed.astimezone(timezone.utc)

def recommend_facilities(symptoms, zone_id, hospitals, statuses, now):
    tags = {str(s).strip().lower().replace(' ', '_') for s in symptoms}
    result = dict(emergency_guidance_required=bool(tags & EMERGENCY), service_category=None,
                  suggested_hospital_id=None, alternatives=[], limitations=[
                      'Synthetic decision-support demo; this is not a diagnosis.',
                      'Reported availability does not guarantee a bed or admission; contact the hospital to confirm.'])
    if result['emergency_guidance_required']:
        result['guidance'] = 'Seek immediate emergency assistance through your local emergency service. Do not wait for facility suggestions.'
        return result
    if not tags or tags - SERVICES.keys():
        result['limitations'].append('Select supported symptom tags; unsupported symptoms require professional advice.')
        return result
    category = 'respiratory' if any(SERVICES[t] == 'respiratory' for t in tags) else 'general'
    result['service_category'] = category
    status_map = {s['hospital_id']: s for s in records(statuses)}
    candidates = []
    for hospital in records(hospitals):
        services = hospital.get('services', [])
        if isinstance(services, str):
            services = services.split('|')
        if category not in services:
            continue
        status = status_map.get(hospital['hospital_id'], {})
        try:
            age = (timestamp(now) - timestamp(status['reported_at'])).total_seconds()
            fresh = 'current' if 0 <= age <= 900 else 'stale'
        except (KeyError, ValueError, TypeError):
            fresh = 'unknown'
        capacity, occupied = status.get('staffed_general_beds'), status.get('occupied_general_beds')
        valid = (type(capacity) is int and type(occupied) is int and 0 <= occupied <= capacity)
        available = capacity - occupied if valid else None
        accepting = status.get('accepting_patients')
        state = 'not_accepting' if accepting is False else ('unknown' if accepting is not True or not valid else ('available' if available else 'full'))
        proximity = 'same_zone' if hospital['zone_id'] == zone_id else ('adjacent_zone' if zone_id in hospital.get('neighboring_zones', []) else 'other_zone')
        item = dict(hospital_id=hospital['hospital_id'], match_reasons=[f'Reports {category} services', proximity.replace('_', ' ')], availability_state=state, available_staffed_beds=available, reported_at=status.get('reported_at'), freshness_state=fresh)
        eligible = fresh == 'current' and accepting is True and valid
        key = (not eligible, {'same_zone': 0, 'adjacent_zone': 1, 'other_zone': 2}[proximity], available == 0, -(available or 0), hospital['hospital_id'])
        candidates.append((key, item, eligible))
    candidates.sort(key=lambda x: x[0])
    result['alternatives'] = [c[1] for c in candidates]
    if candidates and candidates[0][2]:
        result['suggested_hospital_id'] = candidates[0][1]['hospital_id']
    else:
        result['limitations'].append('No suitable facility has current, complete, accepting status information.')
    return result
