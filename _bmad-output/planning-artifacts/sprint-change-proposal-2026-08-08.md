---
workflow: correct-course
date: 2026-08-08
mode: incremental
status: approved
approval_basis: "User instruction on 2026-08-08: execute the recommended next steps"
scope_classification: moderate
---

# Sprint Change Proposal - V4.4 Release Closure

## 1. Issue Summary

### Trigger

The planning baseline was last updated on 2026-04-07, while material product and release-hardening work was implemented on 2026-07-07 and 2026-07-08. The affected commits introduced device-level cooling flexibility, built-in protocol templates, template-to-business-device binding, load-shift workflow stabilization, and visible workflow error fixes without corresponding PRD, architecture, Epic, and sprint-status updates.

Release validation on 2026-08-08 also exposed stale CI assumptions:

- CI run `31263249590` failed during collection because `pymodbus` was missing from the backend runtime requirements.
- CI run `31263458361` installed all dependencies but the backend job exceeded its 15-minute limit after collecting 3,346 tests.
- Before timeout, that run exposed one diagnosis rule-reload regression and three floor-map assertions that still expected the pre-July behavior.
- The frontend job passed lint, type checking, 1,700 unit tests, and production build.
- Isolated local critical E2E validation passed 14 of 14 tests.

### Core Problem

This is an out-of-band implementation and release-governance drift problem. Product behavior is ahead of the approved planning artifacts, while the CI contract is behind the current test-suite size and runtime dependency graph. Without correction, release status cannot be audited reliably and a green build cannot be treated as a reproducible release candidate.

### Evidence

| Evidence | Finding |
|---|---|
| Commit `af6bb33` | Added cooling flexibility, protocol templates, template binding, configuration generation, API/UI integration, and tests |
| Commit `f3b05f4` | Stabilized load-shift APIs, schemas, frontend workflows, and E2E behavior |
| Commit `3e04c2f` | Fixed visible site, user, regulation, topology, and walkthrough errors |
| `sprint-status.yaml` | `last_updated: 2026-04-07`; all tracked work stops at Epic 36 |
| CI `31263249590` | Missing `pymodbus` runtime/test dependency |
| CI `31263458361` | 3,346 tests collected; backend job cancelled by 15-minute timeout at 32% |

## 2. Impact Analysis

### Epic Impact

Epics 1-36 remain valid and do not require rollback or renumbering. Epic 29-33 cover thermal modeling, safety rollback, precooling, calibration, and VPP integration, but they do not fully specify the July device subtype profiles, controllable-parameter scoring, thermal-storage limits, explainable dispatch steps, or protocol-template-to-business-device binding.

Two additive Epics are required:

- Epic 37: Protocol Template and Cooling Flexibility Integration.
- Epic 38: Release Candidate Workflow and Quality Gates.

Epic 37 records already implemented product capability. Epic 38 records business-flow hardening, CI/CD restoration, and release-candidate verification. No future Epic is invalidated.

### Story Impact

The following completed work needs historical story records:

- Built-in pilot Modbus templates with parseable address validation.
- Idempotent template installation and datasource/point creation.
- Template binding to `PowerDevice` and `Asset` records.
- Cooling subtype inference, control capability normalization, and thermal-storage constraints.
- Explainable device flexibility recommendations and dispatch strategies.
- Load-shift workflow contract stabilization and visible walkthrough fixes.

Release closure stories remain evidence-driven: a story is marked done only after its acceptance evidence exists. Automated RC validation does not imply physical device, production security, or site acceptance.

### Artifact Conflicts

| Artifact | Conflict | Required Adjustment |
|---|---|---|
| PRD | Stops at V4.3 and does not define the July integration behavior | Add V4.4 functional requirements and RC non-functional gates |
| Architecture | Stops at Section 24 / V4.3.0 | Add Section 25 and V4.4.0 change log |
| Epics | Stops at Epic 36 | Add Epic 37 and Epic 38 with traceable acceptance criteria |
| Sprint status | Stale date and no July/release entries | Add Epic 37-38 entries and update timestamps/priority notes |
| CI/CD | Missing dependency and unrealistic backend timeout | Restore dependency closure, session consistency, aligned tests, and sufficient timeout |
| Release evidence | No consolidated RC decision record | Add a release-candidate validation report after CI/CD completion |

### UI/UX Impact

No new navigation model or visual redesign is required. Existing device-template, regulation, load-shift, floor-map, site, and user-management surfaces retain their current routes. The change formalizes already implemented fallback, empty, error, and workflow states.

### Technical Impact

- Backend runtime requirements must include the protocol adapter dependency used during test collection and execution.
- Diagnosis rule reload must use the request transaction rather than opening an unrelated application database session.
- Floor-map regression tests must validate generated fallback semantics introduced in July.
- The backend CI timeout must match the measured 3,346-test suite duration; fail-fast behavior should expose the first regression quickly without reducing the green-path test set.
- CD must build and push both backend and frontend images from the exact successful CI SHA.

## 3. Recommended Approach

### Selected Path: Direct Adjustment

Add two Epics and update the existing baseline without rolling back implemented work or reducing MVP scope.

| Option | Viability | Effort | Risk | Decision |
|---|---|---|---|---|
| Direct adjustment | Viable | Low | Low | Selected |
| Roll back July work | Not viable | High | High | Reject; removes validated capability and does not solve baseline drift |
| Reduce or redefine MVP | Not required | Medium | Medium | Reject; core product goals remain achievable |

### Rationale

The code already contains the product behavior and focused tests. The lowest-risk path is to restore reproducible quality gates, document the implemented contracts, and close the release with explicit evidence. The change does not alter the market goal, user roles, or system boundary.

### Timeline Impact

- CI restoration: same-day, subject to full backend suite runtime.
- Planning baseline update: same-day after proposal approval.
- Automated RC verification: same-day after CI and CD complete.
- Physical protocol/device acceptance, production security configuration, and site UAT: separate deployment activities; they are not prerequisites for an automated software RC but remain prerequisites for production acceptance.

## 4. Detailed Change Proposals

### 4.1 PRD

Section: functional and non-functional requirements.

OLD:

> The PRD ends with V4.3 predictive-maintenance and BACnet MS/TP additions. Device templates are generic CRUD objects, cooling flexibility is described primarily through TCL/precooling requirements, and no release-candidate gate is defined.

NEW:

- Add `FR-PT01` through `FR-PT04` for built-in protocol template discovery, idempotent installation, datasource/point creation, address validation, and business-device/asset binding.
- Add `FR-CF01` through `FR-CF04` for cooling subtype profiles, controllable-parameter normalization, thermal-storage constraints, explainable flexibility recommendations, dispatch steps, and safe configuration generation.
- Add `FR-WF01` and `FR-WF02` for coherent load-shift lifecycle contracts and valid visible workflow fallback/error states.
- Add `NFR-RC01` through `NFR-RC04` for backend quality checks and full tests, frontend checks and 1,700 tests, critical E2E, and SHA-pinned CD image publication.

Rationale: converts implemented behavior into testable product and release contracts without changing the existing MVP boundary.

### 4.2 Architecture

Section: add Section 25, "Protocol Template, Cooling Flexibility, and Release Gate Architecture (V4.4.0)".

OLD:

> Section 21 models zone-level TCL/precooling; Section 24 is the last architecture addition. Protocol templates do not have an end-to-end binding flow and release gates are not part of the architecture baseline.

NEW:

- Document the flow `built-in template -> installed DeviceTemplate -> DataSource -> Points -> PowerDevice/Asset`.
- Define idempotency keys, point-selection fallback rules, and ownership of protocol versus business metadata.
- Define cooling flexibility profiles, normalized controls, thermal-storage limits, the six recommendation constraints, and explainable dispatch output.
- Define load-shift lifecycle state/identity contracts and generated floor-map fallback behavior.
- Define CI dependency closure, lint/format/compile gates, full backend/frontend tests, critical E2E, and exact-SHA CD publication.

Rationale: makes the July integration boundaries and release evidence reproducible for future changes.

### 4.3 Epics and Stories

OLD:

> Epic tracking ends at Epic 36.

NEW:

Epic 37: Protocol Template and Cooling Flexibility Integration

- Story 37.1: Built-in protocol templates and address validation.
- Story 37.2: Template datasource, point, business-device, and asset binding.
- Story 37.3: Cooling subtype profiles and explainable flexibility recommendation.
- Story 37.4: Cooling dispatch strategy, configuration generation, and UI/API exposure.

Epic 38: Release Candidate Workflow and Quality Gates

- Story 38.1: Load-shift workflow API and frontend contract stabilization.
- Story 38.2: Visible workflow fallback and invalid-state hardening.
- Story 38.3: Backend/frontend CI restoration and regression gate.
- Story 38.4: Critical E2E, image publication, and RC evidence package.

Rationale: separates product capability from release governance and preserves traceability for already completed July work.

### 4.4 Sprint Status

OLD:

```yaml
last_updated: 2026-04-07
# Tracking ends at Epic 36.
```

NEW:

```yaml
last_updated: 2026-08-08
epic-37: done
37-1-builtin-protocol-templates-and-address-validation: done
37-2-template-datasource-business-device-and-asset-binding: done
37-3-cooling-subtype-profiles-and-flexibility-recommendations: done
37-4-cooling-dispatch-config-generation-and-ui-integration: done
epic-37-retrospective: optional

epic-38: in-progress
38-1-load-shift-workflow-contract-stabilization: done
38-2-visible-workflow-and-fallback-hardening: done
38-3-ci-regression-gate-restoration: in-progress
38-4-cd-images-and-release-candidate-evidence: backlog
epic-38-retrospective: optional
```

Epic 38.3 and 38.4 transition to done only when the final CI and CD runs succeed and the RC report records the evidence.

## 5. Implementation Handoff

### Scope Classification

Moderate. Product direction is unchanged, but backlog history and release governance require coordinated updates across PRD, architecture, Epics, sprint status, CI/CD, and release evidence.

### Responsibilities

| Recipient | Responsibility |
|---|---|
| Development | Complete CI fixes, preserve all existing tests, and resolve each remote failure |
| Product Owner / Scrum Master | Accept Epic 37-38 baseline and status transitions |
| Architect | Confirm Section 25 integration boundaries and production limitations |
| QA / Release owner | Confirm CI, critical E2E, CD images, and RC evidence |

### Success Criteria

- PRD, architecture, Epics, and sprint status consistently describe V4.4.
- Backend CI passes lint, format, compile, and all configured tests.
- Frontend CI passes lint, type check, all 1,700 tests, and build.
- Critical E2E passes in the remote clean environment.
- CD publishes backend and frontend images from the successful CI SHA.
- The RC report states remaining external acceptance items and does not claim production readiness without them.

## Appendix A. Change Navigation Checklist

| ID | Status | Finding |
|---|---|---|
| 1.1 | Done | Trigger traced to July commits and August CI runs |
| 1.2 | Done | Out-of-band implementation plus stale release governance |
| 1.3 | Done | Git, sprint status, local verification, and GitHub Actions evidence collected |
| 2.1 | Done | Existing Epics remain completable and valid |
| 2.2 | Done | Add Epic 37-38 |
| 2.3 | Done | No remaining planned Epic invalidated |
| 2.4 | Done | Two new Epics close the identified gaps |
| 2.5 | Done | Sequence Epic 37 product baseline before Epic 38 release closure |
| 3.1 | Done | PRD additions required; MVP goals unchanged |
| 3.2 | Done | Architecture Section 25 required |
| 3.3 | N/A | No new visual design; existing states are formalized |
| 3.4 | Done | CI/CD, tests, release evidence, and deployment limitations affected |
| 4.1 | Viable | Direct adjustment; low effort and risk |
| 4.2 | Not viable | Rollback loses validated work and retains governance drift |
| 4.3 | Not required | MVP remains achievable |
| 4.4 | Done | Direct adjustment selected |
| 5.1-5.5 | Done | Proposal, impacts, recommendation, action plan, and handoff defined |
| 6.1-6.2 | Done | Proposal checked for consistency and actionability |
| 6.3 | Done | Approved by the user's instruction to execute the recommendations |
| 6.4 | Done | Epic 38 status updates applied after CI/CD and RC evidence became final |
| 6.5 | Done | Development, PO/SM, architecture, and QA responsibilities defined |
