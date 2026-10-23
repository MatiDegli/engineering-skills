# Coordination profile

How agents are coordinated in this repository. The owner keeps this file.

| Field | Setting |
| --- | --- |
| Decides | the owner |
| Implements | helper agents |
| Reviews | a helper that is never the author of the change |
| Integrates | the coordinator, on `main` |
| Helpers at once | at most two |
| Commit size | at most 15 files per commit |

Strategies the owner has decided on:

| Strategy | Decision | Reason |
| --- | --- | --- |
| Longer cache lifetime | rejected | Agents here rarely wait. |
