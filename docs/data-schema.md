# Demo data schemas

These files are fabricated examples for local development. They do not describe real people, hospitals, or locations. The `SYN-` IDs and zone labels are illustrative. Do not put identifiable patient data in this directory.

## Files

- `data/synthetic/cases.csv` — one synthetic case signal per row.
- `data/synthetic/hospitals.csv` — illustrative facility capacities and occupancy snapshot.
- `data/synthetic/zones.csv` — illustrative city zones and adjacency.

## Fields

### Cases

| Field | Meaning | Format |
|---|---|---|
| `case_id` | Synthetic record key; no identity mapping | String |
| `reported_at` | Time the signal was recorded, UTC | ISO 8601 timestamp |
| `hospital_id` | Facility reporting the case | String, references hospitals |
| `zone_id` | Generalized area associated with the case | String, references zones |
| `age_band` | Coarsened age range | `lower-upper` |
| `symptoms` | Normalized symptom labels | `|`-separated strings |
| `severity` | Illustrative severity category | `mild`, `moderate`, or `severe` |
| `admitted` | Whether the synthetic case was admitted | Boolean |

### Hospitals

`hospital_id` is the facility key; `name` is a fictional display name; `zone_id` links to zones; `general_beds` and `icu_beds` are total beds; occupied-bed fields are the snapshot counts; `staffed_shift_capacity` is an illustrative available staff count for a shift. Values are made up for demonstration only.

### Zones

`zone_id` is the area key; `display_name` is fictional; `population_estimate` is an illustrative population count; `neighboring_zones` lists adjacent zone IDs separated by `|`.

## Conventions and next steps

CSV files use a header row, UTF-8 encoding, lowercase snake_case field names, and ISO 8601 UTC timestamps. Empty values should be treated as unknown rather than zero. The examples establish an initial demo contract; task 3 can add machine-readable validation and privacy transformations before ingestion.
