"""
应用配置模块
"""
import secrets
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


def generate_secret_key() -> str:
    """生成安全的随机密钥"""
    return secrets.token_urlsafe(64)


class Settings(BaseSettings):
    """应用配置"""
    # 应用信息
    app_name: str = "算力中心智能监控系统"
    app_version: str = "1.0.0"
    debug: bool = True  # 开发阶段默认开启，正式发布前改为 False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8080

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./dcim.db"

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

    # 模拟模式配置
    simulation_enabled: bool = True  # 是否启用模拟数据
    simulation_interval: int = 5     # 模拟数据生成间隔(秒)

    # 授权配置
    license_key: str = "DEMO-0000-0000-0000"
    max_points: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
