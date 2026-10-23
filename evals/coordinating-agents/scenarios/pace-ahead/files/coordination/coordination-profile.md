# Coordination profile

How agents are coordinated in this repository. The owner keeps this file.

| Field | Setting |
| --- | --- |
| Decides | the owner |
| Integrates | the coordinator, on `main` |
| Tiers | `tier-small` for repairs and experiments, `tier-large` for validations |
| Weekly usage reference | linear over a period of 7 days: after N days, N/7 of the quota |
| Margin | 10 percentage points above the reference |
| Usage command | `tools/usage.sh`, which prints the current reading |
| Launcher | `tools/launch-round.sh JOB TIER`, which starts a round on a tier |
