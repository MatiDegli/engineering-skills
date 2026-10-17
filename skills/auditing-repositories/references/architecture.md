# Architecture and performance

## Start small

Start with a deployable application and modules organized by responsibility. Separate business
logic, transport, persistence, and providers when those boundaries emerge; inject dependencies
there. Avoid layers that only forward calls. See [structure](structure.md).

| Observed need | Add | Evidence |
| --- | --- | --- |
| Slow reads | Indexes and bounded queries | Query plan, volume, and latency |
| Work exceeding a request's time budget | Queue with idempotency and recovery | Duration, retries, and duplicate cost |
| Saturated resources | Concurrency limits and backpressure | Memory, CPU, connections, and sustained load |
| Expensive repeated reads | Cache with invalidation and TTL | Hits and stale-data cost |
| Independent deployments/teams | Service boundaries | Coupling and operating cost |
| Packages that change together | Monorepo and shared tooling | Reuse and versioning needs |

## Contracts, effects, and resources

- Validate schemas at inputs, persistence, and integrations; test compatibility when changing them.
- Centralize configuration; use timezone-aware times and UTC for exchange. Design migrations
  compatible with deploy/rollback, and bound transactions and pools.
- Keep business rules independent of network, disk, processes, and SDKs; put effects in adapters.
  Entrypoints create resources explicitly; imports do not start services.
- Give tasks, threads, and processes clear ownership, timeouts, cancellation, and cleanup. Avoid
  unsupervised tasks, blocking waits in async code, and mutable global runtime state.
- Apply the same to scripts and tooling, agent tooling included. Give every wait a deadline, start
  children in their own process group so that a timeout reaches grandchildren too, clean up the whole
  tree on termination signals, and stop processes by exact identifier. A pattern that matches command
  lines can also match the shell that runs it, so a wait on such a pattern never ends.
- Make errors observable; use broad catches only at justified isolation boundaries. Bound retries
  by cause, time, cost, and idempotency.
- Derive state that can be computed and make shared state explicit. Separate DTOs from domain/ORM models,
  avoid cycles, and check boundaries with import contracts when real modules exist.
- Distinguish application permissions from operating-system isolation. Test failures and resource
  shutdown according to [validation](validation.md).

## Verifiable optimization

1. Fix the load, data, environment, and latency, resource, or cost budget.
2. Measure a baseline and profile the bottleneck.
3. Change one primary variable and compare under the same conditions.
4. Record the result and decision cost; explain differences in scope.
5. Add a regression check to the critical path when feasible. Measure run-to-run variance on the
   target machine before fixing its threshold, and keep it out of correctness suites, which a busy
   host makes flaky.

For services, measure errors, p95/p99 latency, saturation, and volume; correlate logs without
secrets. Test sustained load, peaks, concurrency, data growth, and recovery after overload/restart.
Observe queues and pools as well as the happy path. For persistent data, rehearse migration/restore
and define acceptable loss and downtime. For numerical computation, agree on tolerances before
comparing parallel results. Operational complexity and optimizations should respond to these
measurements.

## Products with models or LLMs

Version prompts, schemas, and evaluations. Validate outputs and provenance; limit tools, cost,
time, and retries. Treat retrieved content as data that grants no permissions. Record model
source/version; evaluate abstention or human review according to the harm of an error. Add context
retrieval or memory only in response to a measured need.

Sources checked on 2026-10-17 against the claims they support:
[signals to process groups](https://man7.org/linux/man-pages/man2/kill.2.html).
