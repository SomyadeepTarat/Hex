# Case-record privacy gate

The active application filters case records before storing them in SQLite. The gate runs for startup seeding, existing stored case payloads at startup, feed replacement, and `POST /api/cases/ingest`. Ingestion requires an operator account and hospital ownership is checked on the server.

The gate detects common email, phone, identifier, explicitly labelled name, and explicitly labelled address patterns. Pattern redaction is deliberately limited: it cannot reliably identify every arbitrary name or address in prose. Therefore raw notes and all unapproved fields are discarded entirely, even when no pattern matches. Only validated hospital and zone IDs, a generalized age band, a report day, supported symptom tags, severity, an admission flag, and an internal random case key can reach case storage.

Incoming case IDs are replaced. Previously generated internal IDs remain stable during startup filtering. Source names, contact details, exact addresses, and patient IDs are not copied into analytics records or ingestion audit events. Raw timestamps are coarsened to UTC reporting days. Public searches remain separate from the case feed.

Invalid batches are rejected before insertion; ingestion and the audit count are committed in one transaction. Successful ingestion requests trigger preparedness recomputation. This does not alter reported hospital bed availability.

This is a rule-based baseline for the current structured input contract, not certified anonymization. Real deployment still requires domain validation, safeguards for inference from rare combinations, and evaluation of detection accuracy. The gate does not erase existing source files, historical backups, or data held by external systems.

Verification: `python -m unittest discover -s tests -p test_privacy_gate.py -v` and `python -m unittest discover -s tests -p test_api.py -v`.
