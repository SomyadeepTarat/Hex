"""Conservative structured-case privacy gate. Raw text is never stored.

Pattern redaction is a baseline, not a guarantee of detecting arbitrary names or
addresses. The storage boundary relies on an explicit allowlist, not on regexes.
"""
import re
from datetime import datetime, timezone
from uuid import uuid4

PATTERNS = {
    'email': re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I),
    'phone': re.compile(r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)'),
    'identifier': re.compile(r'\b(?:patient\s*(?:id|identifier)|MRN|Aadhaar|SSN)\s*[:=#-]?\s*[\w-]+', re.I),
    'labelled_name': re.compile(r'\b(?:patient\s+name|name)\s*:\s*[^\n;|,]+', re.I),
    'labelled_address': re.compile(r'\b(?:exact\s+address|address)\s*:\s*[^\n;|]+', re.I),
}
SYMPTOMS = {'fever','cough','shortness_of_breath','fatigue','vomiting','diarrhea','stomach_pain','severe_breathing_difficulty','unconscious','severe_chest_pain','uncontrolled_bleeding'}
ALIASES = {'breathlessness':'shortness_of_breath','nausea':'vomiting'}
SAFE_ID = re.compile(r'^CASE-[0-9a-f]{32}$')


def redact_text(text):
    """Redact common patterns; return category counts without storing raw text."""
    counts = {}
    value = str(text)
    for category, pattern in PATTERNS.items():
        value, count = pattern.subn(f'[REDACTED_{category.upper()}]', value)
        if count:
            counts[category] = count
    return value, counts


def sanitize_case(record, hospital_ids=None, zone_ids=None, *, preserve_case_id=False):
    if not isinstance(record, dict):
        raise ValueError('Case must be a structured record')
    # Redact pattern matches before projecting onto the storage allowlist.
    # Raw note/name/address fields are discarded entirely, even if no match is found.
    structural = {'case_id','reported_at','hospital_id','zone_id','age_band','age'}
    record = {key: redact_text(value)[0] if isinstance(value,str) and key not in structural else value
              for key,value in record.items()}
    hospital = record.get('hospital_id')
    zone = record.get('zone_id')
    if not isinstance(hospital, str) or not re.fullmatch(r'HOSP-\d{2}', hospital) or (hospital_ids is not None and hospital not in hospital_ids):
        raise ValueError('Unknown hospital')
    if not isinstance(zone, str) or not re.fullmatch(r'ZONE-\d{2}', zone) or (zone_ids is not None and zone not in zone_ids):
        raise ValueError('Unknown zone; exact locations are not accepted')
    try:
        timestamp = datetime.fromisoformat(str(record.get('reported_at','')).replace('Z','+00:00'))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        day = timestamp.astimezone(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
    except (TypeError, ValueError):
        raise ValueError('Invalid report timestamp') from None
    band = record.get('age_band')
    if band is None and 'age' in record:
        try:
            age = int(record['age'])
            band = f'{age//10*10}-{min(age//10*10+9,120)}' if 0 <= age <= 120 else None
        except (ValueError, TypeError):
            band = None
    if not isinstance(band, str) or not re.fullmatch(r'\d{1,3}-\d{1,3}', band):
        raise ValueError('Valid age band is required')
    low, high = map(int, band.split('-'))
    if not 0 <= low <= high <= 120 or high-low > 20:
        raise ValueError('Invalid age band')
    # Re-bin even a supplied narrow range so exact ages do not pass through.
    band = f'{low//10*10}-{min(low//10*10+9,120)}'
    symptoms = record.get('symptoms', [])
    if isinstance(symptoms, str):
        symptoms = re.split(r'[|,;]', symptoms)
    if not isinstance(symptoms, list):
        raise ValueError('Symptoms must be normalized tags')
    tags = []
    for symptom in symptoms:
        normalized = str(symptom).strip().lower().replace(' ','_')
        normalized = ALIASES.get(normalized, normalized)
        if normalized in SYMPTOMS and normalized not in tags:
            tags.append(normalized)
    if not tags:
        raise ValueError('At least one supported symptom tag is required')
    severity = record.get('severity')
    if severity not in {'mild','moderate','severe'}:
        raise ValueError('Invalid severity')
    admitted = record.get('admitted')
    if isinstance(admitted,str) and admitted.lower() in {'true','false'}:
        admitted = admitted.lower() == 'true'
    if not isinstance(admitted,bool):
        raise ValueError('Admission flag must be a boolean')
    case_id = record.get('case_id','')
    # Never retain an upstream patient identifier as the analytics case key.
    if not preserve_case_id or not isinstance(case_id,str) or not SAFE_ID.fullmatch(case_id):
        case_id = f'CASE-{uuid4().hex}'
    return {'case_id':case_id,'reported_at':day,'hospital_id':hospital,'zone_id':zone,
            'age_band':band,'symptoms':'|'.join(tags),'severity':severity,'admitted':admitted}


def sanitize_batch(records, hospital_ids=None, zone_ids=None, *, preserve_case_ids=False):
    return [sanitize_case(record,hospital_ids,zone_ids,preserve_case_id=preserve_case_ids) for record in records]
