"""采集调度器，管理多数据源的异步采集任务"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from .adapters.base import (
    BaseProtocolAdapter,
    DataSourceConfig,
    NormalizedReading,
)
from .adapters.registry import get_adapter
from .dry_contact import DryContactMonitor, DryContactEvent
from .normalizer import DataNormalizer
from .retry import RetryPolicy

logger = logging.getLogger(__name__)

# 数据回调类型: 接收归一化读数列表
OnDataCallback = Callable[[list[NormalizedReading]], Any]
# 告警回调类型: 接收数据源ID和错误信息
OnAlarmCallback = Callable[[str, str], Any]
# 干接点回调类型: 接收干接点事件列表
OnDryContactCallback = Callable[[list[DryContactEvent]], Any]


class CollectionScheduler:
    """采集调度器 — 为每个数据源创建独立的异步采集任务"""

    def __init__(
        self,
        on_data: OnDataCallback | None = None,
        on_alarm: OnAlarmCallback | None = None,
        on_dry_contact: OnDryContactCallback | None = None,
    ) -> None:
        self._on_data = on_data
        self._on_alarm = on_alarm
        self._on_dry_contact = on_dry_contact
        self._tasks: dict[str, asyncio.Task] = {}
        self._configs: dict[str, DataSourceConfig] = {}
        self._adapters: dict[str, BaseProtocolAdapter] = {}
        self._running = False
        self._dry_contact_monitor = DryContactMonitor()

    def start(self) -> None:
        """启动调度器"""
        self._running = True
        logger.info("采集调度器已启动")

    async def stop(self) -> None:
        """停止调度器，取消所有采集任务（保留 configs 以支持重启）"""
        self._running = False
        for ds_id, task in self._tasks.items():
            task.cancel()
            logger.info("取消采集任务: %s", ds_id)

        # 等待所有任务完成取消，记录异常但不抛出
        if self._tasks:
            results = await asyncio.gather(*self._tasks.values(), return_exceptions=True)
            for ds_id, result in zip(self._tasks.keys(), results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    logger.error("任务 %s 停止时异常: %s", ds_id, result)

        self._tasks.clear()
        self._adapters.clear()
        self._dry_contact_monitor.clear_all()
        logger.info("采集调度器已停止，保留 %d 个数据源配置", len(self._configs))

    def add_datasource(self, config: DataSourceConfig) -> None:
        """添加数据源并启动采集任务

        Raises:
            RuntimeError: 调度器未启动
        """
        if not self._running:
            raise RuntimeError("调度器未启动，请先调用 start()")

        ds_id = config.datasource_id
        if ds_id in self._tasks:
            logger.warning("数据源 '%s' 已存在，跳过添加", ds_id)
            return

        self._configs[ds_id] = config
        task = asyncio.create_task(
            self._collection_loop(config),
            name=f"collect-{ds_id}",
        )
        self._tasks[ds_id] = task
        logger.info(
            "添加数据源采集任务: %s (协议: %s, 间隔: %ds)", ds_id, config.protocol_type, config.collection_interval
        )

    async def remove_datasource(self, datasource_id: str) -> None:
        """移除数据源并取消采集任务"""
        task = self._tasks.pop(datasource_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # 断开适配器
        adapter = self._adapters.pop(datasource_id, None)
        if adapter is not None:
            try:
                await adapter.disconnect()
            except Exception:
                logger.exception("断开适配器 '%s' 时出错", datasource_id)

        self._configs.pop(datasource_id, None)
        self._dry_contact_monitor.reset(datasource_id)
        logger.info("已移除数据源: %s", datasource_id)

    async def reload_datasource(self, config: DataSourceConfig) -> None:
        """热重载数据源配置（先移除再添加）"""
        await self.remove_datasource(config.datasource_id)
        self.add_datasource(config)
        logger.info("已重载数据源: %s", config.datasource_id)

    async def _collection_loop(self, config: DataSourceConfig) -> None:
        """单个数据源的采集循环

        流程:
        1. 获取并实例化协议适配器
        2. 建立连接（失败时指数退避重试）
        3. 创建 RetryPolicy
        4. 循环采集: 批量读取 → 归一化 → 回调
        5. 失败时指数退避，通信中断时触发告警
        """
        ds_id = config.datasource_id

        # 获取适配器类并实例化
        adapter_cls = get_adapter(config.protocol_type)
        adapter = adapter_cls()
        self._adapters[ds_id] = adapter

        # 创建重试策略（连接阶段和采集阶段共用）
        retry = RetryPolicy(
            base_delay=config.retry_base_delay,
            max_delay=config.retry_max_delay,
            max_failures=config.retry_max_failures,
        )

        # 建立连接（失败时指数退避重试）
        connected = False
        while self._running and not connected:
            try:
                connected = await adapter.connect(config)
                if connected:
                    retry.record_success()
                    logger.info("数据源 '%s' 连接成功", ds_id)
                else:
                    delay = retry.record_failure()
                    logger.warning(
                        "数据源 '%s' 连接返回 False (连续失败: %d, 下次重试: %.1fs)",
                        ds_id,
                        retry.failure_count,
                        delay,
                    )
                    if retry.is_interrupted:
                        error_msg = f"数据源 '{ds_id}' 连接阶段通信中断，连续失败 {retry.failure_count} 次"
                        logger.error(error_msg)
                        if self._on_alarm:
                            try:
                                result = self._on_alarm(ds_id, error_msg)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                logger.exception("告警回调执行失败")
                    await asyncio.sleep(delay)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                delay = retry.record_failure()
                logger.warning(
                    "数据源 '%s' 连接异常: %s (连续失败: %d, 下次重试: %.1fs)",
                    ds_id,
                    exc,
                    retry.failure_count,
                    delay,
                )
                if retry.is_interrupted:
                    error_msg = f"数据源 '{ds_id}' 连接阶段通信中断，连续失败 {retry.failure_count} 次"
                    logger.error(error_msg)
                    if self._on_alarm:
                        try:
                            result = self._on_alarm(ds_id, error_msg)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            logger.exception("告警回调执行失败")
                await asyncio.sleep(delay)

        if not connected:
            # 调度器已停止，退出
            self._adapters.pop(ds_id, None)
            return

        # 连接成功后重置重试策略用于采集阶段
        retry.reset()

        # 采集超时 = 采集间隔的 80%
        read_timeout = config.collection_interval * 0.8
        normalizer = DataNormalizer()

        try:
            while self._running:
                try:
                    # 批量读取点位，带超时
                    raw_values = await asyncio.wait_for(
                        adapter.read_points(config.points),
                        timeout=read_timeout,
                    )

                    # 成功：重置重试计数
                    retry.record_success()

                    # 归一化处理
                    readings = normalizer.normalize(raw_values, config)

                    # 数据回调
                    if self._on_data and readings:
                        try:
                            result = self._on_data(readings)
                            # 支持异步回调
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            logger.exception("数据源 '%s' 的数据回调执行失败", ds_id)

                    # 干接点状态变化检测
                    dc_events = self._dry_contact_monitor.check(readings, config)
                    if dc_events and self._on_dry_contact:
                        try:
                            result = self._on_dry_contact(dc_events)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            logger.exception("数据源 '%s' 的干接点回调执行失败", ds_id)

                    # 等待下一个采集周期
                    await asyncio.sleep(config.collection_interval)

                except asyncio.CancelledError:
                    raise

                except Exception as exc:
                    delay = retry.record_failure()
                    logger.warning(
                        "数据源 '%s' 采集异常: %s (连续失败: %d, 下次重试: %.1fs)",
                        ds_id,
                        exc,
                        retry.failure_count,
                        delay,
                    )

                    # 通信中断处理
                    if retry.is_interrupted:
                        error_msg = f"数据源 '{ds_id}' 通信中断，连续失败 {retry.failure_count} 次"
                        logger.error(error_msg)
                        if self._on_alarm:
                            try:
                                result = self._on_alarm(ds_id, error_msg)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                logger.exception("告警回调执行失败")
                        await asyncio.sleep(config.retry_max_delay)
                    else:
                        await asyncio.sleep(delay)

        except asyncio.CancelledError:
            logger.info("数据源 '%s' 采集任务被取消", ds_id)
        finally:
            # 确保断开连接
            try:
                await adapter.disconnect()
            except Exception:
                logger.exception("数据源 '%s' 断开连接时出错", ds_id)
            self._adapters.pop(ds_id, None)
            logger.info("数据源 '%s' 采集循环结束", ds_id)
