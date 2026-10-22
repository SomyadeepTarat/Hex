# Central data flow

The supported demo now runs from `scripts/start.py`; see the root README for the complete walkthrough.

- `data/raw/demo_hospitals.csv`, `demo_zones.csv`: fictional facility metadata, initial operational capacity assumptions and adjacency.
- `data/synthetic/generated/cases_normal.csv`, `cases_surge.csv`: distinct synthetic hospital case feeds. Current selected feed is persisted in SQLite; public symptom searches never enter it.
- `data/synthetic/ml_hospital_days.csv`: 26,028 aggregate synthetic hospital-days with lagged features, next-day admissions targets and persistence predictions. Recreated by `python -m src.hex.ml`.
- `models/admission_model.json`: fitted coefficients, training means/scales, validation residual scale and evaluation.
- `models/evaluation.json`: reproducible chronological and unseen-city test results.
- `data/hex.db`: centrally persisted hospital metadata, reported status, hospital constraints, network settings, cases, proposals, audit and versioned results.

The current app serves `/find-care/` and `/hospital/` from the same FastAPI origin. There is no separate government interface, Vite dependency, or port-8001 service in this flow. The network administrator is another account in the shared hospital workspace.

All data is synthetic. Old privacy-server files are retained as a separate prototype and are not used by the unified application.
