# HEX

**Healthcare Emergency eXperimentation & Intelligence** · MangoByte · Smart Cities × Healthcare

HEX helps city healthcare teams prepare for emerging outbreaks. It combines privacy-safe signals from hospitals with simulations to compare response plans across several plausible outbreak scenarios.

> **Don’t plan for one predicted future. Prepare for every plausible one.**

## Workflow

1. **Collect safely:** Hospitals share only the necessary, de-identified case and capacity signals; patient identities stay at the hospital.
2. **Spot unusual patterns:** HEX organizes symptoms and looks for changes that may indicate an emerging syndrome.
3. **Explore plausible futures:** It represents uncertainty in early data and simulates different outbreak paths using a synthetic city and hospital network.
4. **Compare response plans:** It tests options such as adding beds, moving patients, or opening temporary care capacity.
5. **Support decisions:** It presents the plans that hold up across the scenarios, along with risks and assumptions, for human review.

HEX is a decision-support concept, not a diagnostic tool. The initial demo is intended to use synthetic or public data and simulated hospitals.

## Project tasks

- [ ] **1. Project brief and starter structure** — document the idea and organize the repository.
- [ ] **2. Demo data and schemas** — define hospital, case, zone, and capacity inputs; create synthetic examples.
- [ ] **3. Privacy and ingestion** — validate incoming data and implement de-identification/minimization.
- [ ] **4. Syndrome detection** — structure symptoms and flag unusual patterns.
- [ ] **5. Uncertainty and outbreak scenarios** — represent plausible parameter ranges and generate trajectories.
- [ ] **6. City and hospital simulation** — estimate demand and capacity pressure across scenarios.
- [ ] **7. Strategy comparison** — evaluate preparedness options across futures.
- [ ] **8. Dashboard and evaluation** — present results and measure detection, forecast, robustness, and privacy performance.

See the starter folders under `src/`, `data/`, `docs/`, `configs/`, `scripts/`, `models/`, and `tests/` for the planned organization. The code modules are not implemented yet.
