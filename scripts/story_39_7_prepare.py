#!/usr/bin/env python3
"""Build a fixed Story 39.7 candidate and create a blocked burn-in baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_DIR = ROOT / "_bmad-output" / "test-artifacts" / "epic-39" / "39.7"
DEFAULT_CONTRACT = ROOT / "deploy" / "observability" / "story-39-7-contract.yaml"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class EvidencePreparationError(RuntimeError):
    """Raised when a fixed-image evidence baseline cannot be trusted."""


def _run(
    command: Sequence[str],
    *,
    cwd: Path = ROOT,
    text: bool = True,
) -> str | bytes:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if text else result.stderr.decode(errors="replace").strip()
        raise EvidencePreparationError(f"command failed ({' '.join(command)}): {stderr}")
    return result.stdout


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_json(path: Path, payload: Any) -> str:
    data = _canonical_json(payload)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _write_bytes(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def buildx_command(*, tag: str, context: str, git_sha: str, platform: str = "linux/amd64") -> list[str]:
    """Return the deterministic BuildKit command used for a candidate image."""
    if not GIT_SHA_RE.fullmatch(git_sha):
        raise EvidencePreparationError("git SHA must be a 40-character lowercase commit SHA")
    return [
        "docker",
        "buildx",
        "build",
        "--provenance=false",
        "--platform",
        platform,
        "--annotation",
        f"manifest:org.opencontainers.image.revision={git_sha}",
        "--build-arg",
        f"VCS_REF={git_sha}",
        "--tag",
        tag,
        "--load",
        context,
    ]


def extract_oci_manifest(archive: Path, digest: str, git_sha: str) -> bytes:
    """Extract and verify the content-addressed OCI manifest from an image archive."""
    if not SHA256_RE.fullmatch(digest):
        raise EvidencePreparationError("image digest must be a lowercase sha256 value")
    member_name = f"blobs/sha256/{digest}"
    try:
        with tarfile.open(archive, "r") as image_archive:
            member = image_archive.getmember(member_name)
            source = image_archive.extractfile(member)
            if source is None:
                raise EvidencePreparationError(f"OCI manifest is unreadable: {member_name}")
            data = source.read()
    except (KeyError, OSError, tarfile.TarError) as exc:
        raise EvidencePreparationError(f"OCI manifest is missing from image archive: {member_name}") from exc

    if hashlib.sha256(data).hexdigest() != digest:
        raise EvidencePreparationError("OCI manifest bytes do not match the image digest")
    try:
        manifest = json.loads(data)
    except json.JSONDecodeError as exc:
        raise EvidencePreparationError("OCI manifest is not valid JSON") from exc
    if not isinstance(manifest, Mapping) or manifest.get("schemaVersion") != 2:
        raise EvidencePreparationError("OCI manifest has an unsupported schema")
    supported_media_types = {
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    }
    if manifest.get("mediaType") not in supported_media_types:
        raise EvidencePreparationError("image digest does not identify a single content-addressed image manifest")
    annotations = manifest.get("annotations")
    revision = annotations.get("org.opencontainers.image.revision") if isinstance(annotations, Mapping) else None
    if revision != git_sha:
        raise EvidencePreparationError("OCI manifest revision annotation does not match the candidate git SHA")
    return data


def _git_bytes(repository: Path, *args: str) -> bytes:
    return _run(["git", *args], cwd=repository, text=False)  # type: ignore[return-value]


def _git_text(repository: Path, *args: str) -> str:
    return str(_run(["git", *args], cwd=repository)).strip()


def _assert_candidate_source(repository: Path, git_sha: str) -> None:
    if _git_text(repository, "rev-parse", "HEAD") != git_sha:
        raise EvidencePreparationError("candidate git SHA is not the repository HEAD")
    dirty = _git_text(
        repository,
        "status",
        "--porcelain",
        "--",
        "backend",
        "frontend",
        "docker-compose.yml",
        "deploy/observability",
        "scripts/story_39_7_evidence.py",
        ":(exclude)backend/tests",
    )
    if dirty:
        raise EvidencePreparationError("candidate build inputs contain uncommitted changes")


def _image_digest(tag: str) -> tuple[str, str]:
    output = str(_run(["docker", "image", "inspect", tag, "--format", "{{json .RepoDigests}}"])).strip()
    try:
        repo_digests = json.loads(output)
    except json.JSONDecodeError as exc:
        raise EvidencePreparationError(f"Docker returned invalid RepoDigests for {tag}") from exc
    if not isinstance(repo_digests, list):
        raise EvidencePreparationError(f"Docker did not return RepoDigests for {tag}")
    for reference in repo_digests:
        if isinstance(reference, str) and "@sha256:" in reference:
            digest = reference.rsplit("@sha256:", 1)[-1]
            if SHA256_RE.fullmatch(digest):
                return reference, digest
    raise EvidencePreparationError(f"image {tag} has no immutable repo digest")


def _export_manifest(tag: str, digest: str, git_sha: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="story-39-7-") as temp_dir:
        archive = Path(temp_dir) / "image.tar"
        _run(["docker", "image", "save", "--output", str(archive), tag])
        return extract_oci_manifest(archive, digest, git_sha)


def _docker_value(*args: str) -> str:
    return str(_run(["docker", *args])).strip()


def _source_hashes(repository: Path, git_sha: str, required_paths: Any) -> dict[str, str]:
    if not isinstance(required_paths, list) or not required_paths:
        raise EvidencePreparationError("contract required_source_paths must be a non-empty list")
    hashes: dict[str, str] = {}
    for source_path in required_paths:
        if not isinstance(source_path, str) or Path(source_path).is_absolute() or ".." in Path(source_path).parts:
            raise EvidencePreparationError(f"invalid required source path: {source_path!r}")
        hashes[source_path] = hashlib.sha256(_git_bytes(repository, "show", f"{git_sha}:{source_path}")).hexdigest()
    return hashes


def _configuration_digest(repository: Path, git_sha: str, images: Mapping[str, str]) -> str:
    payload = {
        "docker_compose_sha256": hashlib.sha256(
            _git_bytes(repository, "show", f"{git_sha}:docker-compose.yml")
        ).hexdigest(),
        "images": dict(images),
    }
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def prepare_baseline(args: argparse.Namespace) -> dict[str, Any]:
    repository = Path(args.repository).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    contract_path = Path(args.contract).resolve()
    manifest_path = evidence_dir / "manifest.yaml"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    git_sha = args.git_sha or _git_text(repository, "rev-parse", "HEAD")
    if not GIT_SHA_RE.fullmatch(git_sha):
        raise EvidencePreparationError("candidate git SHA is invalid")
    _assert_candidate_source(repository, git_sha)

    backend_tag = args.backend_tag or f"dcim-backend:story-39-7-{git_sha[:7]}"
    frontend_tag = args.frontend_tag or f"dcim-frontend:story-39-7-{git_sha[:7]}"
    build_commands = [
        buildx_command(tag=backend_tag, context="backend", git_sha=git_sha, platform=args.platform),
        buildx_command(tag=frontend_tag, context="frontend", git_sha=git_sha, platform=args.platform),
    ]
    if not args.skip_build:
        for command in build_commands:
            _run(command, cwd=repository)

    backend_image, backend_digest = _image_digest(backend_tag)
    frontend_image, frontend_digest = _image_digest(frontend_tag)
    backend_manifest = _export_manifest(backend_tag, backend_digest, git_sha)
    frontend_manifest = _export_manifest(frontend_tag, frontend_digest, git_sha)

    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if not isinstance(contract, Mapping):
        raise EvidencePreparationError("Story 39.7 contract must be a YAML object")
    source_hashes = _source_hashes(repository, git_sha, contract.get("required_source_paths"))

    docker_context = _docker_value("context", "show")
    docker_server_version = _docker_value("version", "--format", "{{.Server.Version}}")
    docker_server_id = _docker_value("info", "--format", "{{.ID}}")
    cluster_uid = args.cluster_uid or "sha256:" + hashlib.sha256(
        f"{docker_context}\n{docker_server_id}".encode()
    ).hexdigest()
    deployment_id = args.deployment_id or f"story-39-7-local-{git_sha[:12]}"
    environment = {
        "provider": args.provider,
        "deployment_id": deployment_id,
        "cluster_uid": cluster_uid,
        "configuration_digest": _configuration_digest(
            repository,
            git_sha,
            {"backend": backend_image, "frontend": frontend_image},
        ),
        "docker_context": docker_context,
        "docker_server_version": docker_server_version,
        "candidate_git_sha": git_sha,
        "backend_image": backend_image,
        "frontend_image": frontend_image,
    }

    artifacts: dict[str, dict[str, str]] = {}
    for name in (
        "availability_samples",
        "provenance_samples",
        "e2e_runs",
        "incidents",
        "alerts",
        "maintenance_windows",
    ):
        path = evidence_dir / f"{name}.json"
        artifacts[name] = {"path": path.name, "sha256": _write_json(path, [])}
    source_path = evidence_dir / "source_hashes.json"
    artifacts["source_hashes"] = {"path": source_path.name, "sha256": _write_json(source_path, source_hashes)}
    backend_path = evidence_dir / "backend_image_manifest.json"
    artifacts["backend_image_manifest"] = {
        "path": backend_path.name,
        "sha256": _write_bytes(backend_path, backend_manifest),
    }
    frontend_path = evidence_dir / "frontend_image_manifest.json"
    artifacts["frontend_image_manifest"] = {
        "path": frontend_path.name,
        "sha256": _write_bytes(frontend_path, frontend_manifest),
    }
    environment_path = evidence_dir / "environment.json"
    environment_fingerprint = _write_json(environment_path, environment)
    artifacts["environment"] = {"path": environment_path.name, "sha256": environment_fingerprint}

    if artifacts["backend_image_manifest"]["sha256"] != backend_digest:
        raise EvidencePreparationError("backend manifest artifact is not bound to the Docker image digest")
    if artifacts["frontend_image_manifest"]["sha256"] != frontend_digest:
        raise EvidencePreparationError("frontend manifest artifact is not bound to the Docker image digest")

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise EvidencePreparationError("pending Story 39.7 manifest must be a YAML object")
    manifest.update(
        {
            "status": "blocked",
            "gate_result": "BLOCKED",
            "annual_slo_proven": False,
            "provenance": {
                "git_sha": git_sha,
                "backend_image": backend_image,
                "frontend_image": frontend_image,
                "environment_fingerprint": environment_fingerprint,
            },
            "window": {"started_at_utc": None, "ended_at_utc": None},
            "artifacts": artifacts,
            "commands": [
                " ".join(command) for command in build_commands
            ]
            + ["PENDING: deploy the fixed images and start the 72-hour collector plus critical E2E schedule"],
            "tool_versions": {
                "prepare_script": "1",
                "docker_server": docker_server_version,
                "critical_e2e": "PENDING",
            },
            "known_limits": [
                "This is a local fixed-image baseline, not a completed pre-production burn-in window.",
                "The 72-hour window and 12 spaced first-pass critical E2E runs have not occurred.",
                "No annual availability SLO or production-readiness PASS is claimed.",
            ],
        }
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")

    trusted_provenance = {
        "git_sha": git_sha,
        "backend_image": backend_image,
        "frontend_image": frontend_image,
        "environment_fingerprint": environment_fingerprint,
    }
    trusted_path = evidence_dir / "trusted-provenance.json"
    _write_json(trusted_path, trusted_provenance)
    return {
        "status": "BLOCKED",
        "manifest": str(manifest_path),
        "trusted_provenance": str(trusted_path),
        **trusted_provenance,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--git-sha")
    parser.add_argument("--backend-tag")
    parser.add_argument("--frontend-tag")
    parser.add_argument("--platform", default="linux/amd64")
    parser.add_argument("--provider", default="local-docker-desktop")
    parser.add_argument("--deployment-id")
    parser.add_argument("--cluster-uid")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    try:
        result = prepare_baseline(args)
    except EvidencePreparationError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
