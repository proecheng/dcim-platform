"""Story 39.1 WebSocket 服务端授权测试。"""

import time
from contextlib import asynccontextmanager

import pytest
from fastapi.routing import APIWebSocketRoute
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect, WebSocketState
from sqlalchemy import select, update

import app.main as main_module
from app.core.authorization import discover_broadcast_producers, load_authorization_inventory
from app.main import app, verify_websocket_token
from app.models.spatial import Site
from app.models.user import User, UserSession
from app.services.websocket import (
    ConnectionContext,
    ConnectionManager,
    WebSocketAuthorizationContext,
    ws_manager,
)
from tests.conftest import auth_headers


class FakeWebSocket:
    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.sent: list[dict] = []
        self.closed: list[tuple[int, str]] = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self, code=1000, reason=""):
        self.closed.append((code, reason))
        self.client_state = WebSocketState.DISCONNECTED


class FailingWebSocket(FakeWebSocket):
    async def send_json(self, message):
        raise RuntimeError("socket closed")


def _context(
    websocket,
    *,
    user_id,
    jti,
    role="viewer",
    sites=frozenset({1}),
    channel="realtime",
    expires_at=None,
):
    return ConnectionContext(
        websocket=websocket,
        user_id=user_id,
        jti=jti,
        role=role,
        allowed_site_ids=sites,
        channel=channel,
        expires_at=expires_at or time.time() + 3600,
    )


@pytest.mark.asyncio
async def test_site_broadcast_only_reaches_authorized_connections():
    manager = ConnectionManager(revalidate_before_send=False)
    socket_a, socket_b, socket_admin = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    await manager.connect(_context(socket_a, user_id=1, jti="a", sites=frozenset({10})), already_accepted=True)
    await manager.connect(_context(socket_b, user_id=2, jti="b", sites=frozenset({20})), already_accepted=True)
    await manager.connect(
        _context(socket_admin, user_id=3, jti="admin", role="admin", sites=None), already_accepted=True
    )

    sent = await manager.broadcast_realtime({"point_id": 7, "value": 42}, site_id=10)

    assert sent == 2
    assert len(socket_a.sent) == 1
    assert socket_b.sent == []
    assert len(socket_admin.sent) == 1


@pytest.mark.asyncio
async def test_realtime_batch_preserves_site_and_point_filters():
    manager = ConnectionManager(revalidate_before_send=False)
    filtered_socket, other_site_socket, admin_socket = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    filtered_context = _context(filtered_socket, user_id=1, jti="filtered", sites=frozenset({10}))
    manager.update_subscription(
        filtered_context,
        {"action": "subscribe", "filters": {"site_ids": [10], "point_ids": [7]}},
    )
    await manager.connect(filtered_context, already_accepted=True)
    await manager.connect(
        _context(other_site_socket, user_id=2, jti="other", sites=frozenset({20})), already_accepted=True
    )
    await manager.connect(
        _context(admin_socket, user_id=3, jti="admin-batch", role="admin", sites=None), already_accepted=True
    )

    sent = await manager.broadcast_realtime(
        [{"point_id": 7, "value": 42}, {"point_id": 8, "value": 84}],
        site_id=10,
    )

    assert sent == 2
    assert filtered_socket.sent == [
        {"type": "realtime_batch", "data": [{"point_id": 7, "value": 42}]}
    ]
    assert other_site_socket.sent == []
    assert admin_socket.sent == [
        {
            "type": "realtime_batch",
            "data": [{"point_id": 7, "value": 42}, {"point_id": 8, "value": 84}],
        }
    ]


@pytest.mark.asyncio
async def test_site_broadcast_without_trusted_site_is_rejected():
    manager = ConnectionManager(revalidate_before_send=False)
    socket = FakeWebSocket()
    await manager.connect(_context(socket, user_id=1, jti="a"), already_accepted=True)

    sent = await manager.broadcast_realtime({"point_id": 7, "site_id": 1, "value": 42})

    assert sent == 0
    assert socket.sent == []


@pytest.mark.asyncio
async def test_role_filter_is_enforced_by_server():
    manager = ConnectionManager(revalidate_before_send=False)
    viewer, operator = FakeWebSocket(), FakeWebSocket()
    await manager.connect(
        _context(viewer, user_id=1, jti="viewer", role="viewer", channel="alarms"), already_accepted=True
    )
    await manager.connect(
        _context(operator, user_id=2, jti="operator", role="operator", channel="alarms"), already_accepted=True
    )

    sent = await manager.broadcast_diagnosis(
        "diagnosis_alert", {"device_id": 4}, target_roles=["operator", "admin"], site_id=1
    )

    assert sent == 1
    assert viewer.sent == []
    assert len(operator.sent) == 1


@pytest.mark.asyncio
async def test_subscription_cannot_expand_site_or_channel_scope():
    manager = ConnectionManager(revalidate_before_send=False)
    socket = FakeWebSocket()
    context = _context(socket, user_id=1, jti="a", sites=frozenset({10}))
    await manager.connect(context, already_accepted=True)

    with pytest.raises(ValueError):
        manager.update_subscription(context, {"action": "subscribe", "filters": {"site_ids": [20]}})
    with pytest.raises(ValueError):
        manager.update_subscription(context, {"action": "subscribe", "channels": ["alarms"]})


@pytest.mark.asyncio
async def test_subscription_filters_point_area_alarm_level_and_site():
    manager = ConnectionManager(revalidate_before_send=False)
    socket = FakeWebSocket()
    context = _context(socket, user_id=1, jti="a", sites=frozenset({10}), channel="alarms")
    await manager.connect(context, already_accepted=True)
    manager.update_subscription(
        context,
        {
            "action": "subscribe",
            "filters": {
                "site_ids": [10],
                "point_ids": [7],
                "area_codes": ["A1"],
                "alarm_levels": ["critical"],
            },
        },
    )

    matching = {"point_id": 7, "area_code": "A1", "alarm_level": "critical"}
    assert await manager.broadcast_alarm(matching, site_id=10) == 1
    assert await manager.broadcast_alarm({**matching, "point_id": 8}, site_id=10) == 0
    assert await manager.broadcast_alarm({**matching, "area_code": "B1"}, site_id=10) == 0
    assert await manager.broadcast_alarm({**matching, "alarm_level": "major"}, site_id=10) == 0
    assert await manager.broadcast_alarm(matching, site_id=20) == 0
    assert len(socket.sent) == 1


@pytest.mark.asyncio
async def test_site_subscription_does_not_hide_approved_global_message():
    manager = ConnectionManager(revalidate_before_send=False)
    socket = FakeWebSocket()
    context = _context(socket, user_id=1, jti="a", sites=frozenset({10}), channel="system")
    await manager.connect(context, already_accepted=True)
    manager.update_subscription(context, {"action": "subscribe", "filters": {"site_ids": [10]}})

    assert await manager.broadcast_system({"status": "maintenance"}, global_message=True) == 1
    assert socket.sent == [{"type": "system", "data": {"status": "maintenance"}}]


@pytest.mark.asyncio
async def test_expired_token_context_is_closed_before_business_send():
    manager = ConnectionManager(revalidate_before_send=False)
    socket = FakeWebSocket()
    context = _context(socket, user_id=1, jti="expired", expires_at=time.time() - 1)
    await manager.connect(context, already_accepted=True)

    assert await manager.broadcast_realtime({"point_id": 7}, site_id=1) == 0
    assert socket.sent == []
    assert socket.closed == [(4001, "Unauthorized")]
    assert manager.total_connections == 0


@pytest.mark.parametrize(
    "message",
    [
        None,
        {"action": "unknown"},
        {"action": "subscribe", "filters": []},
        {"action": "subscribe", "filters": {"unknown": []}},
        {"action": "subscribe", "filters": {"site_ids": [True]}},
        {"action": "subscribe", "filters": {"point_ids": ["7"]}},
        {"action": "subscribe", "filters": {"area_codes": [7]}},
        {"action": "subscribe", "channels": "realtime"},
    ],
)
def test_malformed_subscription_messages_are_rejected(message):
    manager = ConnectionManager(revalidate_before_send=False)
    context = _context(FakeWebSocket(), user_id=1, jti="a")

    with pytest.raises(ValueError):
        if isinstance(message, dict) and message.get("action") in {"subscribe", "unsubscribe"}:
            manager.update_subscription(context, message)
        else:
            manager.update_subscription(context, message or {})


@pytest.mark.asyncio
async def test_failed_send_removes_connection_from_snapshot():
    manager = ConnectionManager(revalidate_before_send=False)
    socket = FailingWebSocket()
    context = _context(socket, user_id=1, jti="a")
    await manager.connect(context, already_accepted=True)

    assert await manager.broadcast_realtime({"point_id": 7}, site_id=1) == 0
    assert manager.total_connections == 0
    assert socket.closed == [(1000, "send failed")]


@pytest.mark.asyncio
async def test_revalidation_revocation_does_not_send_from_stale_snapshot(monkeypatch):
    manager = ConnectionManager()
    socket = FakeWebSocket()
    context = _context(socket, user_id=1, jti="revoked")
    context.last_validated = time.monotonic() - 60
    await manager.connect(context, already_accepted=True)

    async def revoke(contexts, *, force=False):
        await manager._close_contexts(contexts, 4001, "Unauthorized")
        return []

    monkeypatch.setattr(manager, "_revalidate_contexts", revoke)

    assert await manager.broadcast_realtime({"point_id": 7}, site_id=1) == 0
    assert socket.sent == []
    assert socket.closed == [(4001, "Unauthorized")]


def test_inventory_producers_declare_explicit_runtime_scope():
    inventory = load_authorization_inventory()
    policies = {item["key"]: item for item in inventory["websocket"]["producers"]}

    for producer in discover_broadcast_producers():
        policy = policies[producer["key"]]
        if policy["scope"] == "SITE":
            assert producer["has_site_id"], producer["key"]
        elif policy["scope"] == "GLOBAL":
            assert producer["global_message_is_true"], producer["key"]


@pytest.mark.asyncio
async def test_jti_invalidation_closes_and_removes_connection():
    manager = ConnectionManager(revalidate_before_send=False)
    socket = FakeWebSocket()
    context = _context(socket, user_id=1, jti="revoked")
    await manager.connect(context, already_accepted=True)

    closed = await manager.invalidate_jti("revoked")

    assert closed == 1
    assert socket.closed == [(4001, "Unauthorized")]
    assert manager.total_connections == 0


@pytest.mark.asyncio
async def test_websocket_token_returns_full_active_session_context(async_db, operator_user):
    user, token = operator_user

    context = await verify_websocket_token(token, "realtime", db=async_db)

    assert context is not None
    assert context.user_id == user.id
    assert context.jti
    assert context.role == "operator"
    assert context.allowed_site_ids == frozenset()
    assert context.channel == "realtime"
    assert context.expires_at > time.time()


def test_websocket_routes_do_not_accept_token_query_parameter():
    routes = [route for route in app.routes if isinstance(route, APIWebSocketRoute)]

    assert len(routes) == 3
    assert all(not route.dependant.query_params for route in routes)


def _authorization(channel: str = "realtime") -> WebSocketAuthorizationContext:
    return WebSocketAuthorizationContext(
        user_id=1,
        jti="active-jti",
        role="viewer",
        allowed_site_ids=frozenset({10}),
        channel=channel,
        username="viewer",
        expires_at=time.time() + 3600,
    )


def test_websocket_route_authenticates_before_processing_messages(monkeypatch):
    async def verify(token, channel, *, db=None):
        assert token == "opaque-token"
        return _authorization(channel)

    monkeypatch.setattr(main_module, "verify_websocket_token", verify)
    client = TestClient(app)

    with client.websocket_connect("/ws/realtime") as websocket:
        websocket.send_json({"action": "authenticate", "token": "opaque-token"})
        assert websocket.receive_json() == {"type": "authenticated"}
        websocket.send_json({"action": "ping"})
        assert websocket.receive_json() == {"type": "pong"}


@pytest.mark.parametrize(
    "frame",
    [
        None,
        {},
        {"action": "subscribe", "filters": {}},
        {"action": "authenticate"},
        {"action": "authenticate", "token": 123},
    ],
)
def test_websocket_route_rejects_malformed_first_frame(frame):
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/realtime") as websocket:
            websocket.send_json(frame)
            websocket.receive_json()

    assert exc_info.value.code == 4001


def test_websocket_route_rejects_failed_authentication(monkeypatch):
    async def reject(token, channel, *, db=None):
        return None

    monkeypatch.setattr(main_module, "verify_websocket_token", reject)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/alarms") as websocket:
            websocket.send_json({"action": "authenticate", "token": "invalid"})
            websocket.receive_json()

    assert exc_info.value.code == 4001


def test_websocket_route_rejects_authentication_timeout(monkeypatch):
    monkeypatch.setattr(main_module, "WS_AUTH_TIMEOUT_SECONDS", 0.01)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/system") as websocket:
            websocket.receive_json()

    assert exc_info.value.code == 4001


@pytest.mark.parametrize(
    "message",
    [
        {"action": "authenticate", "token": "duplicate"},
        {"action": "unknown"},
        {"action": "subscribe", "filters": {"site_ids": [20]}},
        {"action": "subscribe", "channels": ["alarms"]},
    ],
)
def test_websocket_route_rejects_post_auth_scope_violations(monkeypatch, message):
    async def verify(token, channel, *, db=None):
        return _authorization(channel)

    monkeypatch.setattr(main_module, "verify_websocket_token", verify)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/realtime") as websocket:
            websocket.send_json({"action": "authenticate", "token": "opaque-token"})
            assert websocket.receive_json() == {"type": "authenticated"}
            websocket.send_json(message)
            websocket.receive_json()

    assert exc_info.value.code == 4001


@pytest.mark.asyncio
async def test_logout_commit_invalidates_current_jti(client, async_db, operator_user):
    user, token = operator_user
    authorization = await verify_websocket_token(token, "realtime", db=async_db)
    assert authorization is not None
    socket = FakeWebSocket()
    context = ConnectionContext(
        websocket=socket,
        user_id=user.id,
        jti=authorization.jti,
        role=user.role,
        allowed_site_ids=frozenset(),
        channel="realtime",
        expires_at=authorization.expires_at,
        username=user.username,
    )
    await ws_manager.connect(context, already_accepted=True)
    try:
        response = await client.post("/api/v1/auth/logout", headers=auth_headers(token))

        assert response.status_code == 200
        assert socket.closed == [(4001, "Unauthorized")]
    finally:
        ws_manager.disconnect(context)


@pytest.mark.asyncio
async def test_site_replacement_commit_invalidates_target_user(client, async_db, admin_user, operator_user):
    _, admin_token = admin_user
    target, target_token = operator_user
    site = Site(site_code="WS-REVOKE", site_name="撤销站点")
    async_db.add(site)
    await async_db.flush()
    authorization = await verify_websocket_token(target_token, "realtime", db=async_db)
    assert authorization is not None
    socket = FakeWebSocket()
    context = ConnectionContext(
        websocket=socket,
        user_id=target.id,
        jti=authorization.jti,
        role=target.role,
        allowed_site_ids=frozenset(),
        channel="realtime",
        expires_at=authorization.expires_at,
        username=target.username,
    )
    await ws_manager.connect(context, already_accepted=True)
    try:
        response = await client.put(
            f"/api/v1/users/{target.id}/sites",
            headers=auth_headers(admin_token),
            json={"site_ids": [site.id]},
        )

        assert response.status_code == 200
        assert socket.closed == [(4001, "Unauthorized")]
    finally:
        ws_manager.disconnect(context)


@pytest.mark.asyncio
async def test_broadcast_revalidation_blocks_revoked_session(async_db, operator_user):
    user, token = operator_user
    authorization = await verify_websocket_token(token, "realtime", db=async_db)
    assert authorization is not None

    @asynccontextmanager
    async def test_session_factory():
        yield async_db

    manager = ConnectionManager(session_factory=test_session_factory)
    socket = FakeWebSocket()
    context = ConnectionContext(
        websocket=socket,
        user_id=user.id,
        jti=authorization.jti,
        role=user.role,
        allowed_site_ids=frozenset(),
        channel="realtime",
        expires_at=authorization.expires_at,
        username=user.username,
    )
    await manager.connect(context, already_accepted=True)
    await async_db.execute(
        update(UserSession).where(UserSession.token_jti == authorization.jti).values(is_active=False)
    )
    await async_db.flush()

    assert await manager.broadcast_realtime({"point_id": 7}, site_id=10) == 0
    assert socket.sent == []
    assert socket.closed == [(4001, "Unauthorized")]


@pytest.mark.asyncio
async def test_concurrent_session_eviction_invalidates_old_connection(client, async_db, operator_user):
    from app.api.v1.auth import login_limiter

    login_limiter.attempts.clear()
    user, token = operator_user
    authorization = await verify_websocket_token(token, "realtime", db=async_db)
    assert authorization is not None
    socket = FakeWebSocket()
    context = ConnectionContext(
        websocket=socket,
        user_id=user.id,
        jti=authorization.jti,
        role=user.role,
        allowed_site_ids=frozenset(),
        channel="realtime",
        expires_at=authorization.expires_at,
        username=user.username,
    )
    await ws_manager.connect(context, already_accepted=True)
    try:
        for _ in range(3):
            response = await client.post(
                "/api/v1/auth/login",
                data={"username": user.username, "password": "test_secure_pwd_!@#"},
            )
            assert response.status_code == 200

        assert socket.closed == [(4001, "Unauthorized")]
    finally:
        ws_manager.disconnect(context)
        login_limiter.attempts.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["role", "disable", "delete"])
async def test_user_authorization_mutations_invalidate_connections(
    mutation, client, async_db, admin_user, operator_user
):
    _, admin_token = admin_user
    target, target_token = operator_user
    authorization = await verify_websocket_token(target_token, "realtime", db=async_db)
    assert authorization is not None
    socket = FakeWebSocket()
    context = ConnectionContext(
        websocket=socket,
        user_id=target.id,
        jti=authorization.jti,
        role=target.role,
        allowed_site_ids=frozenset(),
        channel="realtime",
        expires_at=authorization.expires_at,
        username=target.username,
    )
    await ws_manager.connect(context, already_accepted=True)
    try:
        if mutation == "role":
            response = await client.put(
                f"/api/v1/users/{target.id}", headers=auth_headers(admin_token), json={"role": "viewer"}
            )
        elif mutation == "disable":
            response = await client.put(
                f"/api/v1/users/{target.id}/status?is_active=false", headers=auth_headers(admin_token)
            )
        else:
            response = await client.delete(f"/api/v1/users/{target.id}", headers=auth_headers(admin_token))

        assert response.status_code == 200
        assert socket.closed == [(4001, "Unauthorized")]
    finally:
        ws_manager.disconnect(context)


@pytest.mark.asyncio
async def test_invalidation_failure_does_not_rollback_committed_role_change(
    monkeypatch, caplog, client, async_db, admin_user, operator_user
):
    _, admin_token = admin_user
    target, _ = operator_user

    async def fail_invalidation(user_id):
        raise RuntimeError("notification unavailable")

    monkeypatch.setattr(ws_manager, "invalidate_user", fail_invalidation)
    response = await client.put(
        f"/api/v1/users/{target.id}", headers=auth_headers(admin_token), json={"role": "viewer"}
    )

    assert response.status_code == 200
    updated_role = (await async_db.execute(select(User.role).where(User.id == target.id))).scalar_one()
    assert updated_role == "viewer"
    assert "event=user_authorization_changed" in caplog.text
