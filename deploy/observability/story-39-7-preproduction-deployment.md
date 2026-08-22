# Story 39.7 Pre-production Deployment Plan

## Purpose and current gate

This plan deploys the fixed Story 39.7 application candidate to a dedicated
Linux pre-production host without rebuilding it. Deployment alone does not
complete Task 5.4. The 72-hour window may start only after the evidence
collector, the absolute E2E schedule, the incident drill procedure, and the
independent validator inputs are installed and verified.

The application candidate remains:

| Item | Fixed value |
| --- | --- |
| Git SHA | `ba1177448958c90e7ab979a3666f8719208c2f8f` |
| Backend image | `ghcr.io/proecheng/dcim-platform/backend@sha256:2024d5d0e953153674a769307dbfccb840cbe47596e3277a8efbb09b17b626fc` |
| Backend image ID | `sha256:2024d5d0e953153674a769307dbfccb840cbe47596e3277a8efbb09b17b626fc` |
| Frontend image | `ghcr.io/proecheng/dcim-platform/frontend@sha256:28f85db1baf1f039614c2e1ea4b4a4a1fc610bfda3c30ce239f7b018f6ee0032` |
| Frontend image ID | `sha256:28f85db1baf1f039614c2e1ea4b4a4a1fc610bfda3c30ce239f7b018f6ee0032` |

The branch containing deployment tooling may advance beyond the candidate
SHA. Do not rebuild the application images from that branch. The candidate
identity is the table above.

For repeated deployment to multiple Windows, Linux, or macOS Docker hosts,
use `story-39-7-fleet-deployment.md` and
`scripts/story_39_7_deploy.py`. The fleet controller applies the image and
health checks in Sections 3-5 concurrently through Docker contexts. This
document remains the detailed procedure and evidence boundary for the real
pre-production target.

## Recommended topology

Use a dedicated Linux VM or physical host with:

- Docker Engine and Docker Compose v2.
- At least 8 CPU cores, 16 GB RAM, and 200 GB SSD storage.
- NTP or chrony synchronized to a trusted UTC source.
- Stable outbound access to GHCR, or an approved offline image-transfer path.
- Persistent Docker volumes on monitored storage.
- No unrelated workloads, automatic image updaters, or unattended restarts.

The application stack joins the Story 39.3 `database-client` network and reads
the Story 39.3 `dr-status` volume. It does not start a second PostgreSQL
instance. This prevents the application from reporting backup status for a
different database than the one it serves.

```text
browser/E2E -> nginx -> backend -> Redis/EMQX
                            |
                            +-> Story 39.3 postgres-writer
                            +-> Story 39.3 dr-status (read-only)
```

Formal independent-failure-domain claims still require the real Story 39.3
topology. A single Docker host is suitable only when the deployment is
explicitly classified as a pre-production mechanism environment.

## Required inputs

Obtain these values before deployment:

1. Pre-production hostname and TLS termination choice.
2. Dedicated Linux host access.
3. Immutable Redis, EMQX, and Story 39.3 PostgreSQL image references.
4. Story 39.3 external database network and status-volume names.
5. Production-shaped secrets and a non-production license.
6. A dedicated E2E administrator account whose data may be created and deleted.
7. An approved incident-drill window and owner.

Never copy `backend/.env`, the repository root `.env`, or development secrets
to this host.

## 1. Check out deployment tooling

```bash
sudo install -d -m 0750 -o "$USER" -g "$USER" /opt/dcim
git clone git@github.com:proecheng/dcim-platform.git /opt/dcim/repository
cd /opt/dcim/repository
git checkout codex/story-39-7-release-candidate
git pull --ff-only origin codex/story-39-7-release-candidate
```

Confirm that the fixed candidate is an ancestor of the deployment branch:

```bash
git merge-base --is-ancestor ba1177448958c90e7ab979a3666f8719208c2f8f HEAD
```

The command must exit `0`.

## 2. Prepare the host-only environment file

```bash
sudo install -d -m 0700 /etc/dcim
sudo cp deploy/observability/story-39-7-preprod.env.example /etc/dcim/story-39-7-preprod.env
sudo chmod 0600 /etc/dcim/story-39-7-preprod.env
sudoedit /etc/dcim/story-39-7-preprod.env
```

Replace every angle-bracket placeholder. Passwords embedded in URLs must be
percent-encoded. `REDIS_PASSWORD` and the password inside `REDIS_URL` must
represent the same value.

Pin Redis and EMQX by registry manifest digest. Floating tags such as
`redis:7-alpine`, `emqx/emqx:5`, or `latest` are not acceptable for the
evidence window.

Keep `PREPROD_BIND_ADDRESS=127.0.0.1` when a host reverse proxy or load
balancer terminates TLS. If direct network access is required, bind to an
approved interface instead of all interfaces and restrict the port with the
host firewall. Do not expose the HTTP listener directly to an untrusted
network.

## 3. Deploy the Story 39.3 database layer first

Follow `deploy/dr/README.md` and start the primary, standby, backup scheduler,
stable database endpoint, and status volume. Use a separately protected DR
environment file.

Before starting the application, both resources must exist:

```bash
docker network inspect dcim-story-39-3-dr_database-client >/dev/null
docker volume inspect dcim-story-39-3-dr_dr-status >/dev/null
```

Verify that `postgres-writer` is healthy from a temporary container attached
to the database network and that the backup scheduler has published current,
valid status files. Do not start the 72-hour clock while backup status is
missing, stale, or failed.

## 4. Pull and verify every image before startup

Load the host environment without printing it:

```bash
set -a
. /etc/dcim/story-39-7-preprod.env
set +a
```

Pull all registry images explicitly. The Compose file uses `pull_policy:
never`, so startup cannot replace them later.

```bash
docker pull "$DCIM_BACKEND_IMAGE"
docker pull "$DCIM_FRONTEND_IMAGE"
docker pull "$DCIM_REDIS_IMAGE"
docker pull "$DCIM_EMQX_IMAGE"
```

Verify application image IDs and OCI revisions:

```bash
verify_candidate_image() {
  image_ref="$1"
  expected_id="$2"
  actual_id="$(docker image inspect "$image_ref" --format '{{.Id}}')"
  revision="$(docker image inspect "$image_ref" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
  test "$actual_id" = "$expected_id"
  test "$revision" = "$CANDIDATE_GIT_SHA"
}

verify_candidate_image "$DCIM_BACKEND_IMAGE" "$DCIM_BACKEND_EXPECTED_ID"
verify_candidate_image "$DCIM_FRONTEND_IMAGE" "$DCIM_FRONTEND_EXPECTED_ID"
```

Any mismatch stops deployment. Do not retag or rebuild an image to make the
check pass.

## 5. Validate and start the application stack

```bash
COMPOSE_FILE=deploy/observability/docker-compose.story-39-7-preprod.yml
ENV_FILE=/etc/dcim/story-39-7-preprod.env

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --images
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --hash '*'
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-build --pull never
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
```

Store the service configuration hashes in the evidence directory. Do not store
the rendered Compose output because it contains secrets.

Wait for all services to become healthy, then verify from inside the backend
container and through Nginx:

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend \
  curl -fsS http://127.0.0.1:8080/api/health
curl -fsS "http://127.0.0.1:${NGINX_PORT}/api/health"
curl -fsS "http://127.0.0.1:${NGINX_PORT}/api/readiness"
```

Log in through the pre-production hostname and verify the authorized endpoint
`GET /api/v1/system/observability`. Database, Redis, MQTT, backup, readiness,
and storage must not be `failed`, `unknown`, or stale.

## 6. Freeze the deployment before burn-in

Record the following without exposing secrets:

- Candidate Git SHA.
- All application and DR image references and image IDs.
- Docker Engine and Compose versions.
- Host identity and UTC synchronization status.
- External network and volume identities.
- Service configuration hashes from `docker compose config --hash '*'`.
- Container IDs, process start timestamps, and restart counts.
- Source hashes required by `story-39-7-contract.yaml`.

Create the pre-production `environment.json` from these values and calculate
its SHA-256 as the new environment fingerprint. The existing fingerprint
`1e1127...` belongs to local Docker Desktop and must not be reused.

The current `scripts/story_39_7_prepare.py` creates a local blocked baseline;
it is not a pre-production collector. Do not start the official window until a
collector is installed that writes one-minute availability and provenance
samples with gaps no greater than five minutes.

## 7. Run the 72-hour evidence window

The repository includes a fail-closed collector and absolute-time scheduler.
Run it only after the fixed candidate has passed lifecycle `upgrade` or
`verify`, and after `scripts/story_39_7_prepare.py --skip-build` has bound the
current immutable image manifests to the evidence baseline:

```bash
python -m scripts.story_39_7_burnin probe \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target workstation

python -m scripts.story_39_7_burnin run \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target workstation
```

On Windows, start the `run` command with `Start-Process -WindowStyle Hidden`
and redirect stdout/stderr to protected files outside the evidence artifacts.
The collector calls the Windows execution-state API while it is alive so the
host does not enter automatic sleep. Keep the interactive user session logged
in because the scheduled Microsoft Edge tests are headed.

Inspect progress without reading secrets:

```bash
python -m scripts.story_39_7_burnin status \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target workstation
```

Request a controlled stop when the candidate must change:

```bash
python -m scripts.story_39_7_burnin stop \
  --inventory deploy/observability/story-39-7-targets.yaml \
  --target workstation
```

The runner samples health, readiness, database, Redis, EMQX, WebSocket, image
identity, container identity, restart counts, and Compose configuration every
minute. It runs the headed zero-retry critical Edge suite on the absolute
schedule below, performs the approved Redis recovery drill at `T+25h`, and
runs the independent validator after `T+72h`. A missed five-minute boundary,
candidate drift, process restart, first-attempt E2E failure, failed incident
recovery, or operator stop leaves the manifest and release gate `BLOCKED`.

Use one absolute UTC schedule. The contract's valid 12-run schedule is:

```text
T+00h, T+06h, T+12h, T+18h, T+24h, T+30h,
T+36h, T+42h, T+48h, T+54h, T+60h, T+72h
```

Every run is first-attempt only. A failure, retry, skipped critical test,
candidate drift, process restart, or disallowed telemetry gap blocks the run
and may require a new window.

The root Playwright configuration rejects non-loopback base URLs. Run the
critical suite on the pre-production host against Nginx on `127.0.0.1`:

```bash
CI=1 \
E2E_BASE_URL="http://127.0.0.1:${NGINX_PORT}" \
E2E_ADMIN_USER="$E2E_ADMIN_USER" \
E2E_ADMIN_PASSWORD="$E2E_ADMIN_PASSWORD" \
PLAYWRIGHT_JSON_OUTPUT_FILE="<absolute-evidence-path>/e2e-<run-id>.json" \
npx playwright test \
  e2e/auth.spec.ts \
  e2e/invalid-detail-pages.spec.ts \
  e2e/authorization-matrix.spec.ts \
  e2e/site-isolation-websocket-authorization.spec.ts \
  --project=chromium --workers=1 --retries=0 --reporter=json
```

Do not use the CI workflow's backend restart step during burn-in. Recovery
probes performed for an incident drill are stored as incident recovery checks,
not as extra scheduled E2E runs and not as retries.

## 8. Incident drill

Use a short, approved Redis dependency interruption because it can produce a
real critical dependency alert without restarting the backend candidate:

1. Record approval, change ID, owner, and UTC start time before the drill.
2. Stop Redis with
   `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" stop redis`.
3. Wait for the critical alert and record its trusted fired timestamp.
4. Start Redis with
   `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" start redis`.
5. Record three consecutive healthy readiness and critical-flow checks.
6. Preserve operator actions, alert lifecycle, monotonic timestamps, and the
   final recovery timestamp in `incidents.json` and `alerts.json`.

Keep the interruption short enough that observed availability remains at least
99.5%. If the drill does not produce the expected alert, do not fabricate an
incident; correct the drill design and restart the evidence window if needed.

## 9. Independent validation and completion

After `T+72h`, update artifact hashes and run the validator in a new process:

```bash
python3 scripts/story_39_7_evidence.py \
  --contract deploy/observability/story-39-7-contract.yaml \
  --manifest _bmad-output/test-artifacts/epic-39/39.7/manifest.yaml \
  --repository-root . \
  --trusted-provenance _bmad-output/test-artifacts/epic-39/39.7/trusted-provenance.json \
  --output _bmad-output/test-artifacts/epic-39/39.7/final-validation.json
```

Only exit code `0` and `"valid": true` permit Task 5.4 to be checked and the
Story status to move to `review`. `annual_slo_proven` must remain `false`.

## Rollback

Before the official window starts, rollback may replace the candidate with a
previous verified digest. After the window starts, any image replacement or
application restart invalidates the fixed-candidate window.

To stop only the application stack while retaining volumes:

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down
```

Do not use `down -v`. Preserve application, observability, DR status, database,
Redis, and EMQX volumes for incident analysis.
