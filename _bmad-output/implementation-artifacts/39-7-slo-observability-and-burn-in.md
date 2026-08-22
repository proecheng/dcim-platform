---
baseline_commit: 2959f0210001958b49a522ef3fcc895981124384
story_key: 39-7-slo-observability-and-burn-in
decision_register:
  D39-03:
    status: recorded
    owner: proecheng
    recorded_at: '2026-08-18'
---

# Story 39.7: SLO Observability, MTTR, and Burn-in

Status: in-progress

## Story

As an operations owner,
I want production-critical metrics, alerts, and recovery evidence to be verifiable during a pre-production window,
so that release decisions use real operational evidence without claiming that a short burn-in proves the annual SLO.

## Ownership And Traceability

- **Implementation and evidence owner:** `proecheng` (single maintainer)
- **Evidence governance:** `single-maintainer`; no BMAD virtual-role approval is required
- **Priority:** P0 / HIGH
- **NFR/action traceability:** NFR-PR05, H3
- **Decision prerequisite:** D39-03 is recorded in this Story and Architecture 26.5 on 2026-08-18
- **Upstream input:** Story 39.3 produces backup, archive, replication, and WAL status; this Story consumes that status without changing the DR mechanism
- **Downstream dependencies:** Story 39.3 cannot sign `PASS` until this Story supplies the alert and trusted-timeline contract; Story 39.6 depends on this Story and Story 39.10

`ready-for-dev` authorizes implementation and local validation. It does not prove the 72-hour pre-production window, annual availability, production MTTR, independent-failure-domain recovery, or the Epic 39 production gate.

## D39-03 Observability Decision

### Release Evidence Window And Consecutive Runs

- The pre-production evidence window is one continuous `>=72 hour` interval tied to one Git SHA, immutable backend/frontend image digests, and one environment fingerprint.
- The window must contain `12` scheduled critical-E2E runs. The first and last qualifying run must span at least 72 hours, adjacent runs must be at least 5 hours apart, and every run must pass on its first attempt.
- Retries, reruns, quarantined failures, skipped critical tests, changed images/configuration, monitoring gaps longer than 5 minutes, or a process restart that loses required state invalidate the affected run or restart the window as defined by the evidence validator. Retries may be retained diagnostically but cannot make a failed run qualify.
- A release candidate is stable only when no critical alert remains unresolved, readiness is continuously successful apart from explicitly recorded incident windows, and all 12 qualifying E2E runs pass without retry.

### Thresholds And Alert Recovery

| Signal | Warning | Critical | Recovery |
|---|---:|---:|---|
| Rolling HTTP error rate over 5 minutes | `>0.5%` | `>1.0%` | `<=0.5%` for three consecutive evaluations |
| Process/gateway CPU | `>=80%` for 5 minutes | `>=90%` for 5 minutes | `<75%` for three consecutive evaluations |
| Process/gateway memory | `>=80%` for 5 minutes | `>=90%` for 5 minutes | `<75%` for three consecutive evaluations |
| Host/gateway disk | `>=80%` for 5 minutes | `>=90%` for 5 minutes | `<75%` for three consecutive evaluations |
| Latest successful backup age | `>=26h` | `>=36h`, missing, or failed integrity/status | `<26h` after a verified success |
| Gateway/data-source backlog | any enabled source with `>=3` consecutive failures | any enabled source at `retry_max_failures`, any enabled gateway heartbeat older than 5 minutes, or a gateway explicitly offline | no enabled source at warning threshold and no stale/offline enabled gateway for three evaluations |
| Required dependency | degraded/unknown where operation can continue | failed database, configured Redis/MQTT failure, failed backup status, or failed readiness | three consecutive healthy readiness/dependency evaluations |

- Every alert includes severity, observed value, threshold, first-observed/fired timestamps, owner `proecheng`, and a concrete runbook/action identifier.
- Health probes and metric scrapes do not pollute RED traffic measurements. Unhandled request exceptions are recorded as 500 errors and logged before being re-raised.
- Alert evaluation fails closed on malformed or stale machine status. Development-disabled optional dependencies are reported as disabled, not healthy or failed.

### Availability, Error Budget, And MTTR

- The post-release SLO is annual service availability `>=99.5%`, owned by `proecheng`. The annual error budget is `0.5%`, equal to `43.8 hours` (`2,628 minutes`) in a 365-day year.
- Availability is calculated from eligible service minutes using readiness and critical user-flow success. No maintenance is excluded unless the exclusion was approved and recorded before the interval; missing telemetry is not counted as good time.
- The 72-hour burn-in reports observed availability and provisional budget consumption only. It must explicitly state that it does not prove the annual SLO.
- MTTR starts at the trusted UTC timestamp when a qualifying critical alert first fires, not when an operator acknowledges it. Recovery ends only after readiness and the critical E2E flow both pass in three consecutive evaluations. The evidence retains raw UTC and monotonic timestamps, alert lifecycle, operator actions, and the three recovery confirmations.
- Any SLO/threshold breach keeps the release gate blocked until the incident is resolved, the invalid window is restarted or an allowed D39-08 exception is recorded, and a corrective-work item with owner and due date exists. Non-waivable Epic 39 controls remain non-waivable.

## Acceptance Criteria

### AC1: D39-03 is deterministic and recorded before development

**Given** the single maintainer is preparing Story 39.7
**When** the Story enters development
**Then** the 72-hour window, 12 first-pass E2E runs, error/resource/backup/gateway thresholds, alert recovery rules, annual SLO/error budget, and MTTR boundaries are recorded in this Story and Architecture 26.5
**And** machine-readable contracts use exactly the same values and reject drift

### AC2: RED, health, dependency, log, and backlog telemetry is observable

**Given** the FastAPI service and its dependencies are running
**When** an authorized viewer requests the observability snapshot or a monitoring system scrapes application metrics
**Then** request rate, error count/rate, duration percentiles, uptime, health/readiness, database, Redis, MQTT, WebSocket, storage, process resource, backup age/status, gateway resource/heartbeat, and data-source failure backlog are returned with UTC capture time and explicit unavailable/disabled states
**And** existing `/api/metrics`, `/api/health`, `/api/readiness`, and `/api/v1/system/health` compatibility is preserved
**And** metric/health probes are excluded from RED traffic and unhandled exceptions produce both a 500 metric and a structured error log

### AC3: Alerts are actionable and fail closed

**Given** a complete or degraded observability snapshot
**When** D39-03 rules are evaluated
**Then** each rule has a deterministic state (`ok`, `pending`, `warning`, `critical`, or `unknown`), threshold, duration, owner, runbook, and lifecycle timestamps
**And** sustained resource rules fire only after five minutes while backup, dependency, heartbeat, and explicit-failure rules can fire immediately
**And** malformed, stale, missing, or failed production status cannot be silently converted to healthy
**And** three consecutive recovery evaluations are required where D39-03 specifies recovery confirmation

### AC4: Availability, error budget, and MTTR are independently recomputable

**Given** raw minute samples and incident timelines
**When** the evidence validator calculates SLI results
**Then** observed availability, good/eligible/missing minutes, provisional error-budget consumption, annual budget, incident start, recovery confirmation, and MTTR are recomputed from raw timestamps
**And** missing telemetry is not good time and retries cannot erase a failure
**And** every short-window result contains an explicit `annual_slo_proven: false` assertion

### AC5: Burn-in evidence rejects false PASS claims

**Given** a candidate manifest and raw burn-in records
**When** the independent validator runs in a new process
**Then** it requires one Git SHA, immutable image digests, one environment fingerprint, at least 72 continuous hours, 12 spaced first-pass critical-E2E runs, complete metric coverage, no unresolved critical alert, and valid MTTR recovery evidence for each incident
**And** it rejects retries, skipped critical tests, stale or missing intervals, image/config drift, self-reported summaries without raw records, or any `PASS` claim that does not meet all conditions
**And** the validator emits a machine-readable validation result and a non-zero exit code for invalid evidence

### AC6: The real pre-production window remains an external evidence gate

**Given** local/unit/integration tests pass
**When** no genuine fixed-image pre-production window spanning at least 72 hours has completed
**Then** the Story remains `in-progress`, the burn-in manifest remains `pending` or `blocked`, and no annual SLO or production-readiness `PASS` is claimed
**And** after the real window completes, raw records, commands, versions, environment fingerprint, source hashes, alert/incident timelines, and the 12 first-pass E2E results are published under `_bmad-output/test-artifacts/epic-39/39.7/`

### AC7: Gate ownership and downstream effects stay explicit

**Given** Story 39.7 evidence is evaluated
**When** the result is consumed by Stories 39.3, 39.6, and the Epic 39 gate
**Then** the manifest identifies owner `proecheng`, Git SHA, immutable image digests, environment, UTC window, tools, commands, artifacts, calculated metrics, known limits, decisions, and AC mapping
**And** a Story result does not automatically approve production or prove independent-failure-domain recovery
**And** any breach creates or references corrective work and keeps dependent gates blocked until deterministic closure

## Tasks / Subtasks

- [x] Task 1: Correct and extend application RED collection (AC: #2, #3)
  - [x] 1.1 Add bounded timestamped request/error samples and a correct rolling five-minute view while preserving the current JSON metrics contract
  - [x] 1.2 Exclude probes/scrapes, record unhandled exceptions as 500, and emit structured exception logs
  - [x] 1.3 Add deterministic unit tests for rolling eviction, rates, percentiles, errors, and concurrency-safe snapshots
- [x] Task 2: Build the unified observability snapshot and alert evaluator (AC: #1, #2, #3)
  - [x] 2.1 Reuse health/readiness, process/disk, WebSocket, Redis/MQTT, Gateway/DataSource, and Story 39.3 status producers
  - [x] 2.2 Add an authorized system observability endpoint with explicit capture time, freshness, disabled, unavailable, and degraded states
  - [x] 2.3 Implement D39-03 rules, five-minute pending/firing lifecycle, three-sample recovery, owner, and runbook metadata
  - [x] 2.4 Add API and service tests for healthy, warning, critical, missing, stale, malformed, and recovery paths
- [x] Task 3: Implement availability, error-budget, and MTTR calculations (AC: #4, #7)
  - [x] 3.1 Calculate good/eligible/missing minutes, observed availability, and provisional/annual budget without extrapolating burn-in to a year
  - [x] 3.2 Calculate MTTR from trusted alert time through three readiness plus critical-E2E confirmations and reject clock/order inconsistencies
  - [x] 3.3 Test incident, telemetry-gap, excluded-maintenance, unresolved, and boundary cases
- [x] Task 4: Add the machine-readable contract and independent evidence validator (AC: #1, #4, #5, #7)
  - [x] 4.1 Publish the D39-03 contract and a pending 39.7 manifest bound to the Story decision
  - [x] 4.2 Validate immutable provenance, 72-hour continuity, sample freshness, 12 spaced first-pass E2E runs, alert closure, MTTR evidence, and AC mapping
  - [x] 4.3 Emit deterministic JSON validation output and fail non-zero on drift, retry, gap, unresolved alert, or false PASS
  - [x] 4.4 Add positive and adversarial tests that recompute all derived values from raw evidence
- [ ] Task 5: Verify locally and execute the real burn-in gate (AC: #5, #6)
  - [x] 5.1 Run Story-specific backend tests, Ruff, evidence validation negative gate, and `git diff --check`
  - [x] 5.2 Run the complete backend regression suite and configured quality checks without changing unrelated failures
  - [x] 5.3 Record local validation as implementation evidence only, with `annual_slo_proven: false`
  - [ ] 5.4 Run the genuine fixed-image pre-production window for at least 72 hours with 12 spaced first-pass critical-E2E runs; publish and independently validate the final evidence before changing this Story to `review`

## Dev Notes

### Existing Components To Reuse

- `backend/app/middleware/metrics.py` already owns the in-memory RED collector. Extend it; do not create a second request collector.
- `backend/app/middleware/metrics_middleware.py` already times requests. Preserve Starlette middleware behavior and make exception accounting explicit.
- `backend/app/main.py` already exposes `/api/health`, `/api/readiness`, and `/api/metrics`. Keep their response compatibility and avoid counting their scrape traffic.
- `backend/app/api/v1/system_health.py` already exposes authorized component health and storage. Add the unified endpoint here rather than adding an unrelated router.
- `backend/app/models/gateway.py` contains Gateway CPU/memory/disk/heartbeat and DataSource status/failure fields. Query only enabled records and preserve site authorization policy.
- `deploy/postgres-backup/status-snapshot.sh` atomically publishes `backup-status.json`, `pgbackrest-info.json`, and `postgres-status.json`. Treat them as untrusted machine inputs and never execute shell commands from an API request.
- `prometheus-client>=0.16.0`, PyYAML, psutil, pytest, and Ruff already exist. Do not add a dependency for this Story.

### Architecture And Safety Guardrails

- Development-disabled Redis/MQTT may be `disabled`; configured production dependency failure is not healthy.
- Keep API responses free of secrets, absolute repository credentials, connection strings, and raw backup keys. Evidence stores paths relative to the evidence root.
- An in-memory runtime evaluator is process-local and must be labeled as such until Story 39.10 selects the supported topology. The independent evidence validator is authoritative for release evidence.
- Do not mutate Gateway/DataSource, backup, alert, or incident state from the read-only observability endpoint.
- Use `datetime.now(timezone.utc)` for new timestamps. Evidence must use timezone-aware UTC and reject reversed or duplicate lifecycle ordering.
- Local SQLite tests may validate logic and API contracts but cannot replace PostgreSQL/Redis/MQTT/pre-production runtime evidence.

### Testing Requirements

- Follow red-green-refactor in task order.
- Place backend tests in `backend/tests/test_story_39_7_*.py`; tests must pass individually and in the full backend suite because global singletons have known isolation risk.
- Inject clocks and status readers in unit tests; do not wait five minutes or 72 hours in tests.
- Test exact threshold boundaries (`0.5`, `1.0`, `80`, `90`, `26h`, `36h`, three failures, retry maximum, five-minute heartbeat) and fail-closed parsing.
- The evidence validator must be importable for unit tests and runnable as a separate CLI process.

### Project Structure Notes

- New service logic belongs under `backend/app/services/`; HTTP composition stays in `backend/app/api/v1/system_health.py`.
- D39-03 deployment/evidence contracts belong under `deploy/observability/`; executable evidence tooling belongs under `scripts/`.
- Formal Story evidence belongs under `_bmad-output/test-artifacts/epic-39/39.7/`; do not mark placeholder or local results as production evidence.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-397-SLO-可观测性MTTR-与连续运行H3]
- [Source: _bmad-output/planning-artifacts/epics.md#Epic-39-Story-依赖关系]
- [Source: _bmad-output/planning-artifacts/architecture.md#265-可观测性SLO-与预生产证据]
- [Source: _bmad-output/planning-artifacts/architecture.md#268-生产证据包]
- [Source: _bmad-output/planning-artifacts/architecture.md#269-决策与例外治理]
- [Source: _bmad-output/implementation-artifacts/39-3-postgresql-disaster-recovery-and-failover.md#AC2-自动加密备份连续-WAL-和保留策略失败关闭]
- [Source: backend/app/middleware/metrics.py]
- [Source: backend/app/middleware/metrics_middleware.py]
- [Source: backend/app/api/v1/system_health.py]
- [Source: deploy/postgres-backup/status-snapshot.sh]

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

### Implementation Plan

- Extend the existing collector with bounded cumulative samples plus a clock-injected rolling window; retain current top-level metric fields and correct percentiles with nearest-rank calculation.
- Compose dependency, gateway, backup, resource, and RED inputs in one read-only service; evaluate alert state with an injected monotonic/UTC clock and process-local lifecycle explicitly labeled.
- Keep release evidence authoritative in an independent CLI validator that recomputes availability, error budget, MTTR, continuity, provenance, and first-pass E2E rules from raw records.
- Deploy the fixed candidate through a standalone no-build Compose definition that joins the Story 39.3 database network and status volume; freeze image, service-config, process, and host identity before starting the real window.
- Drive repeated deployments from one versioned YAML inventory and bounded parallel Docker-context workers; verify immutable images, external resources, runtime health, and first-attempt Playwright results per target while keeping secrets out of reports.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- D39-03 recorded before `ready-for-dev`; the real 72-hour pre-production gate remains explicitly unproven.
- Task 1 complete: added bounded five-minute RED samples, corrected nearest-rank percentiles, excluded probes/scrapes, and accounted/logged unhandled 500 responses; 3 focused tests and Ruff pass.
- Task 2 complete: added the authorized read-only observability snapshot, D39-03 alert lifecycle, Story 39.3 backup-status fail-closed parsing, gateway backlog/resource aggregation, real MQTT state, and Redis readiness failure handling; 30 related regression tests and Ruff pass.
- Task 3 complete: added independent availability/error-budget and MTTR recomputation; missing telemetry remains bad time, only pre-approved maintenance is excluded, and recovery requires three consecutive readiness plus critical-E2E passes; 5 focused tests and Ruff pass.
- Task 4 complete: published the D39-03 YAML contract, lifecycle-aware pending `BLOCKED` manifest/schema, pure contract layer, and independently runnable fail-closed validator for provenance, hashes, continuity, retries, E2E spacing, alerts, incidents, source hashes, AC mapping, and false annual claims; the CLI needs no application runtime secret.
- Task 5.1/5.3 complete: 67 Story tests, Ruff, schema contradictions, Compose `VCS_REF` positive/negative checks, pending-evidence non-zero gate, and `git diff --check` pass; local evidence explicitly records `annual_slo_proven: false` and `BLOCKED`.
- Task 5.2 complete by partition: the complete backend corpus passes (`4187 passed, 9 skipped`), including the device-template file separately (`22 passed`); the all-in-one pytest process still has an asynchronous teardown/resource-accumulation risk near 9%, with no business assertion failure in partitioned coverage.
- Fixed-image baseline prepared from candidate `ba1177448958c90e7ab979a3666f8719208c2f8f` using backend image `dcim-backend@sha256:2024d5d0e953153674a769307dbfccb840cbe47596e3277a8efbb09b17b626fc`, frontend image `dcim-frontend@sha256:28f85db1baf1f039614c2e1ea4b4a4a1fc610bfda3c30ce239f7b018f6ee0032`, and environment fingerprint `1e112779666dad5dab8cd69e2298bda847f556eda34ec01c7baedc844e5ab0db`.
- Upgraded the frontend candidate build stage to Node 22 and hardened the preparation tool for UTF-8 BuildKit output on Windows; 6 preparation-tool tests and the frontend production build pass.
- Independent validation rejects the baseline with the expected non-zero exit code only because the manifest is `BLOCKED`, the window and availability samples have not started, critical-E2E placeholders remain, and the resolved incident drill is absent; no provenance binding error was reported.
- Published the fixed backend and frontend candidates to GHCR under `story-39-7-ba11774` without moving `latest`; GHCR and Buildx independently report the original immutable digests and OCI revision `ba1177448958c90e7ab979a3666f8719208c2f8f`.
- Added a standalone pre-production Compose definition, host-only environment template, and operational deployment plan that prohibit builds and automatic pulls, require immutable dependencies, and connect the application to Story 39.3 external database/status resources; all 68 Story tests, 7 preparation/deployment guard tests, Ruff, and Compose configuration validation pass.
- Added a cross-platform fleet controller with `plan`, `preflight`, `deploy`, `verify`, `test`, and `status` actions, a ten-target Docker-context inventory, bounded failure-isolated concurrency, SSH loopback tunnels for headed external Edge, per-target temporary authentication/results isolation, and sanitized JSON reports. Configurable E2E usernames and browser channels now work in the critical flow; 83 Story tests, Ruff, and the 19-test Playwright collection under `msedge` pass. The local Linux/amd64 engine has no Story 39.3 external network or status volume, so no pre-production window was started.
- Task 5.4 remains open: no genuine immutable-image 72-hour pre-production window or 12 spaced first-pass E2E runs have occurred, so this Story remains `in-progress`.

### File List

- `.gitignore`
- `_bmad-output/implementation-artifacts/39-7-slo-observability-and-burn-in.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/planning-artifacts/architecture.md`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `backend/app/contracts/__init__.py`
- `backend/app/contracts/observability.py`
- `backend/app/contracts/slo_evidence.py`
- `backend/app/core/authorization.py`
- `backend/app/middleware/metrics.py`
- `backend/app/middleware/metrics_middleware.py`
- `backend/app/mqtt/client.py`
- `backend/app/services/observability.py`
- `backend/app/services/slo_evidence.py`
- `backend/app/api/v1/system_health.py`
- `backend/app/main.py`
- `backend/authz_inventory.yaml`
- `backend/tests/test_story_39_7_metrics.py`
- `backend/tests/test_story_39_7_observability.py`
- `backend/tests/test_story_39_7_sli.py`
- `backend/tests/test_story_39_7_evidence.py`
- `backend/tests/test_story_39_7_prepare.py`
- `backend/tests/test_story_39_7_deploy.py`
- `backend/app/core/redis_lock.py`
- `backend/tests/test_gateway_registration.py`
- `backend/tests/test_redis_lock.py`
- `deploy/observability/story-39-7-contract.yaml`
- `deploy/observability/docker-compose.story-39-7-preprod.yml`
- `deploy/observability/story-39-7-preprod.env.example`
- `deploy/observability/story-39-7-preproduction-deployment.md`
- `deploy/observability/story-39-7-fleet-deployment.md`
- `deploy/observability/story-39-7-targets.example.yaml`
- `docker-compose.yml`
- `e2e/auth.setup.ts`
- `e2e/auth.spec.ts`
- `playwright.config.ts`
- `scripts/story_39_7_evidence.py`
- `scripts/story_39_7_prepare.py`
- `scripts/story_39_7_deploy.py`
- `scripts/story_39_7_burnin.py`
- `backend/tests/test_story_39_7_burnin.py`
- `_bmad-output/test-artifacts/epic-39/39.7/manifest.yaml`
- `_bmad-output/test-artifacts/epic-39/39.7/manifest.schema.json`
- `_bmad-output/test-artifacts/epic-39/39.7/local-validation.json`
- `_bmad-output/test-artifacts/epic-39/39.7/alerts.json`
- `_bmad-output/test-artifacts/epic-39/39.7/availability_samples.json`
- `_bmad-output/test-artifacts/epic-39/39.7/backend_image_manifest.json`
- `_bmad-output/test-artifacts/epic-39/39.7/baseline-validation.json`
- `_bmad-output/test-artifacts/epic-39/39.7/e2e_runs.json`
- `_bmad-output/test-artifacts/epic-39/39.7/environment.json`
- `_bmad-output/test-artifacts/epic-39/39.7/frontend_image_manifest.json`
- `_bmad-output/test-artifacts/epic-39/39.7/incidents.json`
- `_bmad-output/test-artifacts/epic-39/39.7/maintenance_windows.json`
- `_bmad-output/test-artifacts/epic-39/39.7/provenance_samples.json`
- `_bmad-output/test-artifacts/epic-39/39.7/source_hashes.json`
- `_bmad-output/test-artifacts/epic-39/39.7/trusted-provenance.json`

## Change Log

- 2026-08-18: Created Story 39.7 and recorded D39-03 numeric observability, SLO, MTTR, and burn-in decisions.
- 2026-08-18: Implemented RED/health observability, persistent alert evaluation, SLI/MTTR recomputation, trusted burn-in evidence validation, lifecycle-aware manifest schema, immutable image provenance, and local blocked-gate evidence; Story remains in progress pending complete regression and genuine 72-hour burn-in.
- 2026-08-19: Cleared full backend regression after fixing a test-isolation MQTT settings assertion and hardening Redis lock client reuse across event loops; targeted Ruff and diff checks passed on touched files.
- 2026-08-19: Prepared the Node 22 fixed-image candidate and trusted local `BLOCKED` baseline, fixed Windows BuildKit output decoding, and recorded immutable SHA/digest/environment provenance; the genuine 72-hour gate remains open.
- 2026-08-19: Published the fixed application images to GHCR and added the no-build pre-production deployment package; Story remains in progress until a real target, collector, scheduled E2E runs, and incident drill complete the external gate.
- 2026-08-19: Added inventory-driven cross-platform fleet deployment, runtime verification, SSH-tunneled headed Edge E2E execution, failure-isolated parallel reports, and configurable critical-test users/browser channels; the Story remains blocked pending the genuine 72-hour window.
- 2026-08-22: Added the fail-closed one-minute burn-in collector, absolute headed Edge schedule, controlled Redis incident/recovery drill, Windows sleep prevention, runtime drift detection, status/stop controls, and 9 focused tests; Task 5.4 remains open until the real 72-hour evidence validates.
