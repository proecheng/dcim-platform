"""连接测试服务"""
import asyncio
import logging
from dataclasses import asdict
from gateway.adapters.registry import ADAPTER_REGISTRY
from gateway.adapters.base import DataSourceConfig, ConnectionResult

logger = logging.getLogger(__name__)


async def test_datasource_connection(
    protocol_type: str,
    connection_config: dict,
) -> dict:
    """执行数据源连接测试"""
    if protocol_type not in ADAPTER_REGISTRY:
        raise ValueError(f"不支持的协议类型: {protocol_type}")

    adapter_cls = ADAPTER_REGISTRY[protocol_type]
    adapter = adapter_cls()

    logger.info("开始连接测试: protocol_type=%s", protocol_type)

    try:
        config = DataSourceConfig(
            datasource_id="test-connection",
            protocol_type=protocol_type,
            connection_params=connection_config,
        )

        async def _do_test() -> ConnectionResult:
            connected = await adapter.connect(config)
            if not connected:
                status = adapter.get_status()
                return ConnectionResult(
                    success=False,
                    message=status.error_message or "连接失败",
                )
            return await adapter.test_connection()

        result = await asyncio.wait_for(_do_test(), timeout=10.0)

        logger.info(
            "连接测试完成: protocol_type=%s, success=%s, latency_ms=%s",
            protocol_type, result.success, result.latency_ms,
        )
        return asdict(result)

    except asyncio.TimeoutError:
        logger.warning("连接测试超时: protocol_type=%s", protocol_type)
        return asdict(ConnectionResult(
            success=False,
            message="连接测试超时 (10s)",
        ))
    except Exception as e:
        logger.error("连接测试异常: protocol_type=%s, error=%s", protocol_type, e)
        return asdict(ConnectionResult(
            success=False,
            message=str(e),
        ))
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass  # 断开连接失败可忽略
