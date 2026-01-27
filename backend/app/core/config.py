"""
应用配置模块
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    # 应用信息
    app_name: str = "算力中心智能监控系统"
    app_version: str = "1.0.0"
    debug: bool = True

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8080

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./dcim.db"

    # JWT 配置
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

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
