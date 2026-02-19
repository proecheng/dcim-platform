"""
EMQX ACL 管理服务 — 按站点隔离 MQTT Topic 权限

为每个站点生成 ACL 规则，确保网关只能访问所属站点的 Topic 空间。
Topic 格式: dcim/{site_id}/gw/{gw_id}/{type}

支持两种模式:
1. 本地规则表 (mqtt_acl_rules) — 供平台内部鉴权查询
2. EMQX HTTP API 同步 — 将规则推送到 EMQX Broker (可选，优雅降级)
"""
import logging
from typing import Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.gateway import MqttAclRule

logger = logging.getLogger(__name__)
settings = get_settings()


class EmqxAclService:
    """EMQX ACL 管理"""

    # EMQX REST API 基础配置 (可通过环境变量覆盖)
    EMQX_API_URL = getattr(settings, "emqx_api_url", "http://localhost:18083/api/v5")
    EMQX_API_KEY = getattr(settings, "emqx_api_key", "")
    EMQX_API_SECRET = getattr(settings, "emqx_api_secret", "")

    def generate_acl_rules(self, site_id: int, site_code: str) -> list[dict]:
        """为站点生成标准 ACL 规则"""
        return [
            {
                "site_id": site_id,
                "client_id_pattern": f"gw-{site_code}-*",
                "topic_pattern": f"dcim/{site_id}/gw/+/#",
                "action": "all",
                "permission": "allow",
                "description": f"站点 {site_code} 网关完整访问权限",
            },
            {
                "site_id": site_id,
                "client_id_pattern": f"gw-{site_code}-*",
                "topic_pattern": "dcim/+/gw/+/#",
                "action": "all",
                "permission": "deny",
                "description": f"站点 {site_code} 网关禁止跨站点访问",
            },
        ]

    async def on_site_created(
        self, site_id: int, site_code: str, db: AsyncSession
    ) -> list[MqttAclRule]:
        """站点创建后自动配置 ACL 规则"""
        rules_data = self.generate_acl_rules(site_id, site_code)
        created = []
        for rd in rules_data:
            rule = MqttAclRule(**rd)
            db.add(rule)
            created.append(rule)
        await db.flush()

        # 尝试同步到 EMQX (非阻塞，失败不影响主流程)
        await self._try_sync_to_emqx(site_id, site_code)

        logger.info("站点 %s(%d) ACL 规则已创建: %d 条", site_code, site_id, len(created))
        return created

    async def on_site_deleted(self, site_id: int, db: AsyncSession) -> int:
        """站点删除后清理 ACL 规则（本地 + EMQX 远程）"""
        result = await db.execute(
            delete(MqttAclRule).where(MqttAclRule.site_id == site_id)
        )
        count = result.rowcount

        # 尝试清理 EMQX 远程规则 (非阻塞，失败不影响主流程)
        await self._try_delete_from_emqx(site_id)

        logger.info("站点 %d ACL 规则已清理: %d 条", site_id, count)
        return count

    async def get_site_rules(self, site_id: int, db: AsyncSession) -> list[MqttAclRule]:
        """获取站点的 ACL 规则"""
        result = await db.execute(
            select(MqttAclRule).where(MqttAclRule.site_id == site_id)
        )
        return list(result.scalars().all())

    async def refresh_site_rules(
        self, site_id: int, site_code: str, db: AsyncSession
    ) -> list[MqttAclRule]:
        """刷新站点 ACL 规则（删除旧规则，重新生成）"""
        await self.on_site_deleted(site_id, db)
        return await self.on_site_created(site_id, site_code, db)

    async def check_topic_permission(
        self,
        site_id: int,
        client_id: str,
        topic: str,
        action: str,
        db: AsyncSession,
    ) -> bool:
        """检查客户端对 Topic 的访问权限（本地规则表查询）"""
        rules = await self.get_site_rules(site_id, db)
        if not rules:
            # 无规则时默认允许（向后兼容单站点模式）
            return True

        for rule in rules:
            if self._match_client(rule.client_id_pattern, client_id):
                if self._match_topic(rule.topic_pattern, topic):
                    if rule.action in ("all", action):
                        return rule.permission == "allow"
        # 默认拒绝
        return False

    async def _try_sync_to_emqx(self, site_id: int, site_code: str) -> None:
        """尝试将 ACL 规则同步到 EMQX (优雅降级)"""
        if not self.EMQX_API_KEY:
            logger.debug("EMQX API 未配置，跳过 ACL 同步")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # EMQX v5 内置数据库 ACL 规则 API
                url = f"{self.EMQX_API_URL}/authorization/sources/built_in_database/rules/clients"
                rules_payload = [
                    {
                        "clientid": f"gw-{site_code}-*",
                        "rules": [
                            {
                                "action": "all",
                                "permission": "allow",
                                "topic": f"dcim/{site_id}/gw/+/#",
                            }
                        ],
                    }
                ]
                resp = await client.post(
                    url,
                    json=rules_payload,
                    auth=(self.EMQX_API_KEY, self.EMQX_API_SECRET),
                )
                if resp.status_code in (200, 201, 204):
                    logger.info("EMQX ACL 同步成功: 站点 %s", site_code)
                else:
                    logger.warning(
                        "EMQX ACL 同步失败: %d %s", resp.status_code, resp.text
                    )
        except Exception as e:
            logger.warning("EMQX ACL 同步异常(已降级): %s", e)

    async def _try_delete_from_emqx(self, site_id: int) -> None:
        """尝试从 EMQX 删除站点相关 ACL 规则 (优雅降级)"""
        if not self.EMQX_API_KEY:
            logger.debug("EMQX API 未配置，跳过远程 ACL 清理")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 删除该站点的客户端 ACL 规则
                url = f"{self.EMQX_API_URL}/authorization/sources/built_in_database/rules/clients"
                resp = await client.delete(
                    url,
                    params={"clientid_pattern": f"gw-*-site{site_id}-*"},
                    auth=(self.EMQX_API_KEY, self.EMQX_API_SECRET),
                )
                if resp.status_code in (200, 204, 404):
                    logger.info("EMQX ACL 远程清理成功: 站点 %d", site_id)
                else:
                    logger.warning(
                        "EMQX ACL 远程清理失败: %d %s", resp.status_code, resp.text
                    )
        except Exception as e:
            logger.warning("EMQX ACL 远程清理异常(已降级): %s", e)

    @staticmethod
    def _match_client(pattern: Optional[str], client_id: str) -> bool:
        """简单的客户端 ID 匹配（支持 * 通配符）"""
        if not pattern:
            return True
        if pattern.endswith("*"):
            return client_id.startswith(pattern[:-1])
        return pattern == client_id

    @staticmethod
    def _match_topic(pattern: str, topic: str) -> bool:
        """简单的 MQTT Topic 匹配（支持 + 和 # 通配符）"""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        for i, pp in enumerate(pattern_parts):
            if pp == "#":
                return True  # # 匹配剩余所有层级
            if i >= len(topic_parts):
                return False
            if pp == "+":
                continue  # + 匹配单层
            if pp != topic_parts[i]:
                return False

        return len(pattern_parts) == len(topic_parts)


# 单例
emqx_acl_service = EmqxAclService()
