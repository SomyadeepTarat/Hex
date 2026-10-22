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

## Symptom chat and Groq explanations

The patient finder accepts free text, quick examples, symptom checkboxes, an optional requested specialist, and explicitly requested resources. It shows what it understood and asks for clarification when the request is unclear. It matches current reported services, specialist capabilities, resources and accepting status, then distance. It explains why a closer hospital was excluded. It does not infer a diagnosis, admission requirement, or oxygen prescription from a symptom.

For example, choose **Central / ZONE-03** and use **Lung specialist**: Riverside (10 synthetic km) is suggested because it reports pulmonology; Central (5 synthetic km) reports general medicine only. Ordinary cough/fever without a specialist request prefers the nearer current suitable hospital. Hospital operators can publish updated expertise/resources in **Report expertise and resources**. Both operational and capability reports become stale after 15 minutes.

Distances in `data/synthetic/demo_distances.json` are fictional demonstration routes. Capabilities in `data/synthetic/hospital_capabilities.json` are synthetic initial reports, persisted centrally. They are not real facility measurements, travel times, physician schedules, or quality ratings. Actual deployment needs verified facility feeds and measured routes.

To enable Groq, edit the Git-ignored `.env` file locally:

```dotenv
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Restart the server after configuration changes, then explicitly check **Use Groq** in the patient finder. Your symptom description and selected tags are sent to Groq only for that submitted request. Public requests are not persisted as cases or stored in ordinary application logs. No API key is returned to the browser. A configured key is not a guarantee of working billing/model permissions; provider errors are shown, with a local fallback.

Groq extracts allowlisted symptom tags; inferred specialist/resource requirements need confirmation instead of silently becoming hard requirements. For explanations, Groq selects and orders IDs of server-verified factual sentences. The app renders those sentences verbatim, so the model cannot invent capabilities, distances or a different hospital. This is deliberately grounded explanation curation rather than unrestricted clinical prose. Emergency cues bypass model requests. Groq uses the official Groq Chat Completions endpoint with structured outputs, a 12-second request timeout, at most 1,000 output tokens per call, and a process-wide limit of eight calls per minute. A free-text submission uses at most two calls; automatic five-second refreshes use local matching and make no Groq requests.

References: [Groq structured outputs](https://console.groq.com/docs/structured-outputs). Emergency bypass cues include severe breathing difficulty and chest pain; see [NHS symptom guidance](https://www.nhs.uk/symptoms/shortness-of-breath/). The finite demo cue list is not a validated triage system.

Planning controls now show inline saved values and validation errors. “Set my extra beds to 12” uses the signed-in hospital; the administrator can use the selected hospital. “Set budget to 100”, “Set scenario count to 100”, and “Set horizon days to 14” are network-only changes. Preview → Apply → audit → recompute remains mandatory. A one-day horizon with spare capacity can legitimately recommend baseline after a successful save; the workspace now explains that outcome explicitly.

### Repeatable symptom-chat walkthrough

1. Restart the unified server and open `/hospital/`. Choose **Network administrator** in the same workspace.
2. Click **Publish fresh synthetic network reports** to explicitly replay the saved synthetic values as new reports. This avoids stale status during a presentation without pretending that a real hospital feed is connected.
3. Open `/find-care/`, choose **Central / ZONE-03**, and click **Lung specialist** then **Find and explain**. Riverside at 10 synthetic km should be suggested; the explanation states why Central at 5 km was not chosen.
4. Try **Cough & fever** instead. Without a specialist/resource request, the nearer current suitable hospital is preferred.
5. Publish different expertise/resources or accepting status from the hospital workspace. The patient view recomputes locally within five seconds without additional Groq calls.
6. Test Groq separately by enabling the checkbox for an intentional submission. If Groq denies access, check your Groq billing and team/model permissions. The local result is explicitly identified.

### Broader free-text concerns and useful failures

The interpreter supports a general-assessment category for recognizable health concerns beyond the named symptom tags. Groq distinguishes health-related requests from unrelated inputs; clear health concerns can receive a general-assessment option without forcing the user to choose an exact symptom label. Optional questions such as duration can accompany a suggestion rather than blocking it. This is navigation support, not diagnosis or a guarantee of correct interpretation of every possible message.

Local fallback recognizes stomach-ache variants and additional common concerns such as headache, sore throat, back pain, dizziness and body-part pain. A provider error does not suppress a valid local match. An explicitly requested specialist or resource is never silently dropped: missing requirements remain visible, and unreported specialist expertise is not invented.

Failures distinguish unclear requests, stale/missing reports, non-accepting hospitals, missing requirements and absent network data. Each has a specific title and next step; the same clarification is not repeated twice. Stomach pain has a quick example and a symptom checkbox. Sudden/severe abdominal-pain cues bypass ordinary ranking, consistent with [NHS stomach-ache guidance](https://www.nhs.uk/symptoms/stomach-ache/); the finite cue list is not a validated triage system.
