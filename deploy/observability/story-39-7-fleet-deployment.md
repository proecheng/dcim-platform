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

Every managed target must already have the Story 39.3 database network and
DR status volume described in
`deploy/observability/story-39-7-preproduction-deployment.md`.

## One-time control-computer setup

Install or verify:

- Python 3.11 and PyYAML 6.0.3.
- Docker CLI with Docker Compose v2.
- Node.js 22 and repository dependencies installed with `npm ci`.
- Playwright Chromium installed with `npx playwright install chromium`.
- OpenSSH client and key-based access to remote targets.

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
| `plan` | Validate inventory, env placeholders, immutable digests, and test topology without contacting Docker |
| `preflight` | Require Linux/amd64, Compose, Story 39.3 network and volume, and valid Compose interpolation |
| `deploy` | Pull exact digests, verify image IDs and OCI revision, start with `--no-build --pull never`, then run health checks |
| `verify` | Re-check candidate images, service health, backend health, Nginx proxy health, and readiness |
| `test` | Run `verify`, then execute the first-attempt critical Playwright suite with zero retries |
| `status` | Return a sanitized snapshot of Compose service state |

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
`13001` through `13009`. `headed: true` opens visible Playwright Chromium
windows on the control computer. Set it to `false` for a non-interactive CI
runner.

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

The controller isolates targets. If target 4 fails, targets 1-3 and 5-10 keep
running. The process exits non-zero when any selected target fails. Correct
the target and rerun only that name; `docker compose up` is idempotent.

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
