# HEX

**Healthcare Emergency eXperimentation & Intelligence**  
**Track:** Smart Cities × Healthcare · **Team:** MangoByte

> HEX turns privacy-safe signals from hospitals into outbreak scenarios, tests preparedness options across those scenarios, and recommends plans that remain effective under uncertainty.

**Don’t plan for one predicted future. Prepare for every plausible one.**

## The idea

Early outbreak data is incomplete, so a single forecast can create false confidence. HEX is a city-scale healthcare decision-support concept that detects unusual syndromic patterns, represents uncertainty explicitly, and helps healthcare planners compare response strategies. It supports planning; it does not diagnose patients or replace public-health judgment.

## Workflow

1. **Ingest signals:** Receive de-identified or synthetic case, symptom, time, zone, severity, and hospital-capacity data from multiple facilities.
2. **Protect privacy:** Detect and remove direct identifiers, pseudonymize records, generalize sensitive fields (such as age and location), and retain only modelling-relevant information. Patient identities stay with hospitals.
3. **Structure and discover:** Extract symptoms from clinical-style text, normalize terminology, cluster similar cases, and compare current patterns with historical baselines to flag unusual changes.
4. **Infer uncertainty:** Estimate plausible ranges or distributions for outbreak characteristics such as transmission, severity, and hospitalization rather than asserting one exact value.
5. **Build synthetic scenarios:** Use synthetic population and city-zone characteristics, together with hospital capacity, to generate many plausible outbreak trajectories. Synthetic records are not real patients.
6. **Simulate healthcare impact:** Model case progression, demand, admissions, bed and ICU occupancy, staffing pressure, and movement across hospitals for each scenario.
7. **Test preparedness options:** Compare interventions such as surge beds, patient redistribution, staff reserves, or temporary treatment capacity, subject to resource and access constraints.
8. **Recommend robust plans:** Rank options by how reliably they perform across plausible futures, and show assumptions, uncertainty, overload risks, and expected trade-offs for human review.
9. **Evaluate and monitor:** Measure detection quality, forecast calibration, simulation performance, strategy robustness, and privacy leakage; update the analysis as new signals arrive.

## Intended demo output

A dashboard can present an emerging-syndrome alert, affected zones, plausible hospitalization ranges, hospitals at risk of overload, the number of scenarios simulated, and a preparedness plan with its success rate across those scenarios. Results should be labelled as simulated decision support, with assumptions visible.

## Repository layout

```text
.
├── README.md
├── docs/                  # Architecture, workflow, data and model notes
├── data/
│   ├── raw/               # Local inputs; keep private or licensed data out of Git
│   ├── processed/         # Validated and transformed datasets
│   └── synthetic/         # Generated demo and simulation data
├── models/                # Model artifacts and metadata (large artifacts excluded)
├── configs/               # Scenario, hospital and model configuration
├── scripts/               # Data preparation, training and demo entry points
├── src/hex/
│   ├── ingestion/         # Input adapters and validation
│   ├── privacy/           # PII/PHI detection, minimization and pseudonymization
│   ├── syndromes/         # Symptom extraction, normalization and clustering
│   ├── outbreaks/         # Baselines, anomaly detection and parameter inference
│   ├── population/        # Synthetic population generation and privacy checks
│   ├── hospitals/         # Facility capacity and demand models
│   ├── simulation/        # Outbreak and healthcare-system scenarios
│   ├── optimization/      # Intervention search and robust plan scoring
│   ├── api/               # Service endpoints for the application
│   └── dashboard/         # Planner-facing interface
└── tests/                 # Unit and integration checks
```

## Development status

This repository currently contains the concept brief and starter structure. The modules above are planned boundaries, not claims of implemented functionality. A first demonstrator should use public, synthetic, or explicitly approved data and simulated hospitals; do not commit identifiable patient information.

## Suggested build sequence

1. Define input schemas and a reproducible synthetic demo dataset.
2. Implement validation and privacy transformations, with auditable examples.
3. Build symptom aggregation, baseline comparison, and an interpretable alert.
4. Add uncertain outbreak scenarios and synthetic city/hospital simulation.
5. Compare a small set of preparedness strategies across scenarios.
6. Expose results in a dashboard and report evaluation metrics and limitations.

## Evaluation focus

- **Syndrome and anomaly detection:** precision, recall, F1, and alert timeliness.
- **Uncertainty and forecasting:** calibration, interval coverage, and suitable probabilistic forecast scores.
- **Hospital impact:** error in occupancy and resource-demand estimates.
- **Preparedness:** fraction of plausible scenarios meeting defined capacity and access goals; resource cost and worst-case performance.
- **Privacy:** identifier detection quality and measured re-identification or membership-inference risk for synthetic outputs.

## Privacy and responsible use

HEX is designed around data minimization: hospitals retain identifiable records and share only necessary, protected signals. Synthetic data can still leak information, so generated outputs require privacy-risk checks. Real deployment would need clinical, epidemiological, security, legal, and public-health review. Recommendations must remain explainable and subject to human decision-making.
