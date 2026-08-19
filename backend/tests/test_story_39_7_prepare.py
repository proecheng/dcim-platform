import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest
import yaml

from scripts.story_39_7_prepare import (
    EvidencePreparationError,
    _run,
    buildx_command,
    extract_oci_manifest,
)


GIT_SHA = "6ff2ead1462a9dc583a59cf092b6043f7c916f59"


def _oci_archive(
    tmp_path: Path,
    *,
    revision: str = GIT_SHA,
    media_type: str = "application/vnd.oci.image.manifest.v1+json",
) -> tuple[Path, str, bytes]:
    payload = json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": media_type,
            "config": {"digest": "sha256:" + "1" * 64},
            "layers": [],
            "annotations": {"org.opencontainers.image.revision": revision},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    archive = tmp_path / "image.tar"
    member_name = f"blobs/sha256/{digest}"
    with tarfile.open(archive, "w") as output:
        info = tarfile.TarInfo(member_name)
        info.size = len(payload)
        output.addfile(info, io.BytesIO(payload))
    return archive, digest, payload


def test_extract_oci_manifest_verifies_digest_and_revision(tmp_path):
    archive, digest, payload = _oci_archive(tmp_path)

    assert extract_oci_manifest(archive, digest, GIT_SHA) == payload


def test_extract_oci_manifest_rejects_revision_drift(tmp_path):
    archive, digest, _ = _oci_archive(tmp_path, revision="0" * 40)

    with pytest.raises(EvidencePreparationError, match="revision"):
        extract_oci_manifest(archive, digest, GIT_SHA)


def test_extract_oci_manifest_accepts_docker_distribution_v2(tmp_path):
    archive, digest, payload = _oci_archive(
        tmp_path,
        media_type="application/vnd.docker.distribution.manifest.v2+json",
    )

    assert extract_oci_manifest(archive, digest, GIT_SHA) == payload


def test_buildx_command_binds_manifest_to_candidate_sha():
    command = buildx_command(
        tag="dcim-backend:story-39-7-test",
        context="backend",
        git_sha=GIT_SHA,
    )

    assert command[:3] == ["docker", "buildx", "build"]
    assert "--provenance=false" in command
    assert f"manifest:org.opencontainers.image.revision={GIT_SHA}" in command
    assert f"VCS_REF={GIT_SHA}" in command
    assert command[-2:] == ["--load", "backend"]


def test_frontend_candidate_uses_supported_node_build_image():
    dockerfile = (Path(__file__).resolve().parents[2] / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:22-alpine AS build" in dockerfile


def test_run_decodes_tool_output_as_utf8(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="build \N{check mark}", stderr="")

    monkeypatch.setattr("scripts.story_39_7_prepare.subprocess.run", fake_run)

    assert _run(["docker", "version"]) == "build \N{check mark}"
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_preproduction_compose_cannot_rebuild_or_replace_candidate_images():
    repository = Path(__file__).resolve().parents[2]
    compose_path = repository / "deploy" / "observability" / "docker-compose.story-39-7-preprod.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]

    assert all("build" not in service for service in services.values())
    assert services["backend"]["image"] == "${DCIM_BACKEND_IMAGE:?DCIM_BACKEND_IMAGE is required}"
    assert services["nginx"]["image"] == "${DCIM_FRONTEND_IMAGE:?DCIM_FRONTEND_IMAGE is required}"
    assert all(service["pull_policy"] == "never" for service in services.values())
    assert "dr-database-client" in services["backend"]["networks"]
    assert compose["networks"]["dr-database-client"]["external"] is True
    assert compose["volumes"]["dr-status"]["external"] is True
