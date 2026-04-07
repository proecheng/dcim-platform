"""
Story 34.3: 通知策略配置 — 策略服务层（时段冲突检测 + 站点权限校验）
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_policy import NotificationPolicy
from app.models.spatial import Site
from app.models.user import UserSite


class NotificationPolicyService:
    @staticmethod
    def _to_minutes(hhmm: str) -> int:
        """将 'HH:MM' 转为分钟数 0~1439"""
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    @staticmethod
    def _segments(start: Optional[str], end: Optional[str]) -> list[tuple[int, int]]:
        """将时段转为分钟区间列表，全天返回 [(0, 1440)]，跨午夜拆为两段"""
        if start is None or end is None:
            return [(0, 1440)]
        s = NotificationPolicyService._to_minutes(start)
        e = NotificationPolicyService._to_minutes(end)
        if s == e:
            raise ValueError(f"时段起止相同({start})，零长度时段无效")
        if s < e:
            return [(s, e)]
        else:  # 跨午夜
            return [(s, 1440), (0, e)]

    @staticmethod
    def time_ranges_overlap(
        start1: Optional[str],
        end1: Optional[str],
        start2: Optional[str],
        end2: Optional[str],
    ) -> bool:
        """判断两个时段是否重叠（支持跨午夜），使用分钟区间比较"""
        segs1 = NotificationPolicyService._segments(start1, end1)
        segs2 = NotificationPolicyService._segments(start2, end2)
        for a in segs1:
            for b in segs2:
                if a[0] < b[1] and b[0] < a[1]:
                    return True
        return False

    @staticmethod
    async def check_time_overlap(
        db: AsyncSession,
        site_id: Optional[int],
        alarm_level: str,
        start: Optional[str],
        end: Optional[str],
        exclude_id: Optional[int] = None,
    ) -> Optional[int]:
        """检测时段冲突，返回冲突策略 ID 或 None（检查所有策略含禁用的）"""
        query = select(NotificationPolicy).where(NotificationPolicy.alarm_level == alarm_level)
        if site_id is None:
            query = query.where(NotificationPolicy.site_id.is_(None))
        else:
            query = query.where(NotificationPolicy.site_id == site_id)
        if exclude_id is not None:
            query = query.where(NotificationPolicy.id != exclude_id)

        result = await db.execute(query)
        policies = result.scalars().all()

        for policy in policies:
            if NotificationPolicyService.time_ranges_overlap(
                start, end, policy.time_range_start, policy.time_range_end
            ):
                return policy.id
        return None

    @staticmethod
    async def validate_site_exists(db: AsyncSession, site_id: int) -> bool:
        """校验 site_id 对应的站点是否存在"""
        result = await db.execute(select(Site).where(Site.id == site_id))
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def validate_user_site_access(db: AsyncSession, site_id: Optional[int], user_ids: list[int]) -> list[int]:
        """校验用户站点权限，返回无权限的 user_id 列表"""
        if site_id is None or not user_ids:
            return []
        result = await db.execute(
            select(UserSite.user_id).where(
                UserSite.site_id == site_id,
                UserSite.user_id.in_(user_ids),
            )
        )
        authorized = {row[0] for row in result.fetchall()}
        return [uid for uid in user_ids if uid not in authorized]
