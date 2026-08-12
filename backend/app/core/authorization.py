"""授权清单与默认拒绝的运行时校验。

版本库中的 YAML 是可审计的唯一事实来源。运行时发现仅用于拒绝漂移，
启动期间绝不自动创建放行策略。
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Route


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_INVENTORY_PATH = BACKEND_ROOT / "authz_inventory.yaml"

ACCESS_TYPES = {"PUBLIC", "GLOBAL", "SITE_LIST", "SITE_OBJECT"}
ROLES = {"admin", "operator", "viewer"}
ACTIONS = {"read", "create", "update", "delete", "execute", "authenticate"}
CHANNELS = {"realtime", "alarms", "control", "system", "linkage"}
FRONTEND_CHANNELS = {"realtime", "alarms", "system", "linkage"}
PRODUCER_SCOPES = {"SITE", "GLOBAL", "USER"}

GLOBAL_ADMIN_RESOURCES = {
    "capacity",
    "demand",
    "dispatch",
    "energy",
    "escalations",
    "execution",
    "floor-map",
    "linkage",
    "monitoring",
    "opportunities",
    "optimization",
    "proposals",
    "regulation",
    "topology",
    "trace",
    "vpp",
}

GLOBAL_ADMIN_PATH_PREFIXES = (
    "/api/v1/asset/inventory",
    "/api/v1/diagnosis/ab-tests",
    "/api/v1/diagnosis/breaker-profiles",
    "/api/v1/diagnosis/chaos",
    "/api/v1/diagnosis/config",
    "/api/v1/diagnosis/hmac-key",
    "/api/v1/diagnosis/misdiagnosis-reports",
    "/api/v1/diagnosis/probability-tuning",
    "/api/v1/diagnosis/reports/misdiagnosis",
    "/api/v1/diagnosis/rules",
    "/api/v1/diagnosis/time-window-tuning",
    "/api/v1/operation/alarm-rules",
    "/api/v1/operation/knowledge",
    "/api/v1/operation/plans",
    "/api/v1/operation/statistics",
    "/api/v1/operation/tasks",
    "/api/v1/ota/firmware",
    "/api/v1/reports",
    "/api/v1/video/nvrs",
)

GLOBAL_ADMIN_PATHS = {
    "/api/v1/diagnosis/annotations/stats",
    "/api/v1/diagnosis/categories",
    "/api/v1/diagnosis/fault-trees",
    "/api/v1/diagnosis/health",
    "/api/v1/diagnosis/sensor-metadata/check-expired-calibrations",
    "/api/v1/diagnosis/training-audit",
    "/api/v1/diagnosis/trend-config",
}

GLOBAL_INCLUSIVE_PREFIXES = ("/api/v1/energy/shift",)

GLOBAL_OPERATOR_PATHS = {
    "/api/v1/energy/shift/opportunities/analyze",
    "/api/v1/energy/shift/opportunities/{opp_id}/convert",
    "/api/v1/energy/shift/plans",
    "/api/v1/energy/shift/plans/{plan_id}",
    "/api/v1/energy/shift/plans/{plan_id}/approve",
    "/api/v1/energy/shift/plans/{plan_id}/execute",
    "/api/v1/energy/shift/plans/{plan_id}/submit",
}

GLOBAL_VIEWER_READ_PREFIXES = ("/api/v1/opportunities",)

GLOBAL_VIEWER_READ_PATHS = {
    "/api/v1/diagnosis/probability-tuning/adjustments",
}

GLOBAL_VIEWER_PATHS = {
    "/api/v1/opportunities/{opportunity_id}/select-devices",
    "/api/v1/opportunities/{opportunity_id}/simulate",
}

SITE_PATH_RESOLVER_PREFIXES = (
    ("/api/v1/diagnosis/analyze", "alarm.point.device.site_id"),
    ("/api/v1/diagnosis/battery-soh", "device.site_id"),
    ("/api/v1/diagnosis/sensor-fusion", "cooling.zone.site_id"),
    ("/api/v1/diagnosis/sensor-metadata", "point.device.site_id"),
    ("/api/v1/diagnosis/trend-warnings", "point.device.site_id"),
    ("/api/v1/operation/alarm-rules/check", "alarm.point.device.site_id"),
    ("/api/v1/reports/device-health", "device.site_id"),
    ("/api/v1/video/cameras/by-alarm", "alarm.point.device.site_id"),
    ("/api/v1/video/cameras/by-device", "device.site_id"),
    ("/api/v1/video/playback/alarm", "alarm.point.device.site_id"),
    ("/api/v1/video/cameras", "camera.device_or_cabinet.site_id"),
    ("/api/v1/video/events", "camera.device_or_cabinet.site_id"),
    ("/api/v1/video/playback/segments", "camera.device_or_cabinet.site_id"),
    ("/api/v1/video/ptz", "camera.device_or_cabinet.site_id"),
    ("/api/v1/video/recording", "camera.device_or_cabinet.site_id"),
)

PUBLIC_PATHS = {
    "/",
    "/api/health",
    "/api/readiness",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/api/v1/auth/login",
}

SITE_RESOURCE_RESOLVERS = {
    "alarms": "alarm.point.device.site_id",
    "asset": "asset.cabinet.site_id",
    "command": "command.device.site_id",
    "cooling": "cooling.device.site_id",
    "data-quality": "point.device.site_id",
    "datasources": "datasource.site_id",
    "devices": "device.site_id",
    "diagnosis": "diagnosis.device.site_id",
    "drift": "point.device.site_id",
    "gateways": "gateway.site_id",
    "history": "point.device.site_id",
    "operation": "workorder.device.site_id",
    "ota": "ota.task.gateway.site_id",
    "points": "point.device.site_id",
    "power": "device.site_id",
    "precool": "cooling.device.site_id",
    "predictive-maintenance": "device.site_id",
    "realtime": "point.device.site_id",
    "reports": "report.site_id",
    "spatial": "spatial.site_id",
    "statistics": "point.device.site_id",
    "thresholds": "threshold.point.device.site_id",
    "topology-config": "topology.device.site_id",
    "video": "video.site_id",
}
OWNERSHIP_RESOLVERS = set(SITE_RESOURCE_RESOLVERS.values()) | {
    "alarm.point.device.site_id",
    "asset.cabinet.site_id",
    "camera.device_or_cabinet.site_id",
    "cooling.zone.site_id",
    "site.id",
    "workorder.device.site_id",
}

PRODUCER_METHOD_CHANNELS = {
    "broadcast": "realtime",
    "broadcast_alarm": "alarms",
    "broadcast_diagnosis": "alarms",
    "broadcast_linkage": "linkage",
    "broadcast_realtime": "realtime",
    "broadcast_system": "system",
    "broadcast_to_role": "alarms",
    "send_personal_message": "direct",
    "send_to_user": "direct",
}


class AuthorizationInventoryError(RuntimeError):
    """Raised when the checked-in authorization inventory is invalid or stale."""


@dataclass(frozen=True)
class InventoryValidationResult:
    http_count: int
    websocket_count: int
    channel_count: int
    producer_count: int


def _http_key(method: str, path: str, operation: str) -> str:
    return f"{method.upper()} {path}::{operation}"


def _websocket_key(path: str, operation: str) -> str:
    return f"{path}::{operation}"


def runtime_http_routes(app: Any) -> dict[str, dict[str, Any]]:
    """Return every mounted HTTP method, including explicit framework routes."""
    routes: dict[str, dict[str, Any]] = {}
    for route in app.routes:
        if isinstance(route, APIWebSocketRoute) or not isinstance(route, (APIRoute, Route)):
            continue
        operation = getattr(route, "operation_id", None) or route.name
        for method in sorted(route.methods or []):
            item = {"method": method.upper(), "path": route.path, "operation": operation}
            key = _http_key(**item)
            if key in routes:
                raise AuthorizationInventoryError(f"duplicate runtime HTTP route: {key}")
            routes[key] = item
    return routes


def runtime_websocket_routes(app: Any) -> dict[str, dict[str, str]]:
    routes: dict[str, dict[str, str]] = {}
    for route in app.routes:
        if not isinstance(route, APIWebSocketRoute):
            continue
        item = {"path": route.path, "operation": route.name}
        key = _websocket_key(**item)
        if key in routes:
            raise AuthorizationInventoryError(f"duplicate runtime WebSocket route: {key}")
        routes[key] = item
    return routes


class _ProducerVisitor(ast.NodeVisitor):
    def __init__(self, source: str):
        self.source = source
        self.scope: list[str] = []
        self.items: list[dict[str, Any]] = []
        self._counts: Counter[str] = Counter()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "ws_manager"
            and func.attr in PRODUCER_METHOD_CHANNELS
        ):
            owner = ".".join(self.scope) or "<module>"
            base = f"{self.source}::{owner}::{func.attr}"
            self._counts[base] += 1
            ordinal = self._counts[base]
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None}
            global_message = keywords.get("global_message")
            self.items.append(
                {
                    "key": f"{base}#{ordinal}",
                    "source": self.source,
                    "owner": owner,
                    "call": func.attr,
                    "channel": PRODUCER_METHOD_CHANNELS[func.attr],
                    "has_site_id": "site_id" in keywords,
                    "global_message_is_true": isinstance(global_message, ast.Constant) and global_message.value is True,
                }
            )
        self.generic_visit(node)


def discover_broadcast_producers(source_root: Path | None = None) -> list[dict[str, Any]]:
    """Discover application call sites that can publish WebSocket data."""
    source_root = source_root or (BACKEND_ROOT / "app")
    producers: list[dict[str, str]] = []
    for path in sorted(source_root.rglob("*.py")):
        if path.name == "websocket.py" and path.parent.name == "services":
            continue
        source = path.relative_to(BACKEND_ROOT).as_posix()
        visitor = _ProducerVisitor(source)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        producers.extend(visitor.items)
    return producers


def load_authorization_inventory(path: Path | str = DEFAULT_INVENTORY_PATH) -> dict[str, Any]:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AuthorizationInventoryError(f"unable to load authorization inventory {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AuthorizationInventoryError("authorization inventory root must be a mapping")
    return data


def _duplicates(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _compare_keys(label: str, expected: set[str], actual: set[str], errors: list[str]) -> None:
    missing = sorted(expected - actual)
    stale = sorted(actual - expected)
    if missing:
        errors.append(f"missing {label}: {missing}")
    if stale:
        errors.append(f"stale {label}: {stale}")


def _validate_common_policy(item: Any, label: str, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{label} must be a mapping")
        return
    access = item.get("access")
    if access not in ACCESS_TYPES:
        errors.append(f"{label} has unknown access type: {access!r}")
    tests = item.get("tests")
    if not isinstance(tests, list) or not tests or not all(isinstance(test, str) and test for test in tests):
        errors.append(f"{label} has missing test mapping")
    if not isinstance(item.get("active_session"), bool):
        errors.append(f"{label} must declare active_session as boolean")
    roles = item.get("roles")
    if not isinstance(roles, list) or any(role not in ROLES for role in roles):
        errors.append(f"{label} has invalid roles")
    if access == "PUBLIC":
        if item.get("active_session") or roles:
            errors.append(f"{label} PUBLIC policy cannot require a session or roles")
    elif not item.get("active_session") or not roles:
        errors.append(f"{label} protected policy must require an active session and roles")
    if access in {"SITE_LIST", "SITE_OBJECT"} and item.get("resolver") not in OWNERSHIP_RESOLVERS:
        errors.append(f"{label} has missing ownership resolver")


def validate_authorization_inventory(
    app: Any,
    *,
    inventory: dict[str, Any] | None = None,
    path: Path | str = DEFAULT_INVENTORY_PATH,
) -> InventoryValidationResult:
    """Validate inventory schema and exact correspondence with runtime/code surfaces."""
    inventory = inventory if inventory is not None else load_authorization_inventory(path)
    errors: list[str] = []

    if inventory.get("version") != 1:
        errors.append("unsupported authorization inventory version")

    runtime_http = runtime_http_routes(app)
    http_items = inventory.get("http", [])
    if not isinstance(http_items, list):
        http_items = []
        errors.append("http inventory must be a list")
    http_keys = [item.get("key") for item in http_items if isinstance(item, dict)]
    duplicate_http = _duplicates(http_keys)
    if duplicate_http:
        errors.append(f"duplicate HTTP policy keys: {duplicate_http}")
    _compare_keys("HTTP policies", set(runtime_http), set(http_keys), errors)
    for index, item in enumerate(http_items):
        label = f"HTTP policy[{index}]"
        _validate_common_policy(item, label, errors)
        if not isinstance(item, dict):
            continue
        expected_key = _http_key(str(item.get("method")), str(item.get("path")), str(item.get("operation")))
        if item.get("key") != expected_key:
            errors.append(f"{label} key does not match method/path/operation")
        if item.get("action") not in ACTIONS:
            errors.append(f"{label} has unknown action")
        if not isinstance(item.get("resource"), str) or not item.get("resource"):
            errors.append(f"{label} has missing resource")

    websocket = inventory.get("websocket", {})
    if not isinstance(websocket, dict):
        websocket = {}
        errors.append("websocket inventory must be a mapping")

    runtime_ws = runtime_websocket_routes(app)
    endpoint_items = websocket.get("endpoints", [])
    if not isinstance(endpoint_items, list):
        endpoint_items = []
        errors.append("WebSocket endpoints must be a list")
    endpoint_keys = [item.get("key") for item in endpoint_items if isinstance(item, dict)]
    duplicate_endpoints = _duplicates(endpoint_keys)
    if duplicate_endpoints:
        errors.append(f"duplicate WebSocket endpoint keys: {duplicate_endpoints}")
    _compare_keys("WebSocket endpoints", set(runtime_ws), set(endpoint_keys), errors)
    for index, item in enumerate(endpoint_items):
        label = f"WebSocket endpoint[{index}]"
        _validate_common_policy(item, label, errors)
        if isinstance(item, dict):
            expected_key = _websocket_key(str(item.get("path")), str(item.get("operation")))
            if item.get("key") != expected_key:
                errors.append(f"{label} key does not match path/operation")

    channel_items = websocket.get("channels", [])
    if not isinstance(channel_items, list):
        channel_items = []
        errors.append("WebSocket channels must be a list")
    channel_names = [item.get("name") for item in channel_items if isinstance(item, dict)]
    duplicate_channels = _duplicates(channel_names)
    if duplicate_channels:
        errors.append(f"duplicate WebSocket channels: {duplicate_channels}")
    _compare_keys("WebSocket channels", CHANNELS, set(channel_names), errors)
    for index, item in enumerate(channel_items):
        label = f"WebSocket channel[{index}]"
        _validate_common_policy(item, label, errors)

    frontend_channels = websocket.get("frontend_channels", [])
    if set(frontend_channels) != FRONTEND_CHANNELS:
        errors.append("frontend WebSocket channels do not match the declared client surface")

    discovered_producers = {item["key"]: item for item in discover_broadcast_producers()}
    producer_items = websocket.get("producers", [])
    if not isinstance(producer_items, list):
        producer_items = []
        errors.append("broadcast producers must be a list")
    producer_keys = [item.get("key") for item in producer_items if isinstance(item, dict)]
    duplicate_producers = _duplicates(producer_keys)
    if duplicate_producers:
        errors.append(f"duplicate broadcast producers: {duplicate_producers}")
    _compare_keys("broadcast producers", set(discovered_producers), set(producer_keys), errors)
    for index, item in enumerate(producer_items):
        label = f"broadcast producer[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be a mapping")
            continue
        if item.get("scope") not in PRODUCER_SCOPES:
            errors.append(f"{label} has unknown scope")
        if item.get("channel") not in CHANNELS | {"direct"}:
            errors.append(f"{label} has unknown channel")
        if item.get("scope") == "SITE" and item.get("resolver") not in OWNERSHIP_RESOLVERS:
            errors.append(f"{label} has missing ownership resolver")
        discovered = discovered_producers.get(item.get("key"))
        if item.get("scope") == "SITE" and discovered and not discovered["has_site_id"]:
            errors.append(f"{label} SITE producer must pass explicit site_id")
        if item.get("scope") == "GLOBAL" and discovered and not discovered["global_message_is_true"]:
            errors.append(f"{label} GLOBAL producer must pass global_message=True")
        tests = item.get("tests")
        if not isinstance(tests, list) or not tests:
            errors.append(f"{label} has missing test mapping")

    if errors:
        raise AuthorizationInventoryError("authorization inventory validation failed:\n- " + "\n- ".join(errors))
    return InventoryValidationResult(
        http_count=len(http_items),
        websocket_count=len(endpoint_items),
        channel_count=len(channel_items),
        producer_count=len(producer_items),
    )


def _action_for_method(method: str, operation: str) -> str:
    if method in {"GET", "HEAD"}:
        return "read"
    if "login" in operation or "refresh" in operation:
        return "authenticate"
    return {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}.get(method, "execute")


def _resource_for_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 3 and parts[:2] == ["api", "v1"]:
        return parts[2]
    if path.startswith("/ws/"):
        return "websocket"
    return "framework"


def _path_is_or_under(path: str, prefix: str) -> bool:
    normalized = path.rstrip("/")
    return normalized == prefix or normalized.startswith(f"{prefix}/")


def _default_roles(method: str) -> list[str]:
    return ["admin", "operator", "viewer"] if method in {"GET", "HEAD"} else ["admin", "operator"]


def _mixed_http_policy(method: str, path: str) -> tuple[str, list[str], str | None] | None:
    normalized = path.rstrip("/")
    if normalized == "/api/v1/command/risk-configs":
        if method in {"GET", "HEAD"}:
            return "GLOBAL", ["admin", "operator", "viewer"], None
        return "GLOBAL", ["admin"], None
    if any(_path_is_or_under(path, prefix) for prefix in GLOBAL_INCLUSIVE_PREFIXES):
        roles = (
            ["admin", "operator"]
            if normalized in GLOBAL_OPERATOR_PATHS and method not in {"GET", "HEAD"}
            else ["admin", "operator", "viewer"]
        )
        return "GLOBAL", roles, None
    if normalized in GLOBAL_VIEWER_PATHS or (
        method in {"GET", "HEAD"}
        and (
            normalized in GLOBAL_VIEWER_READ_PATHS
            or any(_path_is_or_under(path, prefix) for prefix in GLOBAL_VIEWER_READ_PREFIXES)
        )
    ):
        return "GLOBAL", ["admin", "operator", "viewer"], None
    if normalized in GLOBAL_ADMIN_PATHS:
        return "GLOBAL", ["admin"], None

    for prefix, resolver in SITE_PATH_RESOLVER_PREFIXES:
        if _path_is_or_under(path, prefix):
            access = "SITE_OBJECT" if "{" in path or method not in {"GET", "HEAD"} else "SITE_LIST"
            roles = _default_roles(method)
            if normalized == "/api/v1/reports/device-health/calculate":
                access = "SITE_LIST"
            if method in {"GET", "HEAD"} and _path_is_or_under(path, "/api/v1/ota/tasks"):
                roles = ["admin", "operator"]
            if method not in {"GET", "HEAD"} and _path_is_or_under(path, "/api/v1/video/cameras"):
                roles = ["admin"]
            if method == "DELETE" and _path_is_or_under(path, "/api/v1/diagnosis/sensor-metadata"):
                roles = ["admin"]
            return access, roles, resolver

    if any(_path_is_or_under(path, prefix) for prefix in GLOBAL_ADMIN_PATH_PREFIXES):
        return "GLOBAL", ["admin"], None

    if method in {"GET", "HEAD"} and _path_is_or_under(path, "/api/v1/ota/tasks"):
        return (
            "SITE_OBJECT" if "{" in path else "SITE_LIST",
            ["admin", "operator"],
            "ota.task.gateway.site_id",
        )
    if method == "POST" and normalized in {
        "/api/v1/command/approvals/{approval_id}/approve",
        "/api/v1/command/approvals/{approval_id}/reject",
    }:
        return "SITE_OBJECT", ["admin"], "command.device.site_id"
    return None


def build_authorization_inventory(app: Any) -> dict[str, Any]:
    """Build a reviewable candidate inventory; callers must explicitly check it in."""
    http: list[dict[str, Any]] = []
    for key, route in sorted(runtime_http_routes(app).items()):
        method = route["method"]
        path = route["path"]
        operation = route["operation"]
        resource = _resource_for_path(path)
        resolver = SITE_RESOURCE_RESOLVERS.get(resource)
        mixed_policy = _mixed_http_policy(method, path)
        if path in PUBLIC_PATHS:
            access = "PUBLIC"
            roles: list[str] = []
            active_session = False
        elif mixed_policy is not None:
            access, roles, resolver = mixed_policy
            active_session = True
        elif resource in GLOBAL_ADMIN_RESOURCES:
            access = "GLOBAL"
            roles = ["admin"]
            active_session = True
            resolver = None
        elif resolver:
            access = "SITE_OBJECT" if "{" in path or method not in {"GET", "HEAD"} else "SITE_LIST"
            roles = _default_roles(method)
            active_session = True
        else:
            access = "GLOBAL"
            roles = _default_roles(method)
            active_session = True
        http.append(
            {
                "key": key,
                "method": method,
                "path": path,
                "operation": operation,
                "access": access,
                "roles": roles,
                "action": _action_for_method(method, operation),
                "resource": resource,
                "resolver": resolver,
                "active_session": active_session,
                "tests": ["AUTHZ-INVENTORY-HTTP-01"],
            }
        )

    endpoints = []
    for key, route in sorted(runtime_websocket_routes(app).items()):
        endpoints.append(
            {
                "key": key,
                **route,
                "access": "SITE_LIST" if route["path"] != "/ws/system" else "GLOBAL",
                "roles": ["admin", "operator", "viewer"],
                "resolver": "site.id" if route["path"] != "/ws/system" else None,
                "active_session": True,
                "tests": ["AUTHZ-INVENTORY-WS-01"],
            }
        )

    channels = []
    for channel in sorted(CHANNELS):
        global_channel = channel == "system"
        channels.append(
            {
                "name": channel,
                "access": "GLOBAL" if global_channel else "SITE_LIST",
                "roles": ["admin", "operator", "viewer"],
                "resolver": None if global_channel else "site.id",
                "active_session": True,
                "tests": ["AUTHZ-INVENTORY-WS-CHANNEL-01"],
            }
        )

    producers = []
    for producer in discover_broadcast_producers():
        user_targeted = producer["channel"] == "direct"
        producers.append(
            {
                "key": producer["key"],
                "source": producer["source"],
                "owner": producer["owner"],
                "call": producer["call"],
                "channel": producer["channel"],
                "scope": "USER" if user_targeted else "SITE",
                "resolver": None if user_targeted else "site.id",
                "tests": ["AUTHZ-INVENTORY-WS-PRODUCER-01"],
            }
        )

    return {
        "version": 1,
        "http": http,
        "websocket": {
            "endpoints": endpoints,
            "channels": channels,
            "frontend_channels": sorted(FRONTEND_CHANNELS),
            "producers": producers,
        },
    }


def write_authorization_inventory(app: Any, path: Path | str = DEFAULT_INVENTORY_PATH) -> Path:
    """Write a deterministic inventory without discarding reviewed classifications."""
    path = Path(path)
    data = build_authorization_inventory(app)
    if path.exists():
        reviewed = load_authorization_inventory(path)
        reviewed_http = {item["key"]: item for item in reviewed["http"]}
        for item in data["http"]:
            previous = reviewed_http.get(item["key"])
            if previous:
                item["action"] = previous["action"]
                item["tests"] = previous["tests"]

        reviewed_producers = {item["key"]: item for item in reviewed["websocket"]["producers"]}
        for item in data["websocket"]["producers"]:
            previous = reviewed_producers.get(item["key"])
            if previous:
                item["scope"] = previous["scope"]
                item["resolver"] = previous["resolver"]
                item["tests"] = previous["tests"]

    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    return path
