"""
应用配置模块
"""

import secrets
from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache
from typing import Optional


def generate_secret_key() -> str:
    """生成安全的随机密钥"""
    return secrets.token_urlsafe(64)


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    app_name: str = "算力中心智能监控系统"
    app_version: str = "3.0.0"
    debug: bool = True  # 开发阶段默认开启，正式发布前改为 False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8080

    # 数据库 — 通过环境变量 DATABASE_URL 切换
    # SQLite:      sqlite+aiosqlite:///./dcim.db
    # PostgreSQL:  postgresql+asyncpg://user:pass@localhost:5432/dcim
    database_url: str = "sqlite+aiosqlite:///./dcim.db"

    # Redis 配置 (Story 26.1: 反事实分析分布式锁)
    REDIS_URL: str = "redis://localhost:6379/0"

    # TimescaleDB（仅 PostgreSQL 生效）
    timescaledb_enabled: bool = False

    # JWT 配置 - 必须通过环境变量设置，无默认值更安全
    secret_key: str = Field(default_factory=generate_secret_key)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 开发阶段8小时，正式发布改为30分钟
    refresh_token_expire_days: int = 7  # 刷新令牌过期天数

    # CORS 配置
    cors_origins: str = "http://localhost:5173,http://localhost:3000"  # 允许的前端地址，逗号分隔

    # 数据采集配置
    collect_interval: int = 10  # 秒
    data_retention_days: int = 30

    # === 数据初始化配置（Story 28.2）===
    seed_enabled: bool = Field(default=False, description="启用最小化种子")
    demo_enabled: bool = Field(default=False, description="启用 Demo 数据")
    simulation_enabled: bool = Field(default=False, description="启用数据模拟器")

    # === Seed 配置（Story 28.2）===
    default_site_name: str = Field(default="默认站点")
    default_floor_count: int = Field(default=1, ge=1, le=50)
    default_room_count: int = Field(default=1, ge=1, le=100)
    default_admin_password: str = Field(default="admin123")

    # === 电价配置（五级制，Story 28.2）===
    default_sharp_peak_price: float = Field(default=1.5)
    default_peak_price: float = Field(default=1.2)
    default_flat_price: float = Field(default=0.8)
    default_valley_price: float = Field(default=0.4)
    default_deep_valley_price: float = Field(default=0.2)

    # 模拟模式配置（已废弃，保留向后兼容）
    simulation_interval: int = 60  # 模拟数据生成间隔(秒)

    # 授权配置
    license_key: str = "DEMO-0000-0000-0000"
    max_points: int = 100

    # VPP 对外接口认证 (Story 33.2)
    VPP_API_KEY: str = "dcim-vpp-default-key-change-me"

    # Redis 配置
    redis_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"

    @property
    def effective_redis_url(self) -> str:
        """Canonical Redis URL used by all Redis clients."""
        return self.redis_url or self.REDIS_URL

    @property
    def redis_host(self) -> str:
        """从 redis_url 解析主机"""
        parsed = urlparse(self.effective_redis_url)
        return parsed.hostname or "localhost"

    @property
    def redis_port(self) -> int:
        """从 redis_url 解析端口"""
        parsed = urlparse(self.effective_redis_url)
        return parsed.port or 6379

    # MQTT 配置
    mqtt_enabled: bool = True
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_client_id: str = "dcim-backend"
    # 电价配置模式
    pricing_strict_mode: bool = Field(
        default=True, description="电价配置严格模式：True=不完整时抛出异常，False=使用默认电价填补"
    )
    pricing_default_price: float = Field(default=0.7, description="默认电价（元/kWh），用于填补缺失时段")

    # 故障树 HMAC 密钥（Story 24.4）
    fault_tree_hmac_key: str = Field(default="", description="故障树 HMAC 签名密钥（至少 32 字符）")
    fault_tree_hmac_key_previous: Optional[str] = Field(
        default=None, description="故障树 HMAC 旧密钥（密钥轮换时使用）"
    )

    @field_validator("fault_tree_hmac_key")
    @classmethod
    def validate_hmac_key(cls, v):
        """验证 HMAC 密钥长度"""
        if not v:
            raise ValueError("FAULT_TREE_HMAC_KEY is required")
        if len(v) < 32:
            raise ValueError("FAULT_TREE_HMAC_KEY must be at least 32 characters")
        return v

    # 邮件服务配置（Story 26.2）
    smtp_enabled: bool = Field(default=False, description="启用邮件服务")
    smtp_host: str = Field(default="", description="SMTP 服务器地址")
    smtp_port: int = Field(default=587, description="SMTP 端口")
    smtp_user: str = Field(default="", description="SMTP 用户名")
    smtp_password: str = Field(default="", description="SMTP 密码")
    smtp_from_email: str = Field(default="", description="发件人邮箱")

    # 报告文件存储目录（Story 26.6）
    report_dir: str = Field(default="reports/", description="报告文件存储目录")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_prefix="",
    )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
