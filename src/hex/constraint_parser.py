"""Allowlisted proposal parser. Persistence and authorization belong to the API."""
import re
from .facility_recommendation import records

FIELDS = {
    'transfer limit': ('transfer_out_limit_per_day', 0, 500, 'hospital'),
    'maximum additional staffed beds': ('max_additional_staffed_beds', 0, 500, 'hospital'),
    'network budget': ('budget_units', 0, 100000, 'network'),
    'scenario count': ('scenario_count', 1, 500, 'network'),
}

def parse_constraint_message(message, actor_context, current_constraints):
    def response(action, explanation, **kwargs):
        return dict(action=action, target=None, field=None, old_value=None, new_value=None, explanation=explanation, **kwargs)
    if not isinstance(message, str) or len(message) > 1000:
        return response('unsupported', 'Use a single supported constraint command of at most 1000 characters.')
    text = message.strip().rstrip('.').strip()
    if text.lower() == 'show current constraints':
        return response('show_constraints', 'Request the current constraints from the authorized API.')
    match = re.fullmatch(r'set\s+(.+?)\s+to\s+(.+?)(?:\s+units|\s+per day)?', text, re.I)
    if not match:
        return response('unsupported', 'Use: Set HOSP-02 transfer limit to 5 per day; Set network budget to 100 units; or Show current constraints.')
    subject, raw = match.groups()
    selected = next(((phrase, spec) for phrase, spec in FIELDS.items() if subject.lower().endswith(phrase)), None)
    if not selected:
        return response('unsupported', 'That field is outside the supported planning constraint set.')
    phrase, (field, lower, upper, scope) = selected
    prefix = subject[:-len(phrase)].strip()
    if not re.fullmatch(r'\d+', raw):
        return response('clarify', f'Enter a whole number between {lower} and {upper}.')
    value = int(raw)
    if not lower <= value <= upper:
        return response('clarify', f'Value must be between {lower} and {upper}.')
    # Canonical input: {hospitals: [metadata + constraints], settings: {...}}.
    hospitals = records(current_constraints.get('hospitals', []))
    if scope == 'network':
        if prefix:
            return response('clarify', 'Network settings must not specify a hospital.')
        target, old = 'network', current_constraints.get('settings', {}).get(field)
    else:
        matches = [h for h in hospitals if prefix.casefold() in {str(h.get('hospital_id', '')).casefold(), str(h.get('name', '')).casefold()}]
        if len(matches) != 1 or not prefix:
            return response('clarify', 'Specify one known, unambiguous hospital ID or full name.')
        target, old = matches[0]['hospital_id'], matches[0].get(field)
    role = actor_context.get('role')
    if role not in {'government', 'government_coordinator', 'hospital', 'hospital_operator'}:
        return response('unsupported', 'An authenticated operational role is required.')
    if role in {'hospital', 'hospital_operator'} and (target == 'network' or target != actor_context.get('hospital_id')):
        return response('unsupported', 'Hospital operators may propose changes only for their own hospital.')
    return dict(action='propose_change', target=target, field=field, old_value=old, new_value=value,
                explanation='Proposed change only. The API must authorize, preview, revalidate versions, and apply it after confirmation.')
