"""
插件管理器
Plugin Manager

负责插件的注册、配置和执行
Responsible for plugin registration, configuration and execution
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .base import (
    AnalysisPlugin,
    AnalysisContext,
    SuggestionResult,
    PluginConfig,
    EnergyData,
    PowerData,
    BillData,
    DeviceData,
    EnvironmentData
)
from app.models.energy import (
    PowerDevice,
    EnergyDaily,
    EnergyMonthly,
    ElectricityPricing,
    EnergySuggestion,
    PUEHistory
)
from app.models.point import Point, PointRealtime

logger = logging.getLogger(__name__)


class PluginManager:
    """
    插件管理器

    负责:
    - 注册和管理插件
    - 构建分析上下文
    - 执行插件分析
    - 保存分析结果
    """

    _instance: Optional['PluginManager'] = None
    _plugins: Dict[str, AnalysisPlugin] = {}
    _plugin_classes: Dict[str, Type[AnalysisPlugin]] = {}

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins = {}
            cls._instance._plugin_classes = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'PluginManager':
        """获取单例实例"""
        return cls()

    def register_plugin_class(self, plugin_class: Type[AnalysisPlugin]) -> None:
        """
        注册插件类

        Args:
            plugin_class: 插件类
        """
        # 创建临时实例获取插件ID
        temp_instance = plugin_class()
        plugin_id = temp_instance.plugin_id

        if plugin_id in self._plugin_classes:
            logger.warning(f"插件 {plugin_id} 已存在，将被覆盖")

        self._plugin_classes[plugin_id] = plugin_class
        # 同时创建默认配置的实例
        self._plugins[plugin_id] = temp_instance
        logger.info(f"注册插件: {plugin_id} ({temp_instance.plugin_name})")

    def register_plugin(self, plugin: AnalysisPlugin) -> None:
        """
        注册插件实例

        Args:
            plugin: 插件实例
        """
        plugin_id = plugin.plugin_id

        if plugin_id in self._plugins:
            logger.warning(f"插件 {plugin_id} 已存在，将被覆盖")

        self._plugins[plugin_id] = plugin
        self._plugin_classes[plugin_id] = type(plugin)
        logger.info(f"注册插件实例: {plugin_id} ({plugin.plugin_name})")

    def unregister_plugin(self, plugin_id: str) -> bool:
        """
        注销插件

        Args:
            plugin_id: 插件ID

        Returns:
            是否成功
        """
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            if plugin_id in self._plugin_classes:
                del self._plugin_classes[plugin_id]
            logger.info(f"注销插件: {plugin_id}")
            return True
        return False

    def get_plugin(self, plugin_id: str) -> Optional[AnalysisPlugin]:
        """
        获取插件实例

        Args:
            plugin_id: 插件ID

        Returns:
            插件实例或None
        """
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> List[AnalysisPlugin]:
        """获取所有插件"""
        return list(self._plugins.values())

    def get_enabled_plugins(self) -> List[AnalysisPlugin]:
        """获取所有启用的插件"""
        return [p for p in self._plugins.values() if p.config.enabled]

    def configure_plugin(self, plugin_id: str, config: PluginConfig) -> bool:
        """
        配置插件

        Args:
            plugin_id: 插件ID
            config: 插件配置

        Returns:
            是否成功
        """
        if plugin_id in self._plugins:
            self._plugins[plugin_id].config = config
            logger.info(f"配置插件: {plugin_id}")
            return True
        return False

    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        if plugin_id in self._plugins:
            self._plugins[plugin_id].config.enabled = True
            return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件"""
        if plugin_id in self._plugins:
            self._plugins[plugin_id].config.enabled = False
            return True
        return False

    async def build_context(
        self,
        db: AsyncSession,
        days: int = 30
    ) -> AnalysisContext:
        """
        构建分析上下文

        Args:
            db: 数据库会话
            days: 分析数据天数

        Returns:
            分析上下文
        """
        now = datetime.now()
        start_date = now - timedelta(days=days)

        context = AnalysisContext(
            analysis_start=start_date,
            analysis_end=now
        )

        # 1. 获取能耗数据
        context.energy_data = await self._load_energy_data(db, start_date, now)

        # 2. 获取功率数据
        context.power_data = await self._load_power_data(db)

        # 3. 获取账单数据
        context.bill_data = await self._load_bill_data(db, days=365)

        # 4. 获取设备数据
        context.device_data = await self._load_device_data(db)

        # 5. 获取环境数据
        context.environment_data = await self._load_environment_data(db, days=7)

        # 6. 加载电价配置
        context.pricing_config = await self._load_pricing_config(db)

        logger.info(
            f"构建分析上下文完成: "
            f"能耗数据 {len(context.energy_data)} 条, "
            f"功率数据 {len(context.power_data)} 条, "
            f"设备数据 {len(context.device_data)} 条"
        )

        return context

    async def _load_energy_data(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime
    ) -> List[EnergyData]:
        """加载能耗数据"""
        energy_data = []

        try:
            result = await db.execute(
                select(EnergyDaily).where(
                    and_(
                        EnergyDaily.date >= start_date.date(),
                        EnergyDaily.date <= end_date.date()
                    )
                ).order_by(EnergyDaily.date)
            )
            records = result.scalars().all()

            for record in records:
                energy_data.append(EnergyData(
                    date=datetime.combine(record.date, datetime.min.time()),
                    total_energy=record.total_energy or 0,
                    peak_energy=record.peak_energy or 0,
                    valley_energy=record.valley_energy or 0,
                    flat_energy=record.flat_energy or 0,
                    peak_cost=record.peak_cost or 0,
                    valley_cost=record.valley_cost or 0,
                    flat_cost=record.flat_cost or 0,
                    total_cost=record.total_cost or 0
                ))
        except Exception as e:
            logger.error(f"加载能耗数据失败: {e}")
            # 生成模拟数据用于演示
            energy_data = self._generate_mock_energy_data(start_date, end_date)

        return energy_data

    def _generate_mock_energy_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[EnergyData]:
        """
        生成确定性的模拟能耗数据

        [V2.9-FIX] 移除 random 模块，使用基于日期的确定性波动
        """
        energy_data = []
        current = start_date

        while current <= end_date:
            # 确定性波动 - 基于日期计算
            day_of_year = current.timetuple().tm_yday
            day_offset = ((day_of_year * 7) % 200 - 100) / 1000  # -0.1 到 +0.1

            base_energy = 1000 * (1 + day_offset)

            # 确定性的时段比例
            peak_ratio = 0.4 + (day_of_year % 10) * 0.01 - 0.05  # 0.35-0.45
            valley_ratio = 0.25 + ((day_of_year * 3) % 6) * 0.01 - 0.03  # 0.22-0.28
            flat_ratio = 1 - peak_ratio - valley_ratio

            peak_energy = base_energy * peak_ratio
            valley_energy = base_energy * valley_ratio
            flat_energy = base_energy * flat_ratio

            energy_data.append(EnergyData(
                date=current,
                total_energy=base_energy,
                peak_energy=peak_energy,
                valley_energy=valley_energy,
                flat_energy=flat_energy,
                peak_cost=peak_energy * 1.2,
                valley_cost=valley_energy * 0.4,
                flat_cost=flat_energy * 0.8,
                total_cost=peak_energy * 1.2 + valley_energy * 0.4 + flat_energy * 0.8
            ))
            current += timedelta(days=1)

        return energy_data

    async def _load_power_data(self, db: AsyncSession) -> List[PowerData]:
        """加载功率数据"""
        power_data = []

        try:
            # 从 PowerDevice 和 PointRealtime 获取实时功率数据
            result = await db.execute(
                select(PowerDevice).where(PowerDevice.status == 'online')
            )
            devices = result.scalars().all()

            for device in devices:
                power_data.append(PowerData(
                    timestamp=datetime.now(),
                    device_id=str(device.id),
                    device_name=device.name,
                    device_type=device.device_type,
                    voltage=device.voltage or 380,
                    current=device.current or 0,
                    active_power=device.active_power or 0,
                    reactive_power=device.reactive_power or 0,
                    apparent_power=device.apparent_power or 0,
                    power_factor=device.power_factor or 0.95,
                    frequency=device.frequency or 50,
                    load_rate=device.load_rate or 0
                ))
        except Exception as e:
            logger.error(f"加载功率数据失败: {e}")
            # 生成模拟数据
            power_data = self._generate_mock_power_data()

        return power_data

    def _generate_mock_power_data(self) -> List[PowerData]:
        """
        生成确定性的模拟功率数据

        [V2.9-FIX] 移除 random 模块，使用固定的设备参数
        """
        power_data = []

        device_types = [
            ('UPS-1', 'UPS', 100),
            ('UPS-2', 'UPS', 100),
            ('PDU-A1', 'PDU', 30),
            ('PDU-A2', 'PDU', 30),
            ('PDU-B1', 'PDU', 30),
            ('AC-1', 'AIR_CONDITIONER', 20),
            ('AC-2', 'AIR_CONDITIONER', 20),
            ('Server-Rack-1', 'IT_EQUIPMENT', 15),
            ('Server-Rack-2', 'IT_EQUIPMENT', 15),
            ('Server-Rack-3', 'IT_EQUIPMENT', 15),
        ]

        for i, (name, dtype, rated_power) in enumerate(device_types):
            # 确定性的负载率 - 基于设备索引
            load_rate = 0.5 + (i % 5) * 0.08  # 0.50-0.82
            active_power = rated_power * load_rate
            # 确定性的功率因数
            power_factor = 0.88 + (i % 10) * 0.01  # 0.88-0.97
            apparent_power = active_power / power_factor
            reactive_power = (apparent_power**2 - active_power**2)**0.5

            power_data.append(PowerData(
                timestamp=datetime.now(),
                device_id=str(i + 1),
                device_name=name,
                device_type=dtype,
                voltage=380 + (i % 5) - 2,  # 378-382
                current=active_power * 1000 / (380 * 1.732),
                active_power=active_power,
                reactive_power=reactive_power,
                apparent_power=apparent_power,
                power_factor=power_factor,
                frequency=50.0,
                load_rate=load_rate * 100
            ))

        return power_data

    async def _load_bill_data(
        self,
        db: AsyncSession,
        days: int = 365
    ) -> List[BillData]:
        """加载账单数据"""
        bill_data = []

        try:
            start_date = datetime.now() - timedelta(days=days)
            result = await db.execute(
                select(EnergyMonthly).where(
                    EnergyMonthly.month >= start_date.strftime('%Y-%m')
                ).order_by(EnergyMonthly.month)
            )
            records = result.scalars().all()

            for record in records:
                total_energy = (record.peak_energy or 0) + (record.valley_energy or 0) + (record.flat_energy or 0)
                if total_energy > 0:
                    bill_data.append(BillData(
                        period_start=datetime.strptime(record.month + '-01', '%Y-%m-%d'),
                        period_end=datetime.strptime(record.month + '-01', '%Y-%m-%d') + timedelta(days=30),
                        total_energy=total_energy,
                        total_cost=record.total_cost or 0,
                        peak_ratio=(record.peak_energy or 0) / total_energy,
                        valley_ratio=(record.valley_energy or 0) / total_energy,
                        flat_ratio=(record.flat_energy or 0) / total_energy,
                        demand_cost=0,
                        basic_cost=0,
                        max_demand=record.max_power or 0
                    ))
        except Exception as e:
            logger.error(f"加载账单数据失败: {e}")
            # 生成模拟数据
            bill_data = self._generate_mock_bill_data(days)

        return bill_data

    def _generate_mock_bill_data(self, days: int) -> List[BillData]:
        """
        生成确定性的模拟账单数据

        [V2.9-FIX] 移除 random 模块，使用与 energy.py 和 DemandAnalysisService 一致的算法
        这是解决"优化建议"与"计量点配置表"数据不一致的关键修复

        关键: max_demand 必须与 DemandAnalysisService 中的模拟数据保持一致
        - 申报需量默认 800kW
        - 实际最大需量 = 申报需量 * 基础比率 * 季节因子
        - 基础比率范围: 0.77-0.87 (确定性)
        """
        from ..demand_analysis_service import DemandAnalysisService

        bill_data = []
        months = days // 30
        current = datetime.now() - timedelta(days=days)

        # 使用与 DemandAnalysisService 一致的常量
        declared_demand = DemandAnalysisService.DEFAULT_DECLARED_DEMAND  # 800.0 kW
        demand_price = DemandAnalysisService.DEFAULT_DEMAND_PRICE  # 38.0 元/kW·月

        for month_idx in range(months):
            month_num = (current.month + month_idx - 1) % 12 + 1

            # 确定性的月度波动 - 与 DemandAnalysisService.generate_mock_demand_curve 保持一致
            # 基础比率 (全站 meter_point_id=None 对应 seed=0)
            seed_factor = 0.1  # seed=0 时: (0 + 1) / 10 = 0.1
            base_ratio = 0.75 + seed_factor * 0.2  # = 0.77

            # 季节性波动
            month_factor = 1.0 + (month_num - 6) * 0.015
            if month_num in [7, 8, 1, 2]:  # 夏季和冬季高峰
                month_factor += 0.04

            # 计算最大需量 - 使用与 DemandAnalysisService 完全一致的公式
            # 基础需量 650.0 * base_ratio * month_factor
            base_demand = 650.0  # 与 DemandAnalysisService 一致
            max_demand = base_demand * base_ratio * month_factor

            # 能耗计算
            total_energy = 30000 + (month_idx % 5) * 1000 - 2000  # 28000-32000
            peak_ratio = 0.40 + (month_idx % 10) * 0.01 - 0.05  # 0.35-0.45
            valley_ratio = 0.25 + (month_idx % 6) * 0.01 - 0.03  # 0.22-0.28
            flat_ratio = 1 - peak_ratio - valley_ratio

            total_cost = (
                total_energy * peak_ratio * 1.2 +
                total_energy * valley_ratio * 0.4 +
                total_energy * flat_ratio * 0.8
            )

            # 需量费用 = 申报需量 * 需量电价
            demand_cost = declared_demand * demand_price

            bill_data.append(BillData(
                period_start=current,
                period_end=current + timedelta(days=30),
                total_energy=total_energy,
                total_cost=total_cost,
                peak_ratio=peak_ratio,
                valley_ratio=valley_ratio,
                flat_ratio=flat_ratio,
                demand_cost=demand_cost,
                basic_cost=200,
                max_demand=round(max_demand, 1)  # 关键：使用确定性的 max_demand
            ))
            current += timedelta(days=30)

        return bill_data

    async def _load_device_data(self, db: AsyncSession) -> List[DeviceData]:
        """加载设备数据"""
        device_data = []

        try:
            result = await db.execute(select(PowerDevice))
            devices = result.scalars().all()

            for device in devices:
                device_data.append(DeviceData(
                    device_id=str(device.id),
                    device_name=device.name,
                    device_type=device.device_type,
                    rated_power=device.rated_power or 0,
                    current_power=device.active_power or 0,
                    efficiency=device.efficiency or 95,
                    running_hours=24 * 30,  # 假设持续运行
                    location=device.location or ''
                ))
        except Exception as e:
            logger.error(f"加载设备数据失败: {e}")
            device_data = self._generate_mock_device_data()

        return device_data

    def _generate_mock_device_data(self) -> List[DeviceData]:
        """
        生成确定性的模拟设备数据

        [V2.9-FIX] 移除 random 模块，使用基于索引的确定性值
        """
        device_data = []

        devices = [
            ('UPS-1', 'UPS', 100, 'A区'),
            ('UPS-2', 'UPS', 100, 'B区'),
            ('PDU-A1', 'PDU', 30, 'A区'),
            ('PDU-A2', 'PDU', 30, 'A区'),
            ('PDU-B1', 'PDU', 30, 'B区'),
            ('AC-1', 'AIR_CONDITIONER', 20, 'A区'),
            ('AC-2', 'AIR_CONDITIONER', 20, 'B区'),
            ('Rack-1', 'IT_EQUIPMENT', 15, 'A区'),
            ('Rack-2', 'IT_EQUIPMENT', 15, 'A区'),
            ('Rack-3', 'IT_EQUIPMENT', 15, 'B区'),
        ]

        for i, (name, dtype, rated_power, location) in enumerate(devices):
            # 确定性的负载率
            load_rate = 0.5 + (i % 5) * 0.08  # 0.50-0.82
            # 确定性的效率值
            if dtype in ['UPS', 'PDU']:
                efficiency = 92.0 + (i % 5) * 1.2  # 92.0-96.8
            else:
                efficiency = 84.0 + (i % 8) * 1.5  # 84.0-94.5

            device_data.append(DeviceData(
                device_id=str(i + 1),
                device_name=name,
                device_type=dtype,
                rated_power=rated_power,
                current_power=rated_power * load_rate,
                efficiency=efficiency,
                running_hours=24 * 30,
                location=location
            ))

        return device_data

    async def _load_environment_data(
        self,
        db: AsyncSession,
        days: int = 7
    ) -> List[EnvironmentData]:
        """加载环境数据"""
        environment_data = []

        try:
            start_date = datetime.now() - timedelta(days=days)
            result = await db.execute(
                select(PUEHistory).where(
                    PUEHistory.recorded_at >= start_date
                ).order_by(PUEHistory.recorded_at)
            )
            records = result.scalars().all()

            for record in records:
                environment_data.append(EnvironmentData(
                    timestamp=record.recorded_at,
                    temperature=25,  # 假设值
                    humidity=50,
                    pue=record.pue or 1.5,
                    it_power=record.it_power or 50,
                    cooling_power=record.cooling_power or 15,
                    total_power=record.total_power or 75
                ))
        except Exception as e:
            logger.error(f"加载环境数据失败: {e}")
            environment_data = self._generate_mock_environment_data(days)

        return environment_data

    def _generate_mock_environment_data(self, days: int) -> List[EnvironmentData]:
        """
        生成确定性的模拟环境数据

        [V2.9-FIX] 移除 random 模块，使用基于小时的确定性波动
        """
        environment_data = []

        current = datetime.now() - timedelta(days=days)
        now = datetime.now()
        hour_idx = 0

        while current <= now:
            # 确定性波动 - 基于小时索引
            offset = (hour_idx * 7) % 100
            it_power = 50 + (offset % 10) - 5  # 45-55
            cooling_power = 15 + (offset % 4) - 2  # 13-17
            other_power = 10 + (offset % 2) - 1  # 9-11
            total_power = it_power + cooling_power + other_power

            # 温湿度确定性波动
            hour_of_day = current.hour
            temp_offset = (hour_of_day - 12) * 0.15  # 日间偏暖
            humidity_offset = ((hour_idx * 3) % 20) - 10  # -10 到 +10

            environment_data.append(EnvironmentData(
                timestamp=current,
                temperature=24 + temp_offset,
                humidity=50 + humidity_offset,
                pue=total_power / it_power if it_power > 0 else 1.5,
                it_power=it_power,
                cooling_power=cooling_power,
                total_power=total_power
            ))
            current += timedelta(hours=1)
            hour_idx += 1

        return environment_data

    async def _load_pricing_config(self, db: AsyncSession) -> Dict[str, float]:
        """加载电价配置"""
        pricing_config = {
            'peak_price': 1.2,
            'valley_price': 0.4,
            'flat_price': 0.8,
            'demand_price': 38.0
        }

        try:
            result = await db.execute(
                select(ElectricityPricing).where(
                    ElectricityPricing.is_active == True
                )
            )
            records = result.scalars().all()

            for record in records:
                if record.period_type == 'peak':
                    pricing_config['peak_price'] = record.price
                elif record.period_type == 'valley':
                    pricing_config['valley_price'] = record.price
                elif record.period_type == 'flat':
                    pricing_config['flat_price'] = record.price
        except Exception as e:
            logger.error(f"加载电价配置失败: {e}")

        return pricing_config

    async def run_analysis(
        self,
        db: AsyncSession,
        plugin_ids: Optional[List[str]] = None,
        days: int = 30,
        save_results: bool = True
    ) -> List[SuggestionResult]:
        """
        执行分析

        Args:
            db: 数据库会话
            plugin_ids: 要执行的插件ID列表，为None则执行所有启用的插件
            days: 分析数据天数
            save_results: 是否保存结果到数据库

        Returns:
            所有建议结果
        """
        # 构建分析上下文
        context = await self.build_context(db, days)

        # 确定要执行的插件
        if plugin_ids:
            plugins = [self._plugins[pid] for pid in plugin_ids if pid in self._plugins]
        else:
            plugins = self.get_enabled_plugins()

        # 按执行顺序排序
        plugins.sort(key=lambda p: p.config.execution_order)

        all_results: List[SuggestionResult] = []

        # 执行每个插件
        for plugin in plugins:
            try:
                logger.info(f"执行插件: {plugin.plugin_id} ({plugin.plugin_name})")

                # 验证上下文
                if not plugin.validate_context(context):
                    logger.warning(f"插件 {plugin.plugin_id} 上下文验证失败，跳过")
                    continue

                # 执行分析
                results = await plugin.analyze(context)
                all_results.extend(results)

                logger.info(f"插件 {plugin.plugin_id} 生成 {len(results)} 条建议")

            except Exception as e:
                logger.error(f"插件 {plugin.plugin_id} 执行失败: {e}", exc_info=True)

        # 保存结果
        if save_results and all_results:
            await self._save_suggestions(db, all_results)

        return all_results

    async def run_single_plugin(
        self,
        db: AsyncSession,
        plugin_id: str,
        days: int = 30,
        save_results: bool = True
    ) -> List[SuggestionResult]:
        """
        执行单个插件

        Args:
            db: 数据库会话
            plugin_id: 插件ID
            days: 分析数据天数
            save_results: 是否保存结果

        Returns:
            建议结果列表
        """
        return await self.run_analysis(db, [plugin_id], days, save_results)

    async def _save_suggestions(
        self,
        db: AsyncSession,
        results: List[SuggestionResult]
    ) -> None:
        """保存建议到数据库"""
        for result in results:
            try:
                suggestion = EnergySuggestion(
                    suggestion_type=result.suggestion_type.value,
                    priority=result.priority.value,
                    title=result.title,
                    description=result.description,
                    detail=result.detail,
                    estimated_saving=result.estimated_saving,
                    estimated_cost_saving=result.estimated_cost_saving,
                    implementation_difficulty=result.implementation_difficulty,
                    payback_period=result.payback_period,
                    status='pending',
                    created_at=result.created_at
                )
                db.add(suggestion)
            except Exception as e:
                logger.error(f"保存建议失败: {e}")

        try:
            await db.commit()
            logger.info(f"保存 {len(results)} 条建议到数据库")
        except Exception as e:
            await db.rollback()
            logger.error(f"提交建议失败: {e}")

    def get_plugin_info(self) -> List[Dict]:
        """获取所有插件信息"""
        return [
            {
                'plugin_id': p.plugin_id,
                'name': p.plugin_name,
                'description': p.plugin_description,
                'suggestion_type': p.suggestion_type.value,
                'enabled': p.config.enabled,
                'execution_order': p.config.execution_order
            }
            for p in self._plugins.values()
        ]


# 全局插件管理器实例
plugin_manager = PluginManager.get_instance()
