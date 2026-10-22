# Person 1 engine and integration contract

The decision engine uses Python's standard library and has no database, HTTP, authentication, or UI dependencies. All data is synthetic. This implements the Person 1 scope from the two-flow plan; Person 2 owns persistence, authorization, APIs, client polling, and the two interfaces.

## Run and verify

From the project root:

```sh
python3 scripts/generate_demo_data.py
python3 scripts/run_demo.py --mode surge --output data/processed/surge_result.json
python3 scripts/run_demo.py --mode normal --output data/processed/normal_result.json
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
```

Generated case feeds contain 28 days. Normal and surge datasets share a seed but contain independent sampled records. The surge ramps up during the final week. Starter CSVs remain unchanged. Generated timestamps are fixed demo timestamps, not live reports. Replay must publish an actual new report timestamp rather than silently treating old snapshots as current.

## API integration

Set `PYTHONPATH=src` or add the project's `src` directory to the server's import path.

```python
from hex.pipeline import run_analysis
from hex.facility_recommendation import recommend_facilities
from hex.constraint_parser import parse_constraint_message

result = run_analysis(cases, hospitals, zones, statuses, constraints, settings)
public_result = recommend_facilities(symptoms, zone_id, hospitals, statuses, now)
proposal = parse_constraint_message(message, actor_context, current_constraints)
```

Inputs are lists of dictionaries; hospitals, statuses, constraints and zones also accept ID-keyed dictionary containers whose values include their IDs. CSV numeric and boolean values in capacity/constraint inputs must be converted to Python types by ingestion. `cases.symptoms` accepts a pipe-delimited string or list. `cases.admitted` accepts a boolean or CSV `true`/`false`. Feed validation and privacy filtering belong to ingestion.

Hospital metadata includes `hospital_id`, `name`, `zone_id`, and `services` (list or pipe-delimited string). Optional `neighboring_zones` supplies zone adjacency; the generated context includes it. Service tags are `general` and `respiratory`. Supported ordinary symptoms are `cough`, `shortness_of_breath`, `fever`, `fatigue`, `vomiting`, and `diarrhea`. Explicit emergency tags are `severe_breathing_difficulty`, `unconscious`, `severe_chest_pain`, and `uncontrolled_bleeding`; this is a small demo allowlist, not a clinical triage system. Public UI must offer emergency guidance independently of this finite tag list.

Status fields: `hospital_id`, `staffed_general_beds`, `occupied_general_beds`, `accepting_patients`, `reported_at`, `version`. Planning requires exactly one valid capacity snapshot per hospital. Public suggestions preserve missing capacity as unknown, label reports older than 15 minutes stale, and exclude stale, missing, future-dated, and non-accepting reports from the primary suggestion. Candidates are ordered by current eligibility, same/adjacent/other zone, nonzero reported availability, available count, then stable hospital ID. Bed counts are information, not admission criteria. Planned capacity is never read by public matching. `alternatives` includes the suggested facility as the first candidate, allowing clients to render the whole ranked list.

Constraints: `hospital_id`, `max_additional_staffed_beds`, `transfer_out_limit_per_day` (whole numbers 0–500). Missing constraints imply no additional beds or transfers. Settings: `scenario_count` (1–500), `horizon_days` (1–60), `seed`, `budget_units`, `status_version`, `constraints_version`. Default settings are 100 futures, 14 days, seed 42, and budget 100 units.

Parser context:

```python
actor_context = {"role": "government", "actor_id": "demo-coordinator"}
current_constraints = {
    "hospitals": [
        {"hospital_id": "HOSP-02", "name": "Riverside Medical Centre",
         "max_additional_staffed_beds": 12, "transfer_out_limit_per_day": 5}
    ],
    "settings": {"budget_units": 100, "scenario_count": 100}
}
```

Hospital operators use `role="hospital"` and a server-derived `hospital_id`. Long-form `hospital_operator` and `government_coordinator` roles are also supported. Resolve hospital IDs or exact full names; ambiguous names return clarification. Parser authorization is defensive only: the API must independently authorize both preview and apply, keep proposals server-side, reject stale versions, require Apply, and transact the change with its audit event. Parser never writes data and never returns SQL. Network budgets are limited to 100,000 demo units.

`run_analysis` returns JSON-compatible detection, scenario metadata, ranked strategies, recommendation, assumptions, run ID, timestamps and input versions. The computation is deterministic for a seed; run ID and generation timestamp intentionally differ. The API must pass snapshot versions through settings and discard superseded results. Public matching does not append symptoms to the case feed.

## Modeling choices and limits

Detection compares three recent days' respiratory count mean against a 14-day mean plus three Poisson standard deviations. Missing dates are zero under the **complete daily reporting assumption**. Fewer than 17 observed calendar days cannot produce an alert. This is an interpretable synthetic baseline, not a trained anomaly model or validated outbreak detector.

Scenario arrivals start from the last three reporting dates' admitted case counts by hospital. Daily growth is uniformly sampled between -0.02 and 0.12 and length of stay between four and eight days. Rounded nonnegative Gaussian arrival noise provides illustrative variation. These ranges are assumptions, not fitted posteriors; forecast calibration and clinical performance have not been established.

Simulation releases a fraction `1 / length_of_stay` of occupied beds each day, adds arrivals and previous waiting demand, transfers within permitted sending limits and spare receiving capacity, and carries remaining unmet demand forward. Unmet bed-days sum waiting demand over time. Occupancy can be fractional because departures are expected values. No ICU, mortality, transport, staff skill mix, emergency acuity, or patient outcomes are modeled. Transfers use the whole hospital network rather than geographic routes. Zone populations are metadata, not fitted transmission parameters.

Three strategies share the exact same futures: baseline, flex capacity, and redistribution. Flex allocation greedily adds the bed with the best marginal worst-case/mean improvement until limits, budget, or improvement are exhausted. It remains fixed across all futures. Ten illustrative units fund one additional staffed bed for the horizon. Redistribution reserves one unit per permitted transfer per day, even if unused, so realized costs cannot exceed budget. A deterministic round-robin allocation reduces network sending limits when budget is insufficient. Transfer receiving capacity is enforced after expected discharges and arrivals. Plans are ranked by worst-case unmet bed-days, mean unmet bed-days, then reserved intervention cost. **Best means best among these evaluated feasible plans**; neither the greedy bed allocator nor transfer allocator is a global optimizer.

Hospital `general_beds` in starter data initialize staffed capacity only as an explicit demo assumption. Recommended flex beds are proposed actions and become public availability only after an authorized operational status update.
