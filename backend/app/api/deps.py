"""
API 依赖注入模块
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, AsyncGenerator, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, or_, select
from starlette.requests import HTTPConnection

from ..core.config import get_settings
from ..core.authorization import DEFAULT_INVENTORY_PATH, load_authorization_inventory
from ..core.database import async_session
from ..models.alarm import Alarm
from ..models.asset import Asset, Cabinet
from ..models.cooling import CoolingUnit
from ..models.device import Device
from ..models.gateway import Gateway, OtaTask, OtaTaskGateway
from ..models.point import Point
from ..models.operation import WorkOrder, WorkOrderApproval
from ..models.spatial import Floor, Room, Row
from ..models.topology_config import CoolingZone
from ..models.user import User, UserSession, UserSite
from ..models.video import Camera

logger = logging.getLogger(__name__)
settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUserContext:
    """Identity proven by a JWT and its active server-side session."""

    user: User
    jti: str


@dataclass(frozen=True)
class SiteAccessContext:
    """Request-scoped authorization facts used by site-aware queries."""

    user_id: int
    role: str
    jti: str
    site_ids: Optional[frozenset[int]]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def authenticate_access_token(token: Optional[str], db: AsyncSession) -> AuthenticatedUserContext:
    """Authenticate a JWT against the active session owned by its subject."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        if not isinstance(username, str) or not username or not isinstance(jti, str) or not jti:
            raise credentials_exception
    except JWTError:
        # JWT 签名验证失败 — 记录安全告警
        logger.warning("JWT 签名验证失败，可能存在令牌篡改")
        try:
            from ..models.log import OperationLog

            security_log = OperationLog(
                module="auth", action="jwt_tamper_detected", remark="JWT 签名验证失败，可能存在令牌篡改"
            )
            db.add(security_log)
            await db.commit()
        except Exception:
            pass  # 日志写入失败不影响主流程
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

    session_result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.token_jti == jti,
            UserSession.is_active == True,
        )
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已在其他设备登录或已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUserContext(user=user, jti=jti)


async def get_authenticated_user_context(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUserContext:
    """Return the identity cached by the policy gate, or authenticate directly."""
    identity = getattr(request.state, "authenticated_user_context", None)
    if identity is None:
        identity = await authenticate_access_token(token, db)
        request.state.authenticated_user_context = identity
    return identity


async def get_current_user(context: AuthenticatedUserContext = Depends(get_authenticated_user_context)) -> User:
    """Return the current user after strict active-session authentication."""
    return context.user


async def build_site_access_context(user: User, jti: str, db: AsyncSession) -> SiteAccessContext:
    """Build immutable site authorization facts from trusted database rows."""
    if user.role == "admin":
        site_ids = None
    else:
        result = await db.execute(select(UserSite.site_id).where(UserSite.user_id == user.id))
        site_ids = frozenset(result.scalars().all())
    return SiteAccessContext(user_id=user.id, role=user.role, jti=jti, site_ids=site_ids)


async def get_site_access_context(
    request: Request,
    identity: AuthenticatedUserContext = Depends(get_authenticated_user_context),
    db: AsyncSession = Depends(get_db),
) -> SiteAccessContext:
    """FastAPI dependency for a request-scoped site authorization context."""
    context = getattr(request.state, "site_access_context", None)
    if context is None:
        context = await build_site_access_context(identity.user, identity.jti, db)
        request.state.site_access_context = context
    return context


@lru_cache(maxsize=1)
def _http_policy_index() -> dict[str, dict[str, Any]]:
    inventory = load_authorization_inventory(DEFAULT_INVENTORY_PATH)
    return {item["key"]: item for item in inventory["http"]}


async def enforce_inventory_authorization(
    connection: HTTPConnection,
    db: AsyncSession = Depends(get_db),
) -> None:
    """对 HTTP 路由应用清单中的身份、角色和显式站点策略。"""
    if connection.scope["type"] != "http":
        return

    token = await oauth2_scheme(connection)  # type: ignore[arg-type]
    route = connection.scope.get("route")
    operation = getattr(route, "operation_id", None) or getattr(route, "name", None)
    path = getattr(route, "path", None)
    key = f"{connection.scope['method'].upper()} {path}::{operation}"
    policy = _http_policy_index().get(key)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="授权策略缺失")
    if policy["access"] == "PUBLIC":
        return

    identity = await authenticate_access_token(token, db)
    connection.state.authenticated_user_context = identity
    if identity.user.role not in policy["roles"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

    if policy["access"] not in {"SITE_LIST", "SITE_OBJECT"}:
        return
    context = await build_site_access_context(identity.user, identity.jti, db)
    connection.state.site_access_context = context
    raw_site_id = connection.path_params.get("site_id") or connection.query_params.get("site_id")
    if raw_site_id is not None:
        try:
            site_id = int(raw_site_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="站点 ID 无效") from exc
        require_context_site_access(site_id, context)


def apply_site_scope(statement: Any, site_column: Any, context: SiteAccessContext) -> Any:
    """Constrain a SQLAlchemy statement to the caller's allowed sites."""
    if context.site_ids is None:
        return statement
    return statement.where(site_column.in_(context.site_ids))


def apply_device_site_scope(statement: Any, device_id_column: Any, context: SiteAccessContext) -> Any:
    """通过 Device.site_id 的可信关系约束任意设备关联查询。"""
    if context.site_ids is None:
        return statement
    authorized_device_ids = select(Device.id).where(Device.site_id.in_(context.site_ids))
    return statement.where(device_id_column.in_(authorized_device_ids))


def authorized_point_ids_query(context: SiteAccessContext) -> Any:
    """返回当前请求可访问的点位 ID 查询；管理员返回 None 表示全站。"""
    if context.site_ids is None:
        return None
    return select(Point.id).join(Device, Point.device_id == Device.id).where(Device.site_id.in_(context.site_ids))


def apply_point_site_scope(statement: Any, point_id_column: Any, context: SiteAccessContext) -> Any:
    """通过 Point -> Device 的可信关系约束任意点位关联查询。"""
    authorized_point_ids = authorized_point_ids_query(context)
    if authorized_point_ids is None:
        return statement
    return statement.where(point_id_column.in_(authorized_point_ids))


def apply_cabinet_site_scope(statement: Any, cabinet_id_column: Any, context: SiteAccessContext) -> Any:
    """Constrain cabinet-backed resources through Cabinet -> Row -> Room -> Floor -> Site."""
    if context.site_ids is None:
        return statement
    authorized_cabinet_ids = (
        select(Cabinet.id)
        .join(Row, Cabinet.row_id == Row.id)
        .join(Room, Row.room_id == Room.id)
        .join(Floor, Room.floor_id == Floor.id)
        .where(Floor.site_id.in_(context.site_ids))
    )
    return statement.where(cabinet_id_column.in_(authorized_cabinet_ids))


def authorized_asset_ids_query(context: SiteAccessContext) -> Any:
    """返回通过机柜空间层级解析到授权站点的资产 ID 查询。"""
    if context.site_ids is None:
        return None
    return (
        select(Asset.id)
        .join(Cabinet, Asset.cabinet_id == Cabinet.id)
        .join(Row, Cabinet.row_id == Row.id)
        .join(Room, Row.room_id == Room.id)
        .join(Floor, Room.floor_id == Floor.id)
        .where(Floor.site_id.in_(context.site_ids))
    )


def apply_asset_site_scope(statement: Any, asset_id_column: Any, context: SiteAccessContext) -> Any:
    """通过 Asset -> Cabinet -> Row -> Room -> Floor 约束资产关联查询。"""
    authorized_ids = authorized_asset_ids_query(context)
    if authorized_ids is None:
        return statement
    return statement.where(asset_id_column.in_(authorized_ids))


def authorized_work_order_ids_query(context: SiteAccessContext) -> Any:
    """返回通过持久化设备关系解析到授权站点的工单 ID 查询。"""
    if context.site_ids is None:
        return None
    return (
        select(WorkOrder.id)
        .join(Device, WorkOrder.device_id == Device.id)
        .where(Device.site_id.in_(context.site_ids))
    )


def apply_work_order_site_scope(statement: Any, order_id_column: Any, context: SiteAccessContext) -> Any:
    """通过 WorkOrder -> Device -> Site 约束工单关联查询。"""
    authorized_ids = authorized_work_order_ids_query(context)
    if authorized_ids is None:
        return statement
    return statement.where(order_id_column.in_(authorized_ids))


def apply_work_order_approval_site_scope(
    statement: Any, approval_id_column: Any, context: SiteAccessContext
) -> Any:
    """通过 WorkOrderApproval -> WorkOrder -> Device -> Site 约束审批查询。"""
    if context.site_ids is None:
        return statement
    authorized_approval_ids = (
        select(WorkOrderApproval.id)
        .join(WorkOrder, WorkOrderApproval.order_id == WorkOrder.id)
        .join(Device, WorkOrder.device_id == Device.id)
        .where(Device.site_id.in_(context.site_ids))
    )
    return statement.where(approval_id_column.in_(authorized_approval_ids))


def apply_cooling_unit_site_scope(statement: Any, unit_id_column: Any, context: SiteAccessContext) -> Any:
    """Constrain cooling-unit-backed resources through CoolingUnit -> Device -> Site."""
    if context.site_ids is None:
        return statement
    authorized_unit_ids = (
        select(CoolingUnit.id)
        .join(Device, CoolingUnit.device_id == Device.id)
        .where(Device.site_id.in_(context.site_ids))
    )
    return statement.where(unit_id_column.in_(authorized_unit_ids))


def apply_cooling_zone_site_scope(statement: Any, site_column: Any, context: SiteAccessContext) -> Any:
    """Constrain cooling-zone resources using the zone's persisted trusted site owner."""
    return apply_site_scope(statement, site_column, context)


def authorized_camera_ids_query(context: SiteAccessContext) -> Any:
    """返回所有可信设备/机柜关系均落在授权站点内的摄像头 ID 查询。"""
    if context.site_ids is None:
        return None
    return (
        select(Camera.id)
        .outerjoin(Device, Camera.device_id == Device.id)
        .outerjoin(Cabinet, Camera.cabinet_id == Cabinet.id)
        .outerjoin(Row, Cabinet.row_id == Row.id)
        .outerjoin(Room, Row.room_id == Room.id)
        .outerjoin(Floor, Room.floor_id == Floor.id)
        .where(
            or_(
                and_(
                    Camera.device_id.is_not(None),
                    Device.site_id.in_(context.site_ids),
                    or_(Camera.cabinet_id.is_(None), Floor.site_id.in_(context.site_ids)),
                ),
                and_(
                    Camera.device_id.is_(None),
                    Camera.cabinet_id.is_not(None),
                    Floor.site_id.in_(context.site_ids),
                ),
            )
        )
    )


def apply_camera_site_scope(statement: Any, camera_id_column: Any, context: SiteAccessContext) -> Any:
    """通过 Camera -> Device/Cabinet -> Site 的可信关系约束查询。"""
    authorized_ids = authorized_camera_ids_query(context)
    if authorized_ids is None:
        return statement
    return statement.where(camera_id_column.in_(authorized_ids))


def authorized_ota_task_ids_query(
    context: SiteAccessContext, *, require_resolvable_gateways: bool = False
) -> Any:
    """返回全部目标网关均可解析且落在授权站点内的 OTA 任务 ID 查询。"""
    if context.site_ids is None and not require_resolvable_gateways:
        return None

    target_count = (
        select(func.count(OtaTaskGateway.id))
        .where(OtaTaskGateway.task_id == OtaTask.task_id)
        .correlate(OtaTask)
        .scalar_subquery()
    )
    resolved_count_query = (
        select(func.count(OtaTaskGateway.id))
        .select_from(OtaTaskGateway)
        .join(Gateway, OtaTaskGateway.gateway_id == Gateway.gateway_id)
        .where(OtaTaskGateway.task_id == OtaTask.task_id)
        .correlate(OtaTask)
    )
    if context.site_ids is not None:
        resolved_count_query = resolved_count_query.where(Gateway.site_id.in_(context.site_ids))
    resolved_count = resolved_count_query.scalar_subquery()

    return select(OtaTask.id).where(target_count > 0, resolved_count == target_count)


def apply_ota_task_site_scope(
    statement: Any,
    task_id_column: Any,
    context: SiteAccessContext,
    *,
    require_resolvable_gateways: bool = False,
) -> Any:
    """通过 OtaTaskGateway -> Gateway 的完整目标集合约束 OTA 任务查询。"""
    authorized_ids = authorized_ota_task_ids_query(
        context, require_resolvable_gateways=require_resolvable_gateways
    )
    if authorized_ids is None:
        return statement
    return statement.where(task_id_column.in_(authorized_ids))


def require_context_site_access(
    site_id: Optional[int], context: SiteAccessContext, *, hide_existence: bool = False
) -> Optional[int]:
    """Authorize a trusted site owner using the 403/404 enumeration contract."""
    if context.site_ids is None:
        return site_id
    if site_id is None or site_id not in context.site_ids:
        if hide_existence:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资源不存在")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该站点")
    return site_id


async def resolve_device_site_id(db: AsyncSession, device_id: int) -> Optional[int]:
    """Resolve Device ownership from the database, never from request data."""
    result = await db.execute(select(Device.site_id).where(Device.id == device_id))
    return result.scalar_one_or_none()


async def resolve_point_site_id(db: AsyncSession, point_id: int) -> Optional[int]:
    """Resolve Point ownership through Point -> Device -> Site."""
    result = await db.execute(
        select(Device.site_id).select_from(Point).join(Device, Point.device_id == Device.id).where(Point.id == point_id)
    )
    return result.scalar_one_or_none()


async def resolve_cabinet_site_id(db: AsyncSession, cabinet_id: int) -> Optional[int]:
    """Resolve cabinet ownership through the persisted spatial hierarchy."""
    result = await db.execute(
        select(Floor.site_id)
        .select_from(Cabinet)
        .join(Row, Cabinet.row_id == Row.id)
        .join(Room, Row.room_id == Room.id)
        .join(Floor, Room.floor_id == Floor.id)
        .where(Cabinet.id == cabinet_id)
    )
    return result.scalar_one_or_none()


async def resolve_room_site_id(db: AsyncSession, room_id: int) -> Optional[int]:
    """Resolve room ownership through Room -> Floor -> Site."""
    result = await db.execute(
        select(Floor.site_id).select_from(Room).join(Floor, Room.floor_id == Floor.id).where(Room.id == room_id)
    )
    return result.scalar_one_or_none()


async def get_authorized_device(db: AsyncSession, device_id: int, context: SiteAccessContext) -> Device:
    """Read a device within site scope, hiding foreign and missing IDs identically."""
    query = apply_site_scope(select(Device).where(Device.id == device_id), Device.site_id, context)
    device = (await db.execute(query)).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    return device


async def get_authorized_cabinet(db: AsyncSession, cabinet_id: int, context: SiteAccessContext) -> Cabinet:
    """Read a cabinet through its trusted spatial site relation."""
    query = apply_cabinet_site_scope(select(Cabinet).where(Cabinet.id == cabinet_id), Cabinet.id, context)
    cabinet = (await db.execute(query)).scalar_one_or_none()
    if cabinet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜不存在")
    return cabinet


async def get_authorized_asset(db: AsyncSession, asset_id: int, context: SiteAccessContext) -> Asset:
    """按可信空间层级读取资产，统一隐藏站外、未归属和不存在对象。"""
    query = apply_asset_site_scope(select(Asset).where(Asset.id == asset_id), Asset.id, context)
    asset = (await db.execute(query)).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
    return asset


async def get_authorized_row(db: AsyncSession, row_id: int, context: SiteAccessContext) -> Row:
    """通过 Row -> Room -> Floor -> Site 读取授权机柜行。"""
    query = (
        select(Row)
        .join(Room, Row.room_id == Room.id)
        .join(Floor, Room.floor_id == Floor.id)
        .where(Row.id == row_id)
    )
    query = apply_site_scope(query, Floor.site_id, context)
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机柜行不存在")
    return row


async def get_authorized_work_order(
    db: AsyncSession, order_id: int, context: SiteAccessContext
) -> WorkOrder:
    """按设备站点读取工单，统一隐藏站外、未归属和不存在对象。"""
    query = apply_work_order_site_scope(
        select(WorkOrder).where(WorkOrder.id == order_id), WorkOrder.id, context
    )
    order = (await db.execute(query)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return order


async def get_authorized_work_order_approval(
    db: AsyncSession, approval_id: int, context: SiteAccessContext
) -> WorkOrderApproval:
    """通过工单设备归属读取审批，统一隐藏站外与不存在记录。"""
    query = apply_work_order_approval_site_scope(
        select(WorkOrderApproval).where(WorkOrderApproval.id == approval_id),
        WorkOrderApproval.id,
        context,
    )
    approval = (await db.execute(query)).scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审批记录不存在")
    return approval


async def get_authorized_alarm(db: AsyncSession, alarm_id: int, context: SiteAccessContext) -> Alarm:
    """通过 Alarm -> Point -> Device -> Site 读取授权告警。"""
    query = apply_point_site_scope(select(Alarm).where(Alarm.id == alarm_id), Alarm.point_id, context)
    alarm = (await db.execute(query)).scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    return alarm


async def get_authorized_room(db: AsyncSession, room_id: int, context: SiteAccessContext) -> tuple[Room, int]:
    """Read a room and its trusted site owner in one scoped query."""
    query = (
        select(Room, Floor.site_id)
        .join(Floor, Room.floor_id == Floor.id)
        .where(Room.id == room_id)
    )
    query = apply_site_scope(query, Floor.site_id, context)
    row = (await db.execute(query)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
    return row[0], row[1]


async def get_authorized_cooling_unit(
    db: AsyncSession, unit_id: int, context: SiteAccessContext
) -> CoolingUnit:
    """Read a cooling unit through its trusted device site owner."""
    query = apply_cooling_unit_site_scope(
        select(CoolingUnit).where(CoolingUnit.id == unit_id), CoolingUnit.id, context
    )
    unit = (await db.execute(query)).scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空调不存在")
    return unit


async def get_authorized_cooling_zone(
    db: AsyncSession, zone_id: int, context: SiteAccessContext
) -> CoolingZone:
    """Read a cooling zone by its persisted site owner."""
    query = apply_cooling_zone_site_scope(
        select(CoolingZone).where(CoolingZone.id == zone_id), CoolingZone.site_id, context
    )
    zone = (await db.execute(query)).scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="制冷区域不存在")
    return zone


async def get_authorized_camera(db: AsyncSession, camera_id: int, context: SiteAccessContext) -> Camera:
    """按可信设备或机柜归属读取摄像头，隐藏站外与未归属对象。"""
    query = apply_camera_site_scope(select(Camera).where(Camera.id == camera_id), Camera.id, context)
    camera = (await db.execute(query)).scalar_one_or_none()
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="摄像头不存在")
    return camera


async def get_authorized_gateways(
    db: AsyncSession, gateway_ids: list[int], context: SiteAccessContext
) -> list[Gateway]:
    """在任何批量副作用前解析并授权全部目标网关。"""
    requested_ids = set(gateway_ids)
    query = select(Gateway).where(Gateway.id.in_(requested_ids))
    query = apply_site_scope(query, Gateway.site_id, context)
    gateways = (await db.execute(query)).scalars().all()
    if {gateway.id for gateway in gateways} != requested_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="网关不存在")
    return gateways


async def get_authorized_ota_task(
    db: AsyncSession,
    task_id: str,
    context: SiteAccessContext,
    *,
    require_resolvable_gateways: bool = False,
) -> OtaTask:
    """按完整网关集合读取 OTA 任务，统一隐藏站外与不存在任务。"""
    query = select(OtaTask).where(OtaTask.task_id == task_id)
    query = apply_ota_task_site_scope(
        query,
        OtaTask.id,
        context,
        require_resolvable_gateways=require_resolvable_gateways,
    )
    task = (await db.execute(query)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return task


async def get_authorized_point(db: AsyncSession, point_id: int, context: SiteAccessContext) -> Point:
    """在同一 SQL 中按站点范围读取点位，站外对象与不存在对象统一返回 404。"""
    query = apply_point_site_scope(select(Point).where(Point.id == point_id), Point.id, context)
    point = (await db.execute(query)).scalar_one_or_none()
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="点位不存在")
    return point


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活动用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    return current_user


def require_role(allowed_roles: list[str]):
    """角色权限检查装饰器"""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return current_user

    return role_checker


# 常用权限依赖
require_admin = require_role(["admin"])
require_operator = require_role(["admin", "operator"])
require_viewer = require_role(["admin", "operator", "viewer"])


def require_permission(permission: str):
    """
    细粒度权限检查装饰器

    Args:
        permission: 权限标识，格式: "module:action"
                   例如: "diagnosis:view_advanced"

    Returns:
        权限检查函数
    """

    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        # Admin 拥有所有权限
        if current_user.role == "admin":
            return current_user

        # 定义权限映射表
        permission_map = {
            # 诊断高级功能权限（反事实分析、闭环学习等）
            # Story 26.1 要求: 普通运维（operator）无权访问反事实分析
            "diagnosis:view_advanced": ["admin"],
            "diagnosis:manage_annotations": ["admin", "operator"],
            "diagnosis:manage_fault_trees": ["admin"],
            # 其他模块权限可以在此扩展
        }

        allowed_roles = permission_map.get(permission, [])
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"权限不足: 需要 {permission} 权限")

        return current_user

    return permission_checker


# 预定义常用权限检查器
require_diagnosis_advanced = require_permission("diagnosis:view_advanced")
require_diagnosis_annotations = require_permission("diagnosis:manage_annotations")
require_diagnosis_fault_trees = require_permission("diagnosis:manage_fault_trees")


async def get_user_site_ids(
    context: SiteAccessContext = Depends(get_site_access_context),
) -> Optional[list[int]]:
    """获取用户可访问的站点ID列表。admin 返回 None（不过滤）"""
    if context.site_ids is None:
        return None
    return sorted(context.site_ids)


async def require_site_access(
    site_id: int, context: SiteAccessContext = Depends(get_site_access_context)
) -> int:
    """验证用户对指定站点的访问权限。admin 不限制，其他角色检查 UserSite 关联。"""
    return require_context_site_access(site_id, context)
