# Demonstration checklist

## Start

Stop an older HEX process with Ctrl+C, then run from the repository root:

```sh
.venv/bin/python scripts/start.py
```

Open `/find-care/` and `/hospital/` at `http://localhost:8000`. One backend serves both interfaces. Node/Vite and the legacy privacy server are not required. The intro can be skipped; it never gates data processing.

## Prepare synthetic reports

1. In operations choose City network / Administrator and Sign in.
2. Publish fresh synthetic network reports. This explicitly replays saved fictional values; it does not claim receipt of real reports.
3. Choose the respiratory surge case feed, budget 100, scenario count 100, horizon 14 days.
4. Select a hospital, permit up to 12 extra staffed beds and three daily transfers, then Save constraints.
5. Wait for Plan is current. Input versions on the result must match the current saved versions.

## Patient and hospital loop

1. In care navigation enter `I have stomach ache`, continue, select Riverside, then Show my care options.
2. Confirm that Riverside is suggested and its explanation describes general assessment.
3. In operations select Riverside (or sign in as its operator). Uncheck Currently accepting patients and Publish status.
4. Within five seconds the patient result should change to North District, explaining that closer Riverside is not reporting accepting patients.
5. Restore accepting status and publish. The patient result returns to Riverside.
6. Open Report expertise and resources. Update a count and publish. The directory and matching use the new reported data.

## Distance versus expertise

Edit the care request to `I was asked to see a lung specialist for my cough`, continue and select Central. Riverside should rank above Central: 10 fictional km with reported pulmonology versus 5 km without that expertise. This is capability matching, not diagnosis or a quality rating.

## Preparedness and assistant

1. Enter `Set my extra beds to 8` as a hospital operator. As administrator use `Set HOSP-02 maximum additional staffed beds to 8` or select that hospital before an implicit request.
2. Preview must show old/new values without saving. Apply writes the change and audit, then queues recomputation.
3. Public available bed counts must stay unchanged by planning limits.
4. Enter occupied beds greater than staffed beds: an inline error must appear and the database must remain unchanged.
5. Switch to Normal case feed: detection should no longer flag a respiratory surge; baseline can be the best feasible plan. Switch back to Respiratory surge afterward.
6. Expand Model evidence and Activity & audit history to show trained forecasting metrics and saved changes.

## Failure and emergency states

- Unrecognized or unrelated concerns get a focused clarification without an invented specialist match.
- If reports become stale, the result explains that current availability cannot be confirmed. Publish fresh synthetic reports for the demo instead of silently ignoring timestamps.
- `I cannot breathe` must show emergency guidance before area selection; no provider call should be made.
- Missing requested resources or specialists must remain missing; they cannot be invented to force a suggestion.

## Groq

The key stays in ignored `.env`. Enable Use Groq for an intentional final care request. Automatic refresh and the first-step emergency preview never call Groq. A live synthetic stomach-ache test after this merge returned both Groq interpretation and a Groq-assisted verified explanation. The previous gateway 403 was resolved by identifying the application with an explicit User-Agent header. Transport, schema, grounding and failure cases are also tested offline.

## Verification

```sh
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests -v
```

Tests include HTTP/static asset contracts, guided-preview behavior, authorization, capacity validation, proposal ownership/versioning, reproducibility, constraints and provider failure isolation. Browser checks additionally cover the upgraded conversation, automatic rerouting, hospital capability reports, constraints, assistant preview/apply, network settings and feed switching.
