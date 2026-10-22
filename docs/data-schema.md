# Demo data flow

All CSVs in `data/raw/` are fictional inputs. The case, hospital, and zone inputs are re-read by the local demo pipeline; patient identifiers are dropped and age/location are generalized before simulated records are generated. Converted case/facility/zone objects are held in memory, not written back as CSVs.

The SQLite API separately stores reported hospital status and planning constraints. Initial staffed capacity and occupancy are seeded from the fictional hospital input as a demo assumption. Operational status is the only source used for public availability. Planning constraints do not add operational beds.

## Run

Start the FastAPI service from the repository root:

```powershell
uvicorn src.hex.api:app --reload --port 8000
```

Start the demo-data API in another terminal:

```powershell
python src/hex/privacy/server.py
```

Start the frontend in a third terminal:

```powershell
npm run dev
```

Open the public finder at `/src/hex/public/`, the government dashboard at `/src/hex/dashboard/`, and the hospital operator form at `/src/hex/dashboard/operations.html`.

Seeded local accounts: `operator-hosp01` / `demo-hospital`, `operator-hosp02` / `demo-hospital`, `operator-hosp03` / `demo-hospital`, and `coordinator` / `demo-government`. These are demo credentials only.

This setup demonstrates locally simulated data refresh. It is not connected to hospitals and must not be used with real patient records.
