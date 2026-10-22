# Hackathon problem-statement shortlist

Researched 22 October 2026. This is a targeted extraction of public briefs relevant to a two-person, 4–5 hour build, not an exhaustive scrape of every hackathon. Brief summaries below are paraphrases. Proposed products and feasibility judgments are our analysis, not organizer requirements.

## Recommendation

Continue HEX, narrowed to hospital surge planning for a suspected water-borne outbreak. Keep three hospitals, one syndrome, and three constrained response plans. Use explicitly synthetic signals and scenario assumptions. Do not add water sensors, pathogen diagnosis, or a city-scale digital twin.

The strongest full pivot is education: a student-support prioritization dashboard with an evaluated dropout classifier. Prefer it only if demonstrating trained ML is a major judging criterion. It has better immediate labeled-data access but requires a new workflow and pitch.

## Extracted briefs

| Event | Issuer | Identifier | Brief summary | Source |
|---|---|---|---|---|
| SIH 2025 | Ministry of Development of North Eastern Region | SIH25001 | Water-borne disease early warning | S1 |
| SIH 2025 | Government of Rajasthan | SIH25102 | Dropout prediction and counseling | S1 |
| SIH 2025 | Government of Rajasthan | SIH25101 | Remote rural-college classrooms | S1 |
| SIH 2025 | Government of Jharkhand | SIH25031 | Civic issue reporting and resolution | S1 |
| SIH 2025 | Ministry of Fisheries, Animal Husbandry & Dairying | SIH25006 | Livestock farm biosecurity management | S1 |
| SIH 2025 | MathWorks India | SIH25099 | Crop/soil/pest monitoring using imaging and sensors | S1 |
| SIH 2025 | MathWorks India | SIH25100 | Indian road-network simulation modeling | S1 |
| Megathon 2025 archive | Bhashini | Not shown | Multimodal Indian-language applications across a chosen domain | S2 |
| Megathon 2025 archive | Chubb | Not shown | Vehicle-claim damage assessment and fraud checks | S2 |
| Megathon 2025 archive | Chubb | Not shown | Explainable insurance churn analysis | S2 |
| NASA Space Apps 2024 | NASA Space Apps | Challenge title | Agricultural decisions using Earth observations | S3 |
| Emerging Technologies Hackathon 2026 | DoT / TCOE event | PS06 | Edge AI traffic monitoring and signal adjustment | S4 |
| Emerging Technologies Hackathon 2026 | DoT / TCOE event | PS09 | Immersive remote STEM learning | S4 |
| Jammu Smart City Hackathon 2026 | JSCL / JMC | Waste category | Prevent waste entering drains during rainfall | S5 |
| Jammu Smart City Hackathon 2026 | JSCL / JMC | Infrastructure category | Reduce municipal electricity consumption | S5 |
| Jammu Smart City Hackathon 2026 | JSCL / JMC | Resilience category | Faster detection and response to Old Jammu fires | S5 |

## Sources and provenance

- S1: [Institution-hosted SIH portal export](https://www.driems.ac.in/wp-content/uploads/2025/09/Smart-India-Hackathon_PROBLEM-STATEMENTS.pdf). Export dated 31 August 2025. The original SIH portal returned HTTP 403 during research; this copy is not a live official list. IDs and issuers were checked against its text. Some original theme labels are surprising; the proposed track grouping is ours.
- S2: [Megathon host site](https://megathon.in/). The site explicitly labels these as 2025 briefs. It lists Lloyds as a 2026 sponsor, but does not provide the requested Lloyds brief. Do not attribute an inferred problem to Lloyds.
- S3: [NASA Space Apps 2024 agricultural challenge](https://www.spaceappschallenge.org/nasa-space-apps-2024/challenges/leveraging-earth-observation-data-for-informed-agricultural-decision-making/?tab=resources). Challenge identity verified; detailed requirements were not accessible in extracted text.
- S4: [DoT/TCOE host problem statements](https://hackathon2026.tcoe.in/problem-statements.html).
- S5: [Jammu host problem statements](https://hackathon.myjammu.in/ProblemStatements.aspx).
- Additional checked program: [JPMorganChase Code for Good](https://www.jpmorganchase.com/careers/explore-opportunities/programs/tfsg-hackathons?tags=location__Americas__UnitedStatesofAmerica). Confirms nonprofit challenges, but the inspected overview does not publish individual briefs, so none are invented here.
- Additional checked program: [Bajaj Finserv HackRx 6.0 organizer listing](https://unstop.com/hackathons/hackrx-60-bajaj-finserv-1514382/amp). Describes LLM document-query retrieval. Its historical hackrx.in link redirected to unrelated content during research, so use the event listing rather than that domain.

## Four build candidates

### Healthcare: focused HEX

User: district hospital coordinator. Decision: where to add staffed beds or redirect demand under uncertain surge size. Demo: inject a synthetic rise in gastrointestinal syndrome reports; generate occupancy scenarios; compare baseline, staffed flex beds, and bounded transfers. Display worst-case unmet bed-days and the share of scenarios without shortfall. All strategies share a budget and identical futures. Keep inference assumptions visible. This is preparedness simulation, not validated outbreak prediction.

ML owner: data generation, baseline detection, scenario engine, strategy evaluation. Frontend/security owner: existing dashboard, API, input validation, aggregate views. Main risk: speculative scenario assumptions. Reuse advantage: existing hospital schema and interface.

### Education: student-support prioritization

User: college support coordinator with limited counseling slots. Decision: which cases need review this week, and what evidence should the counselor see? Demo: score a held-out cohort, show reason codes, select a weekly review capacity, create a support queue, and record human follow-up. Suggested support actions are rules for counselor review, not proven causal interventions.

Data: [UCI Predict Students' Dropout and Academic Success](https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success), 4,424 records and 36 features, with dropout/enrolled/graduate outcomes. Source context is Portuguese higher education, not an Indian validation cohort. Choose a prediction time and exclude information only available later; a first-semester model must exclude second-semester features. Do not relabel enrolled students as successful graduates. Compare a simple baseline with a tree model and report held-out macro-F1 plus dropout recall at the chosen queue capacity. Feature associations do not prove why someone will drop out.

ML owner: preprocessing, split, classifier, evaluation, reason codes. Frontend/security owner: upload validation, review queue, counselor detail view, access checks. Main risk: changing domains and confusing prediction with effective intervention.

### Smart cities: drain-maintenance prioritization

User: municipal works supervisor with two crews before forecast rain. Decision: which reported drain blockages to inspect first? Demo: load geolocated reports, merge likely duplicates using proximity and text similarity, produce a constrained inspection order, show travel and priority trade-offs, and require human confirmation before closing incidents. Use an explicitly synthetic street network if real routing data are unavailable.

ML owner: duplicate grouping, transparent priority features, route heuristic, comparison against first-in-first-out. Frontend/security owner: map/list, reporting form, crew assignment, protected closure action, audit history. Main risk: no verified local labeled blockage/flood dataset was established in this research. A priority heuristic must not be presented as a validated flood model.

### Agriculture: farm biosecurity incident triage

User: poultry cooperative field officer. Decision: which farms require inspection when visits are limited? Demo: structured farm checklist and reported changes in mortality/feed intake, anomaly flags, nearby-incident context, ranked inspection queue, and authorized follow-up. Use synthetic farm records and clearly label alerts as inspection prompts.

ML owner: synthetic time series, anomaly baseline, distance clustering, prioritization. Frontend/security owner: farmer form, cooperative dashboard, role checks, private farm location handling. Main risk: no labeled outbreak dataset verified; do not claim disease identification or recommend treatment.

## Decision rule

Use focused HEX for the shortest route to a coherent operational demo. Switch to education only when actual model training/evaluation is more important in the rubric than scenario planning. Avoid adding satellite processing, AR/VR, hardware, or on-device deployment under this deadline unless the required assets already work.
