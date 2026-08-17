"""WebSocket 连接授权、服务端过滤、心跳与会话撤销。"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import WebSocket
from sqlalchemy import select
from starlette.websockets import WebSocketState

from ..core.database import async_session
from ..models.user import User, UserSession, UserSite

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 10
AUTH_REVALIDATE_INTERVAL = 30
SUPPORTED_CHANNELS = frozenset({"realtime", "alarms", "control", "system", "linkage"})
SUPPORTED_ROLES = frozenset({"admin", "operator", "viewer"})
SUBSCRIPTION_FILTERS = frozenset({"site_ids", "point_ids", "area_codes", "alarm_levels"})
MAX_SUBSCRIPTION_VALUES = 1000


@dataclass(eq=False)
class ConnectionContext:
    """不可变身份事实，以及只能缩小权限范围的客户端订阅条件。"""

    websocket: WebSocket
    user_id: int
    jti: str
    role: str
    allowed_site_ids: Optional[frozenset[int]]
    channel: str
    expires_at: float
    username: Optional[str] = None
    subscriptions: dict[str, frozenset[Any]] = field(default_factory=dict)
    last_validated: float = field(default_factory=time.monotonic)
    is_authorized: bool = True


@dataclass(frozen=True)
class WebSocketAuthorizationContext:
    """连接进入连接池前由服务端建立的授权事实。"""

    user_id: int
    jti: str
    role: str
    allowed_site_ids: Optional[frozenset[int]]
    channel: str
    username: str
    expires_at: float


class ConnectionManager:
    """在每次业务发送前执行批量授权校验的连接管理器。"""

    def __init__(self, *, revalidate_before_send: bool = True, session_factory=async_session):
        self.active_connections: dict[str, list[ConnectionContext]] = {
            channel: [] for channel in sorted(SUPPORTED_CHANNELS)
        }
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._revalidate_before_send = revalidate_before_send
        self._session_factory = session_factory

    async def connect(self, context: ConnectionContext, *, already_accepted: bool = False) -> None:
        if context.channel not in SUPPORTED_CHANNELS:
            raise ValueError("unsupported WebSocket channel")
        if not already_accepted:
            await context.websocket.accept()
        self.active_connections[context.channel].append(context)
        logger.debug(
            "WebSocket connected: channel=%s user_id=%s connections=%d",
            context.channel,
            context.user_id,
            len(self.active_connections[context.channel]),
        )

    def disconnect(self, connection: ConnectionContext | WebSocket, channel: Optional[str] = None) -> None:
        channels = [channel] if channel else list(self.active_connections)
        for current_channel in channels:
            contexts = self.active_connections.get(current_channel, [])
            for context in list(contexts):
                if context is connection or context.websocket is connection:
                    contexts.remove(context)
                    logger.debug(
                        "WebSocket disconnected: channel=%s user_id=%s connections=%d",
                        current_channel,
                        context.user_id,
                        len(contexts),
                    )

    def start_heartbeat(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info(
                "WebSocket heartbeat started (interval=%ds, timeout=%ds)", HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT
            )

    def stop_heartbeat(self) -> None:
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            logger.info("WebSocket heartbeat stopped")

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self._ping_all()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("WebSocket heartbeat failed: %s", exc)
                await asyncio.sleep(5)

    async def _ping_all(self) -> None:
        contexts = [context for connections in self.active_connections.values() for context in list(connections)]
        contexts = await self._revalidate_contexts(contexts)
        dead: list[ConnectionContext] = []
        for context in contexts:
            websocket = context.websocket
            try:
                if websocket.client_state != WebSocketState.CONNECTED:
                    dead.append(context)
                    continue
                await asyncio.wait_for(websocket.send_json({"type": "ping", "ts": time.time()}), HEARTBEAT_TIMEOUT)
            except Exception:
                dead.append(context)
        await self._close_contexts(dead, 1000, "heartbeat timeout")

    @property
    def total_connections(self) -> int:
        return sum(len(connections) for connections in self.active_connections.values())

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        await websocket.send_json(message)

    async def send_to_user(self, user: str | int, message: dict) -> int:
        contexts = [
            context
            for connections in self.active_connections.values()
            for context in list(connections)
            if (isinstance(user, str) and context.username == user) or (type(user) is int and context.user_id == user)
        ]
        contexts = await self._revalidate_contexts(contexts, force=True)
        return await self._send_snapshot(contexts, message)

    def update_subscription(self, context: ConnectionContext, message: dict[str, Any]) -> None:
        if not isinstance(message, dict):
            raise ValueError("WebSocket message must be an object")
        if set(message) - {"action", "type", "channels", "filters"}:
            raise ValueError("unsupported subscription field")
        if message.get("action") and message.get("type") and message["action"] != message["type"]:
            raise ValueError("conflicting subscription action")
        action = message.get("action") or message.get("type")
        if action not in {"subscribe", "unsubscribe"}:
            raise ValueError("unsupported subscription action")
        channels = message.get("channels")
        if channels is not None:
            if not isinstance(channels, list) or set(channels) - {context.channel}:
                raise ValueError("subscription channel exceeds connection scope")

        if action == "unsubscribe":
            if "filters" in message:
                raise ValueError("unsubscribe does not accept filters")
            context.subscriptions.clear()
            return

        filters = message.get("filters", {})
        if not isinstance(filters, dict) or set(filters) - SUBSCRIPTION_FILTERS:
            raise ValueError("unsupported subscription filter")
        narrowed: dict[str, frozenset[Any]] = {}
        for name, values in filters.items():
            if not isinstance(values, list) or len(values) > MAX_SUBSCRIPTION_VALUES:
                raise ValueError("invalid subscription filter values")
            if name in {"site_ids", "point_ids"} and any(type(value) is not int for value in values):
                raise ValueError("invalid numeric subscription filter")
            if name in {"area_codes", "alarm_levels"} and any(not isinstance(value, str) for value in values):
                raise ValueError("invalid text subscription filter")
            narrowed[name] = frozenset(values)

        requested_sites = narrowed.get("site_ids")
        if requested_sites is not None and context.allowed_site_ids is not None:
            if not requested_sites.issubset(context.allowed_site_ids):
                raise ValueError("subscription site exceeds authorization scope")
        context.subscriptions = narrowed

    async def handle_client_message(self, context: ConnectionContext, message: Any) -> None:
        if not isinstance(message, dict):
            raise ValueError("WebSocket message must be an object")
        if message.get("action") and message.get("type") and message["action"] != message["type"]:
            raise ValueError("conflicting WebSocket action")
        action = message.get("action") or message.get("type")
        if action == "ping":
            await context.websocket.send_json({"type": "pong"})
        elif action == "pong":
            return
        elif action in {"subscribe", "unsubscribe"}:
            self.update_subscription(context, message)
            await context.websocket.send_json({"type": f"{action}d"})
        else:
            raise ValueError("unsupported WebSocket action")

    async def broadcast(
        self,
        message: dict,
        channel: str = "realtime",
        *,
        site_id: Optional[int] = None,
        global_message: bool = False,
        target_roles: Optional[list[str]] = None,
    ) -> int:
        if not isinstance(message, dict):
            logger.warning("Rejected malformed WebSocket broadcast: channel=%s", channel)
            return 0
        if channel not in SUPPORTED_CHANNELS:
            logger.warning("Rejected WebSocket broadcast to unknown channel: %s", channel)
            return 0
        if type(global_message) is not bool or (global_message and site_id is not None):
            logger.warning("Rejected conflicting WebSocket broadcast scope: channel=%s", channel)
            return 0
        if not global_message and (type(site_id) is not int or site_id <= 0):
            logger.warning("Rejected unscoped WebSocket broadcast: channel=%s type=%s", channel, message.get("type"))
            return 0
        if target_roles is not None and (
            not isinstance(target_roles, list) or any(role not in SUPPORTED_ROLES for role in target_roles)
        ):
            logger.warning("Rejected WebSocket broadcast with invalid roles: channel=%s", channel)
            return 0

        contexts = await self._revalidate_contexts(list(self.active_connections[channel]), force=True)
        roles = frozenset(target_roles or [])
        eligible = [
            context
            for context in contexts
            if self._can_receive(context, message, site_id=site_id, global_message=global_message, target_roles=roles)
        ]
        return await self._send_snapshot(eligible, message)

    def _can_receive(
        self,
        context: ConnectionContext,
        message: dict,
        *,
        site_id: Optional[int],
        global_message: bool,
        target_roles: frozenset[str],
    ) -> bool:
        if target_roles and context.role not in target_roles:
            return False
        if not global_message and context.allowed_site_ids is not None and site_id not in context.allowed_site_ids:
            return False
        requested_sites = context.subscriptions.get("site_ids")
        if not global_message and requested_sites is not None and site_id not in requested_sites:
            return False
        data = message.get("data") if isinstance(message.get("data"), dict) else message
        for filter_name, data_name in (
            ("point_ids", "point_id"),
            ("area_codes", "area_code"),
            ("alarm_levels", "alarm_level"),
        ):
            allowed = context.subscriptions.get(filter_name)
            if allowed is not None and data.get(data_name) not in allowed:
                return False
        return True

    async def _send_snapshot(self, contexts: list[ConnectionContext], message: dict) -> int:
        dead: list[ConnectionContext] = []
        expired: list[ConnectionContext] = []
        sent = 0
        for context in list(contexts):
            if not context.is_authorized or not self._is_registered(context):
                continue
            if time.time() >= context.expires_at:
                expired.append(context)
                continue
            try:
                await context.websocket.send_json(message)
                sent += 1
            except Exception as exc:
                logger.warning(
                    "WebSocket send failed: channel=%s user_id=%s error=%s", context.channel, context.user_id, exc
                )
                dead.append(context)
        await self._close_contexts(expired, 4001, "Unauthorized")
        await self._close_contexts(dead, 1000, "send failed")
        return sent

    async def _close_contexts(self, contexts: list[ConnectionContext], code: int, reason: str) -> int:
        closed = 0
        for context in list(dict.fromkeys(contexts)):
            context.is_authorized = False
            self.disconnect(context)
            try:
                await context.websocket.close(code=code, reason=reason)
            except Exception as exc:
                log = logger.error if code == 4001 else logger.warning
                log(
                    "WebSocket close failed: event=connection_revocation_failed channel=%s user_id=%s "
                    "jti_suffix=%s code=%s error=%s",
                    context.channel,
                    context.user_id,
                    context.jti[-8:],
                    code,
                    exc,
                    extra={
                        "security_event": "connection_revocation_failed",
                        "user_id": context.user_id,
                        "channel": context.channel,
                        "close_code": code,
                    },
                )
            closed += 1
        return closed

    def _is_registered(self, context: ConnectionContext) -> bool:
        return context in self.active_connections.get(context.channel, [])

    async def invalidate_jti(self, jti: str) -> int:
        contexts = [
            context
            for connections in self.active_connections.values()
            for context in list(connections)
            if context.jti == jti
        ]
        return await self._close_contexts(contexts, 4001, "Unauthorized")

    async def invalidate_user(self, user_id: int) -> int:
        contexts = [
            context
            for connections in self.active_connections.values()
            for context in list(connections)
            if context.user_id == user_id
        ]
        return await self._close_contexts(contexts, 4001, "Unauthorized")

    async def _revalidate_contexts(
        self, contexts: list[ConnectionContext], *, force: bool = False
    ) -> list[ConnectionContext]:
        now = time.monotonic()
        candidates = [context for context in contexts if context.is_authorized and self._is_registered(context)]
        expired = [context for context in candidates if time.time() >= context.expires_at]
        if expired:
            await self._close_contexts(expired, 4001, "Unauthorized")
            candidates = [context for context in candidates if context not in expired]
        if force and not self._revalidate_before_send:
            return candidates
        due = [context for context in candidates if force or now - context.last_validated >= AUTH_REVALIDATE_INTERVAL]
        if not due:
            return candidates
        jtis = {context.jti for context in due}
        try:
            async with self._session_factory() as db:
                result = await db.execute(
                    select(UserSession.token_jti, User.id, User.username, User.role, User.is_active)
                    .join(User, UserSession.user_id == User.id)
                    .where(UserSession.token_jti.in_(jtis), UserSession.is_active == True)  # noqa: E712
                )
                identity_rows = {row[0]: row for row in result.all()}
                user_ids = {row[1] for row in identity_rows.values() if row[4]}
                site_result = await db.execute(
                    select(UserSite.user_id, UserSite.site_id).where(UserSite.user_id.in_(user_ids))
                )
                sites_by_user: dict[int, set[int]] = {user_id: set() for user_id in user_ids}
                for user_id, site_id in site_result.all():
                    sites_by_user[user_id].add(site_id)
        except Exception as exc:
            logger.error(
                "WebSocket authorization revalidation failed: event=authorization_revalidation_failed "
                "connections=%d error=%s",
                len(due),
                exc,
                extra={
                    "security_event": "authorization_revalidation_failed",
                    "connection_count": len(due),
                },
            )
            await self._close_contexts(due, 4001, "Unauthorized")
            return [context for context in candidates if context not in due and context.is_authorized]

        revoked: list[ConnectionContext] = []
        for context in due:
            row = identity_rows.get(context.jti)
            if row is None or not row[4] or row[1] != context.user_id or row[3] != context.role:
                revoked.append(context)
                continue
            current_sites = None if row[3] == "admin" else frozenset(sites_by_user.get(row[1], set()))
            if current_sites != context.allowed_site_ids:
                revoked.append(context)
                continue
            context.last_validated = now
        await self._close_contexts(revoked, 4001, "Unauthorized")
        return [context for context in candidates if context not in revoked and context.is_authorized]

    async def broadcast_realtime(self, point_data: dict | list[dict], *, site_id: Optional[int] = None) -> int:
        if isinstance(point_data, dict):
            return await self.broadcast({"type": "realtime", "data": point_data}, "realtime", site_id=site_id)

        if (
            not isinstance(point_data, list)
            or not point_data
            or any(not isinstance(item, dict) for item in point_data)
            or type(site_id) is not int
            or site_id <= 0
        ):
            logger.warning("Rejected malformed realtime batch broadcast: site_id=%s", site_id)
            return 0

        contexts = await self._revalidate_contexts(list(self.active_connections["realtime"]), force=True)
        sent = 0
        for context in contexts:
            filtered_data = [
                item
                for item in point_data
                if self._can_receive(
                    context,
                    {"data": item},
                    site_id=site_id,
                    global_message=False,
                    target_roles=frozenset(),
                )
            ]
            if filtered_data:
                sent += await self._send_snapshot(
                    [context],
                    {"type": "realtime_batch", "data": filtered_data},
                )
        return sent

    async def broadcast_alarm(
        self, alarm_data: dict, *, site_id: Optional[int] = None, global_message: bool = False
    ) -> int:
        action = alarm_data.get("action", "new")
        data = {key: value for key, value in alarm_data.items() if key != "action"}
        return await self.broadcast(
            {"type": "alarm", "action": action, "data": data},
            "alarms",
            site_id=site_id,
            global_message=global_message,
        )

    async def broadcast_system(
        self, system_data: dict, *, site_id: Optional[int] = None, global_message: bool = False
    ) -> int:
        return await self.broadcast(
            {"type": "system", "data": system_data},
            "system",
            site_id=site_id,
            global_message=global_message,
        )

    async def broadcast_linkage(
        self, linkage_data: dict, *, site_id: Optional[int] = None, global_message: bool = False
    ) -> int:
        return await self.broadcast(
            {"type": "linkage", "data": linkage_data},
            "linkage",
            site_id=site_id,
            global_message=global_message,
        )

    async def broadcast_to_role(
        self,
        message: dict,
        role: str,
        channel: str = "alarms",
        *,
        site_id: Optional[int] = None,
        global_message: bool = False,
    ) -> int:
        return await self.broadcast(
            message,
            channel,
            site_id=site_id,
            global_message=global_message,
            target_roles=[role],
        )

    async def broadcast_diagnosis(
        self,
        msg_type: str,
        data: dict,
        target_roles: Optional[list[str]] = None,
        *,
        site_id: Optional[int] = None,
        global_message: bool = False,
    ) -> int:
        roles = target_roles or ["operator", "admin"]
        message = {"type": msg_type, "target_roles": roles, "data": data}
        return await self.broadcast(
            message,
            "alarms",
            site_id=site_id,
            global_message=global_message,
            target_roles=roles,
        )


ws_manager = ConnectionManager()
