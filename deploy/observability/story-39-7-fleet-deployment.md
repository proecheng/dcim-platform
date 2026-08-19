# Story 39.7 Fleet Deployment

## Outcome

One control computer can now deploy and test the fixed Story 39.7 candidate
on ten Docker targets. The control plane is:

```text
one YAML inventory
        |
        v
story_39_7_deploy.py -- bounded parallel workers
        |
        +-- local Docker Desktop (Linux containers)
        +-- Docker Engine over SSH context
        +-- Docker Engine over SSH context
        +-- ... up to the inventory size
        |
        +-- sanitized JSON report per action
        +-- local headed Playwright or remote loopback through SSH tunnel
```

The repository, Compose file, environment files, Node.js, and Playwright stay
on the control computer. Docker contexts send the Compose workload to each
engine. A repository checkout is not required on every target.

This automation deploys and verifies a candidate. It does not collect the
complete 72-hour evidence window and does not change the Story 39.7 release
gate from `BLOCKED`.

## Supported systems

The control script uses Python 3.11, Docker CLI, and standard OpenSSH tools,
so the control computer may run Windows 10/11, Linux, or macOS.

| Managed target | Support | Requirement |
| --- | --- | --- |
| Linux host | Yes | Docker Engine, Compose v2, `amd64` |
| Windows host | Yes, through Docker Desktop or WSL2 | Linux-container mode, `amd64` |
| Intel macOS host | Yes, through Docker Desktop | Linux containers, `amd64` |
| Native Windows containers | No | Candidate images are Linux images |
| ARM64 / Apple Silicon engine | No for this fixed candidate | Publish and validate a separate multi-architecture candidate first |

The `bootstrap` action can create the Story 39.3 database, DR status volume,
first verified full backup, and Story 39.7 application on an empty target.
The older `deploy` action remains available when Story 39.3 already exists.

## One-time control-computer setup

Install or verify:

- Python 3.11 and PyYAML 6.0.3.
- Docker CLI with Docker Compose v2.
- Node.js 22 and repository dependencies installed with `npm ci`.
- Microsoft Edge installed on a Windows control computer for the example's
  `browser_channel: msedge`, or Playwright Chromium installed with
  `npx playwright install chromium` when no channel is configured.
- OpenSSH client and key-based access to remote targets.
- A GHCR login on the control computer that can pull the private immutable
  application and PostgreSQL packages. Image pulls are sent through each
  Docker context before remote Compose starts with `--pull never`.

Confirm the Python dependency without exposing configuration:

```bash
python -c "import yaml; print(yaml.__version__)"
```

Create one Docker context for each remote engine. For example:

```bash
docker context create qa-linux-01 --docker host=ssh://deploy@qa-linux-01.example.invalid
docker --context qa-linux-01 info
```

On PowerShell, quote the Docker endpoint value:

```powershell
docker context create qa-linux-01 --docker "host=ssh://deploy@qa-linux-01.example.invalid"
docker --context qa-linux-01 info
```

The remote SSH account must be authorized to use Docker without an
interactive password or elevation prompt.

## Inventory and secret files

Copy the example inventory to a host-specific file and replace context names,
SSH destinations, and target names:

```bash
cp deploy/observability/story-39-7-targets.example.yaml \
  deploy/observability/story-39-7-targets.yaml
```

The example contains ten targets and a concurrency limit of three. All paths
are resolved relative to the inventory file except Playwright spec paths,
which are resolved from the repository root.

Environment files are intentionally outside the repository. Create one from
`story-39-7-preprod.env.example` for every target. Do not commit the populated
files. On Linux or macOS, restrict each file to its owner:

```bash
install -d -m 0700 ../dcim-fleet-secrets
for target in workstation qa-linux-01 qa-linux-02 qa-linux-03 qa-linux-04 \
  qa-linux-05 qa-linux-06 qa-linux-07 qa-linux-08 preproduction; do
  install -m 0600 deploy/observability/story-39-7-preprod.env.example \
    "../dcim-fleet-secrets/${target}.env"
done
```

On Windows, use an access-controlled directory outside the checkout:

```powershell
$targets = @(
  "workstation", "qa-linux-01", "qa-linux-02", "qa-linux-03",
  "qa-linux-04", "qa-linux-05", "qa-linux-06", "qa-linux-07",
  "qa-linux-08", "preproduction"
)
New-Item -ItemType Directory -Force D:\dcim-fleet-secrets | Out-Null
foreach ($target in $targets) {
  Copy-Item deploy\observability\story-39-7-preprod.env.example `
    "D:\dcim-fleet-secrets\$target.env"
}
```

Use distinct credentials for pre-production. Passwords inside URLs must be
percent-encoded. The control script validates presence and consistency but
never writes environment values to its reports.

Each target also declares a `dr` block. `secret_directory` must be outside the
checkout. Missing DR secret files are generated with exclusive creation;
existing files are validated and are never overwritten. For SSH targets every
Compose, generated DR environment, and secret file is copied to a same-directory
`.incoming-*` path. The remote account verifies owner and SHA-256, applies mode
`0600`, and atomically renames it. Existing secrets must also match byte-for-byte;
they are never replaced. A shell trap and controller cleanup cover command
failure, SCP interruption, and control-process interrupts. On Windows the
controller applies and reads back a single-current-SID protected DACL before it
reads each target environment file and whenever it creates secret or state files.

`state_directory` is also outside the checkout. Back it up with the control
computer configuration: it is the sanitized source of truth for rollback.
Restrict it to deployment operators even though it contains no secret values.
The controller applies the same current-account-only Windows ACL to this
directory and its state files.

## Zero-to-one lifecycle

On a new empty Docker host, one command performs the complete first deployment:

```bash
python scripts/story_39_7_deploy.py bootstrap \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target qa-linux-01
```

`bootstrap` fails closed if it finds existing Compose resources, an existing
pgBackRest repository volume, or an existing lifecycle state. It then:

1. validates Linux/amd64, Compose, inventory paths, the canonical manifest, and
   confirms that the target is empty;
2. writes a sanitized `bootstrap_pending` / `prepared` checkpoint before the
   first persistent lifecycle change;
3. creates or reuses protected secret files without replacing them;
4. pulls the exact canonical PostgreSQL, final PostgreSQL, schema application,
   and Story 39.7 application images;
5. starts the canonical primary and restores the approved 188-table schema;
6. explicitly transitions the primary to the final DR runtime;
7. starts the standby and backup scheduler, then runs `stanza`, `full`, `check`,
   `verify`, and `status`;
8. deploys Story 39.7, verifies health/readiness, and runs headed Edge E2E when
   the target enables E2E;
9. promotes the checkpoint to a verified state snapshot for upgrade and rollback.

The controller checkpoints `canonical_running`, `schema_verified`,
`runtime_started`, and `dr_verified` as those phases finish. If any phase is
interrupted, fix the cause and run the identical `bootstrap` command again. It
resumes from the last completed phase; a completed schema report is reused and
an application/E2E retry after `dr_verified` does not recreate the database,
restart schema bootstrap, create another first full backup, or delete a volume.
Schema report reuse requires exact project, container, network, database,
approved image, artifact, catalog, table inventory, and Alembic identities. A
post-schema resume also requires the original Docker daemon and primary-volume
fingerprint, then re-queries and hashes the full live catalog through a one-off
approved backend container before continuing.

The lifecycle journal contains immutable image references but no passwords,
tokens, URLs, rendered Compose, configuration values, or generated DR secrets.
Its HMAC-SHA256 key and digest-addressed Compose/configuration snapshots live in
the protected repository-external `secret_directory`; any signature, snapshot,
Docker daemon, primary volume, repository volume, live catalog, stanza, or
initial-full-backup mismatch fails closed. Every lifecycle change invalidates any
formal 72-hour observation window and retains `release_gate: BLOCKED`.

For a later application release, update that target's external environment
file to the new immutable references and run:

```bash
python scripts/story_39_7_deploy.py upgrade \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target qa-linux-01 \
  --schema-compatible
```

`--schema-compatible` is an explicit operator assertion in addition to an
automated contract gate. The controller compares the candidate backend with
the approved schema application image across table names, columns, types, Enum
members, nullability, primary/foreign keys, constraints, indexes, Alembic heads,
and the hash of every migration file. The controller refuses any difference and any
database runtime change. Schema-changing releases must use the migration and
restore-point workflow first. Upgrade writes a pending journal before changing
containers and records the previous verified release only after verification.

To restore the previous immutable application release without deleting any
database, Redis, EMQX, backup, or status volume:

```bash
python scripts/story_39_7_deploy.py rollback \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target qa-linux-01 \
  --schema-compatible
```

Rollback also works after a failed pending upgrade, even when candidate release
fields in the current environment file are malformed. It restores the verified
immutable release fields and non-sensitive application configuration snapshot,
while requiring the current secret values to remain available. It uses the saved
Compose snapshot and requires all rollback images by local digest, so a registry
outage does not turn rollback into an image pull. The lifecycle code never runs
`docker compose down -v` and never removes a data volume.

Lifecycle operations take an exclusive local file lock and reserve a uniquely
named, running `--rm` container on the target Docker daemon. The lock carries
owner, action, and UTC expiry labels. The controller refreshes its heartbeat every
60 seconds; after 30 minutes without a successful heartbeat the container exits,
so a crashed controller cannot leave a permanent lock. Upgrade and rollback fail
unless the approved DR runtime image already exists on the target; lock
acquisition never pulls it from a registry. This serializes separate control
processes even when they use different local state directories. Immediately
before lifecycle execution, context endpoints and Docker daemon IDs are resolved;
aliases to the same engine cannot reuse application projects, DR projects, or
pgBackRest repository volumes. Remote directories are also unique per SSH host.

If a legacy or abnormal stopped lock remains, first confirm no lifecycle process
is active, inspect its labels and state, and remove only that exact container:

```bash
docker --context qa-linux-01 container inspect dcim-lifecycle-lock-<daemon-id-hash>
docker --context qa-linux-01 container rm dcim-lifecycle-lock-<daemon-id-hash>
```

The controller automatically removes a stopped lock only when it has the DCIM
lock label and its parseable lease expiry is in the past. It never removes a
running lock or an unlabelled same-name container.

## Deployment workflow

Use the same command on Windows PowerShell, Linux, and macOS:

```bash
python scripts/story_39_7_deploy.py plan \
  --inventory deploy/observability/story-39-7-targets.yaml

python scripts/story_39_7_deploy.py preflight \
  --inventory deploy/observability/story-39-7-targets.yaml

python scripts/story_39_7_deploy.py deploy \
  --inventory deploy/observability/story-39-7-targets.yaml

python scripts/story_39_7_deploy.py test \
  --inventory deploy/observability/story-39-7-targets.yaml
```

PowerShell accepts the commands on one line or with its backtick line
continuation character instead of `\`.

Actions are deliberately separate:

| Action | Effect |
| --- | --- |
| `bootstrap` | Empty host to Story 39.3 canonical schema, final DR runtime, first full backup, Story 39.7 application, verification, optional headed E2E, and state snapshot; resumes from the last completed bootstrap phase |
| `plan` | Validate inventory, env placeholders, immutable digests, and test topology without contacting Docker |
| `preflight` | Require Linux/amd64, Compose, Story 39.3 network and volume, and valid Compose interpolation |
| `deploy` | Pull exact digests, verify image IDs and OCI revision, start with `--no-build --pull never`, then run health checks |
| `upgrade` | Require verified state and `--schema-compatible`, journal the candidate, deploy exact digests, verify, and retain the previous release |
| `rollback` | Require `--schema-compatible`, restore the previous verified immutable references, preserve all volumes, and verify |
| `verify` | Re-check candidate images, service health, backend health, Nginx proxy health, and readiness |
| `test` | Run `verify`, then execute the first-attempt critical Playwright suite with zero retries |
| `status` | Independently return sanitized application, signed lifecycle journal, and DR service state; the journal remains readable with Docker offline, while missing/exited/unhealthy services produce `partial` and a non-zero exit |

Run one or more selected targets while diagnosing a failure:

```bash
python scripts/story_39_7_deploy.py deploy \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target qa-linux-03 --target qa-linux-07
```

Override concurrency only when target and registry capacity permits it:

```bash
python scripts/story_39_7_deploy.py preflight \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --concurrency 5
```

## Browser testing

`e2e.mode: local` runs against a loopback port on the control computer.
`e2e.mode: ssh-tunnel` opens a temporary local forward to the remote target's
loopback listener. This satisfies the repository's loopback-only Playwright
policy without exposing the pre-production HTTP port.

Every concurrent SSH target needs a unique `local_port`. The example reserves
`13001` through `13009`. `headed: true` opens visible external Microsoft Edge
windows on the control computer because the example sets `browser_channel:
msedge`. Remove `browser_channel` to use bundled Playwright Chromium, or set
`headed: false` for a non-interactive CI runner.

Concurrent targets use separate temporary authentication-state and trace
directories. Those directories are deleted after each run so bearer tokens do
not become deployment artifacts. Only the target-specific Playwright JSON
result is retained under `report_directory`.

The `test` action is intentionally first-attempt only: one worker, zero
retries, and a JSON result artifact. A failed run remains failed and is not
converted into a qualifying Story 39.7 burn-in run by rerunning this command.

## Reports and failure handling

Each action writes a UTC-named JSON report under `report_directory`. Reports
contain candidate identity, image references, configuration hashes, service
state, and check outcomes. They contain neither rendered Compose YAML nor
environment values. Known secret values and URL credentials are redacted from
command errors.
Lifecycle failures preserve completed checks in the action report and record a
redacted failure stage in the pending journal.

The controller isolates targets. If target 4 fails, targets 1-3 and 5-10 keep
running. The process exits non-zero when any selected target fails. Correct
the target and rerun only that name. A `status` result can be `partial`; inspect
all three independent checks instead of treating a missing application as a
missing database or journal.

For post-deployment diagnosis, run `status`, then `verify`, then `test` for the
affected target. Fix source code in the repository, build and publish a new
immutable candidate, update the external target environment file, and use
`upgrade`. Do not edit running containers: those changes cannot be audited or
rolled back from the lifecycle state. A failed bootstrap preserves its data,
phase checkpoint, and evidence; rerun `bootstrap` to resume. Inspect the JSON
report before any operator-reviewed cleanup.

Reports always include:

```json
{
  "annual_slo_proven": false,
  "release_gate": "BLOCKED"
}
```

These reports support deployment diagnosis. They do not replace the raw
availability, provenance, alert, incident, and 12-run evidence required by
the independent Story 39.7 validator.

## Recommended expansion

For regular deployment beyond ten environments, keep this script as the
validated target executor and invoke it from a CI runner or an operations
orchestrator. Store environment files in a secret manager, materialize them
only for the job, run `plan -> preflight -> deploy -> test`, upload the JSON
reports, and remove the materialized secret files. Preserve approval gates for
pre-production and production rather than granting a CI runner unrestricted
access to every Docker engine.
