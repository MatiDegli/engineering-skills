# Operations criteria

Apply these criteria when a service is deployed or the project keeps persistent data; see the
[areas table](criteria.md#areas). Otherwise close the area in Coverage with
`OPS-* (no deployed service or persistent data)`.

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| OPS-01 | Services document configuration, health, logs, migrations, and rollback | Deployed service | [standard](standard.md#delivery-and-operations) |
| OPS-02 | Persistent data has tested backup and restoration, and agreed acceptable loss and downtime | Persistent data | [standard](standard.md#delivery-and-operations) |
| OPS-03 | Services set objectives on user-visible indicators, alert on symptoms that consume the error budget, and give each alert a runbook | Service in operation | [standard](standard.md#delivery-and-operations) |
| OPS-04 | Changes reach users progressively, stop or roll back automatically on user-visible regressions, and rollback is rehearsed | Deployed service with users | [standard](standard.md#delivery-and-operations) |
