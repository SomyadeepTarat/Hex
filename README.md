# HEX — central hospital network

Two journeys, one backend and SQLite database:

- **Patient:** select symptoms and area → see a suitable hospital, reasons, alternatives and current reported availability.
- **Hospital:** report current capacity → public suggestions refresh → inspect the ML-backed preparedness plan → adjust planning limits using a form or assistant → preview and apply → the plan recomputes.

The network administrator uses the same hospital workspace, with permission to change network budgets and switch synthetic case feeds. There is no separate government dashboard in the current demo.

## Start everything

Python 3.10+ is required. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/start.py
```

Open **http://localhost:8000/** for the patient flow and **http://localhost:8000/hospital/** for hospital operations. Stop with Ctrl+C. If another service already uses port 8000, stop it or run `.venv/bin/python scripts/start.py --port 8010`.

No Node.js, Vite, or separate demo-data API is needed for this flow. Older frontend and privacy-server files remain as historical prototypes; they are not used by the unified launcher.

The hospital workspace offers seeded demo accounts for each of three fictional hospitals. Operator credentials are `operator-hosp01` (or `02`, `03`) / `demo-hospital`. The network administrator uses `coordinator` / `demo-government`, in the same interface. Each operator can change only their own hospital. The app is a localhost synthetic demonstration, not a production deployment.

## A three-minute demonstration

1. Open patient finder and hospital workspace side by side.
2. In the finder, select **Cough**, choose **ZONE-03**, and request suggestions. With fresh reports, Central is preferred because it reports the service and is in the selected zone. Old reports correctly show as stale; to refresh a hospital, sign in and publish its current status.
3. Sign in as **Central Community Hospital**. Review its prefilled status. Uncheck **Accepting patients**, then **Publish status & update suggestions**. Within five seconds the patient suggestion changes to another current suitable hospital, or reports no current option if every alternative is stale. Recheck and publish to restore it.
4. In the planning assistant, enter **Set HOSP-01 maximum additional staffed beds to 12.** Review the old/new values, then click **Apply change & recompute**. Watch the strategy table update. Planning does not create publicly available beds.
5. Scroll to **Next-day admissions forecast**. Show the dataset size, trained model's held-out error, baseline error, and current admission predictions.
6. Optional: sign out and choose **Network administrator** in the same workspace. Load the normal versus surge feed or change budget; compare detection and the recomputed plan. Hospital reports remain separate from case-feed switching.

If all strategy results are equal, check the hospital's allowed extra beds/transfer limits. They initialize to zero, so no intervention is feasible until the operator enables it. A plan can still predict unmet demand even after adding beds; constraints and budget limit the available actions.

## What the ML actually does

A trained **ridge autoregression** predicts next-day admissions from previous admissions (yesterday, seven days ago, seven-day mean and recent trend), previous-day respiratory case share, and the target weekday. Predictions initialize the demand level used by the scenario engine. The public hospital ranking is a transparent service/status/proximity rule system, not a diagnosis model.

The benchmark contains **26,028 hospital-day rows**, representing 12 synthetic cities, 36 hospitals, and 730 days per hospital (seven warm-up days excluded). It is aggregate synthetic demand data; it contains no patient identities. The operational demonstration uses a separate synthetic case feed held in the central database.

Training uses cities 0–9 and days 7–509; validation days 510–619 select ridge regularization; days 620–729 are the chronological test. Cities 10–11 are held out from both fitting and model selection. Scaling is learned only on training data. Features use prior observed admissions and respiratory share; no target-day admissions are used as inputs.

Reproduce dataset, training artifact and evaluation:

```bash
.venv/bin/python -m src.hex.ml
```

Fixed seed: 42. Temporal-test MAE is approximately **1.61 admissions/day**, versus **2.54** for yesterday's count; unseen-city MAE is approximately **1.76**. See `models/evaluation.json` for RMSE, splits and sample counts. These results measure learning on the synthetic generator; they do not establish accuracy on real hospitals. Larger real-world validation remains future work. The pure-Python ridge implementation requires no scikit-learn dependency.

## Decision engine and state

Hospital status, constraints, case signals, settings, proposals, audits and plan results are stored centrally in SQLite (`data/hex.db`). Public searches are request-only and never become case signals. Each status/constraint/feed change queues planning on a single worker; frequent changes coalesce, results retain snapshot versions, and superseded computations cannot overwrite current results. Failed planning does not prevent public availability reads.

Strategies are baseline, fixed flex-bed allocation, and constrained redistribution, compared on the same seeded demand futures. A greedy flex allocation respects hospital limits and a shared budget; transfer sending limits and receiving capacity are enforced. The recommendation is best among evaluated feasible plans, not a globally optimal solution. Costs, growth, length of stay and geographic assumptions are illustrative.

The assistant only supports an allowlisted command set and stores a preview. Apply rechecks server-side role, proposal ownership and snapshot versions and writes its audit event in the same transaction. Hospital limits are hospital-owned; network settings are administrator-owned.

## Tests

```bash
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests -v
```

Tests cover matching, emergency bypass, unknown/stale status, budget and transfer limits, reproducibility, ML holdouts, API authorization, preview/apply/audit, stale proposals, superseded runs, and failure isolation.
