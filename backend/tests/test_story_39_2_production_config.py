"""Story 39.2 production startup configuration tests."""

from copy import deepcopy
import os
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import ProductionConfigurationError, Settings, parse_cors_origins, validate_production_settings
from app.core.security import verify_password
from app.models import User
from app.seeds import minimal_seed


ROOT = Path(__file__).resolve().parents[2]


SAFE_PRODUCTION_CONFIG = {
    "app_env": "production",
    "debug": False,
    "database_url": "postgresql+asyncpg://dcim:correct-horse-battery-staple@db:5432/dcim",
    "secret_key": "jwt-secret-" + "a" * 64,
    "cors_origins": "https://dcim.example.com",
    "seed_enabled": False,
    "demo_enabled": False,
    "simulation_enabled": False,
    "default_admin_password": "Admin-Password-39.2!",
    "license_key": "ENT-1234-5678-9012-3456",
    "VPP_API_KEY": "vpp-key-" + "b" * 40,
    "redis_url": "redis://:redis-password-" + "f" * 32 + "@redis:6379/0",
    "mqtt_enabled": True,
    "mqtt_username": "dcim-service",
    "mqtt_password": "mqtt-password-" + "c" * 32,
    "gateway_secret_key": "gateway-secret-" + "d" * 40,
    "fault_tree_hmac_key": "e" * 40,
}


def make_settings(**overrides) -> Settings:
    values = deepcopy(SAFE_PRODUCTION_CONFIG)
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_safe_production_configuration_passes():
    validate_production_settings(make_settings())


@pytest.mark.parametrize(
    ("override", "field_name"),
    [
        ({"debug": True}, "DEBUG"),
        (
            {"database_url": "mysql+aiomysql://dcim:correct-horse-battery-staple@db:3306/dcim"},
            "DATABASE_URL",
        ),
        ({"database_url": "postgresql+asyncpg://dcim:short@db:5432/dcim"}, "DATABASE_URL"),
        ({"database_url": "postgresql+asyncpg://dcim:dcim_password@db:5432/dcim"}, "DATABASE_URL"),
        ({"database_url": "postgresql+asyncpg://dcim:dcim%5Fpassword@db:5432/dcim"}, "DATABASE_URL"),
        ({"secret_key": "change-this-to-a-secure-random-key"}, "SECRET_KEY"),
        ({"secret_key": "<required-random-secret-at-least-48-characters>"}, "SECRET_KEY"),
        ({"cors_origins": "*"}, "CORS_ORIGINS"),
        ({"cors_origins": "null"}, "CORS_ORIGINS"),
        ({"cors_origins": "http://localhost:3000"}, "CORS_ORIGINS"),
        ({"cors_origins": "http://127.1:3000"}, "CORS_ORIGINS"),
        ({"cors_origins": "http://2130706433:3000"}, "CORS_ORIGINS"),
        ({"seed_enabled": True, "default_admin_password": "admin123"}, "DEFAULT_ADMIN_PASSWORD"),
        ({"demo_enabled": True}, "DEMO_ENABLED"),
        ({"simulation_enabled": True}, "SIMULATION_ENABLED"),
        ({"VPP_API_KEY": "dcim-vpp-default-key-change-me"}, "VPP_API_KEY"),
        ({"license_key": "DEMO-0000-0000-0000"}, "LICENSE_KEY"),
        ({"fault_tree_hmac_key": "your-secret-key-at-least-32-chars-long-change-this"}, "FAULT_TREE_HMAC_KEY"),
        ({"redis_url": "redis://redis:6379/0"}, "REDIS_URL"),
        ({"redis_url": "redis://:short@redis:6379/0"}, "REDIS_URL"),
        ({"redis_url": "redis://:change%2Dthis@redis:6379/0"}, "REDIS_URL"),
        ({"gateway_secret_key": "default-secret-key-change-in-production"}, "GATEWAY_SECRET_KEY"),
        ({"mqtt_username": ""}, "MQTT_USERNAME"),
        ({"mqtt_username": "   "}, "MQTT_USERNAME"),
        ({"mqtt_password": ""}, "MQTT_PASSWORD"),
        ({"mqtt_password": "short"}, "MQTT_PASSWORD"),
    ],
)
def test_unsafe_production_configuration_is_rejected(override, field_name):
    with pytest.raises(ProductionConfigurationError) as error:
        validate_production_settings(make_settings(**override))

    message = str(error.value)
    assert field_name in message
    for value in override.values():
        if isinstance(value, str) and value and value not in {"*", "null", "http://localhost:3000"}:
            assert value not in message


def test_temporary_default_factory_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    values = deepcopy(SAFE_PRODUCTION_CONFIG)
    values.pop("secret_key")
    settings = Settings(_env_file=None, **values)

    with pytest.raises(ProductionConfigurationError, match="SECRET_KEY"):
        validate_production_settings(settings)


def test_development_configuration_remains_supported():
    settings = Settings(_env_file=None, app_env="development", fault_tree_hmac_key="x" * 32)

    validate_production_settings(settings)


@pytest.mark.asyncio
async def test_seed_runner_rejects_direct_call_when_disabled(monkeypatch):
    settings = Settings(_env_file=None, seed_enabled=False, fault_tree_hmac_key="x" * 32)
    create_admin = AsyncMock()
    monkeypatch.setattr(minimal_seed, "settings", settings)
    monkeypatch.setattr(minimal_seed, "_create_default_admin_user", create_admin)

    with pytest.raises(RuntimeError, match="SEED_ENABLED"):
        await minimal_seed.run_minimal_seed()

    create_admin.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_creates_login_capable_admin_idempotently(monkeypatch, async_engine):
    password = "Ci-E2E-Admin-39.2!"
    settings = Settings(
        _env_file=None,
        seed_enabled=True,
        default_admin_password=password,
        fault_tree_hmac_key="x" * 32,
    )
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    monkeypatch.setattr(minimal_seed, "settings", settings)
    monkeypatch.setattr(minimal_seed, "async_session", session_factory)

    await minimal_seed._create_default_admin_user()
    await minimal_seed._create_default_admin_user()

    async with session_factory() as session:
        users = (await session.execute(select(User).where(User.username == "admin"))).scalars().all()

    assert len(users) == 1
    assert users[0].role == "admin"
    assert users[0].is_active is True
    assert verify_password(password, users[0].password_hash)


def test_production_validation_precedes_database_and_background_side_effects():
    main_source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    lifespan_source = main_source[main_source.index("async def lifespan(") :]

    validation_position = lifespan_source.index("validate_production_settings(settings)")
    side_effect_positions = [
        lifespan_source.index("await init_db()"),
        lifespan_source.index("asyncio.create_task("),
        lifespan_source.index("yield"),
    ]

    assert all(validation_position < position for position in side_effect_positions)


def test_production_compose_requires_secrets_and_disables_seed_modes():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    for variable in (
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "SECRET_KEY",
        "CORS_ORIGINS",
        "MQTT_USERNAME",
        "MQTT_PASSWORD",
        "GATEWAY_SECRET_KEY",
        "VPP_API_KEY",
        "LICENSE_KEY",
        "FAULT_TREE_HMAC_KEY",
    ):
        assert f"${{{variable}:?" in compose
        assert f"${{{variable}:-" not in compose

    assert "APP_ENV: production" in compose
    assert 'SEED_ENABLED: "false"' in compose
    assert 'DEMO_ENABLED: "false"' in compose
    assert 'SIMULATION_ENABLED: "false"' in compose


def test_unsafe_production_uvicorn_exits_before_listening_without_secret_leak():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    leaked_secret = "do-not-print-this-production-secret"
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "production",
            "DEBUG": "true",
            "SECRET_KEY": leaked_secret,
            "FAULT_TREE_HMAC_KEY": "x" * 32,
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--lifespan",
            "on",
            "--log-level",
            "warning",
        ],
        cwd=ROOT / "backend",
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )

    assert completed.returncode != 0
    assert "Unsafe production configuration" in completed.stdout
    assert "DEBUG" in completed.stdout
    assert leaked_secret not in completed.stdout
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.5)
        assert client.connect_ex(("127.0.0.1", port)) != 0


@pytest.mark.parametrize(
    "origins",
    [
        "https://good.example.com/path",
        "https://good.example.com/",
        "https://good.example.com:443",
        "https://GOOD.example.com",
        "https://user@good.example.com",
        "ftp://good.example.com",
        "https://good.example.com?q=x",
    ],
)
def test_origin_parser_rejects_non_origin_values(origins):
    with pytest.raises(ValueError):
        parse_cors_origins(origins)
