# 虚拟电厂方案模板实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现一个完整的虚拟电厂（VPP）方案生成系统，能够自动分析企业用电数据并生成包含所有计算指标的方案报告。

**Architecture:** 基于现有的后端FastAPI架构，新增VPP方案分析模块。前端展示方案报告，所有数据指标均来源于数据库或通过计算公式得出。

**Tech Stack:** Python/FastAPI, SQLAlchemy, Vue3/TypeScript, ECharts

---

## 数据来源与计算公式定义

### 源数据表 (已存在或需新建)

#### 1. 电费清单数据 (`electricity_bills`)
| 字段 | 说明 | 单位 |
|------|------|------|
| month | 月份 | - |
| total_consumption | 月度总用电量 | kWh |
| total_cost | 月度总电费 | 元 |
| peak_consumption | 峰段用电量 | kWh |
| valley_consumption | 谷段用电量 | kWh |
| flat_consumption | 平段用电量 | kWh |
| max_demand | 最大需量 | kW |
| power_factor | 功率因数 | - |
| basic_fee | 基本电费 | 元 |
| market_purchase_fee | 市场化购电电费 | 元 |
| transmission_fee | 输配电费 | 元 |
| system_operation_fee | 系统运行费 | 元 |
| government_fund | 政府性基金及附加 | 元 |

#### 2. 负荷曲线数据 (`load_curves`)
| 字段 | 说明 | 单位 |
|------|------|------|
| timestamp | 时间戳 (15分钟间隔) | - |
| load_value | 负荷值 | kW |
| date | 日期 | - |
| time_period | 时段类型 (峰/平/谷) | - |
| is_workday | 是否工作日 | boolean |

#### 3. 电价配置 (`electricity_prices`)
| 字段 | 说明 | 单位 |
|------|------|------|
| period_type | 时段类型 | peak/valley/flat |
| price | 单价 | 元/kWh |
| start_time | 开始时间 | HH:MM |
| end_time | 结束时间 | HH:MM |

#### 4. 可调节负荷资源 (`adjustable_loads`)
| 字段 | 说明 | 单位 |
|------|------|------|
| equipment_name | 设备名称 | - |
| equipment_type | 设备类型 | - |
| rated_power | 额定功率 | kW |
| adjustable_ratio | 可调节比例 | % |
| response_time | 响应时间 | 分钟 |
| adjustment_cost | 调节成本 | 元/次 |

---

### 计算指标与公式

#### A. 用电规模指标

**A1. 平均电价**
```
average_price = total_cost / total_consumption
数据来源: electricity_bills.total_cost, electricity_bills.total_consumption
单位: 元/kWh
```

**A2. 月度用电波动率**
```
fluctuation_rate = (max(total_consumption) - min(total_consumption)) / avg(total_consumption) * 100
数据来源: electricity_bills.total_consumption (多月数据)
单位: %
```

**A3. 峰段用电占比**
```
peak_ratio = peak_consumption / total_consumption * 100
数据来源: electricity_bills.peak_consumption, electricity_bills.total_consumption
单位: %
```

**A4. 谷段用电占比**
```
valley_ratio = valley_consumption / total_consumption * 100
数据来源: electricity_bills.valley_consumption, electricity_bills.total_consumption
单位: %
```

#### B. 负荷特性指标

**B1. 最大负荷 (P_max)**
```
P_max = max(load_value) 对于指定日期范围
数据来源: load_curves.load_value
单位: kW
```

**B2. 平均负荷 (P_avg)**
```
P_avg = sum(load_value) / count(load_value) 对于指定日期
数据来源: load_curves.load_value
单位: kW
每日96个点 (15分钟间隔)
```

**B3. 最小负荷 (P_min)**
```
P_min = min(load_value) 对于指定日期范围
数据来源: load_curves.load_value
单位: kW
```

**B4. 日负荷率 (η)**
```
η = P_avg / P_max
数据来源: 计算值 P_avg, P_max
范围: 0.65-0.85 为工业企业典型区间
```

**B5. 峰谷差 (ΔP)**
```
ΔP = P_max - P_min
数据来源: 计算值 P_max, P_min
单位: kW
```

**B6. 负荷标准差**
```
load_std = sqrt(sum((load_value - P_avg)^2) / n)
数据来源: load_curves.load_value
单位: kW
```

#### C. 电费结构指标

**C1. 市场化购电占比**
```
market_ratio = market_purchase_fee / total_cost * 100
数据来源: electricity_bills.market_purchase_fee, electricity_bills.total_cost
单位: %
典型值: 65%-72%
```

**C2. 输配电费占比**
```
transmission_ratio = transmission_fee / total_cost * 100
数据来源: electricity_bills.transmission_fee, electricity_bills.total_cost
单位: %
典型值: 22%-25%
```

**C3. 基本电费占比**
```
basic_fee_ratio = basic_fee / total_cost * 100
数据来源: electricity_bills.basic_fee, electricity_bills.total_cost
单位: %
```

#### D. 峰谷转移潜力指标

**D1. 可转移负荷量**
```
transferable_load = sum(adjustable_loads.rated_power * adjustable_loads.adjustable_ratio / 100)
数据来源: adjustable_loads表
单位: kW
```

**D2. 峰谷电价差**
```
price_spread = peak_price - valley_price
数据来源: electricity_prices表
单位: 元/kWh
```

**D3. 峰谷转移年收益潜力**
```
annual_transfer_benefit = transferable_load * daily_shift_hours * 365 * price_spread
数据来源: 计算值 transferable_load, price_spread
假设参数: daily_shift_hours (每日可转移小时数, 默认4小时)
单位: 元/年
```

#### E. 需量优化指标

**E1. 削峰空间**
```
peak_reduction_potential = P_max - target_demand
数据来源: 计算值 P_max
配置参数: target_demand (目标需量, 可设为P_max * 0.9)
单位: kW
```

**E2. 需量优化年收益**
```
demand_optimization_benefit = peak_reduction_potential * demand_price * 12
数据来源: 计算值 peak_reduction_potential
配置参数: demand_price (需量电价, 元/kW/月)
单位: 元/年
```

#### F. 虚拟电厂收益指标

**F1. 需求响应收益**
```
demand_response_revenue = adjustable_capacity * response_count * response_price
数据来源:
  - adjustable_capacity = sum(adjustable_loads.rated_power * adjustable_loads.adjustable_ratio / 100)
配置参数:
  - response_count (年响应次数, 默认20次)
  - response_price (响应补贴, 默认3-5元/kW)
单位: 元/年
```

**F2. 辅助服务收益**
```
ancillary_service_revenue = adjustable_capacity * service_hours * service_price
配置参数:
  - service_hours (年服务小时数, 默认200小时)
  - service_price (服务价格, 默认0.5-1元/kW·h)
单位: 元/年
```

**F3. 现货市场套利收益**
```
spot_arbitrage_revenue = transferable_load * arbitrage_hours * price_spread_spot
配置参数:
  - arbitrage_hours (年套利小时数, 默认500小时)
  - price_spread_spot (现货价差, 默认0.2-0.4元/kWh)
单位: 元/年
```

**F4. VPP年总收益**
```
total_vpp_revenue = demand_response_revenue + ancillary_service_revenue + spot_arbitrage_revenue
单位: 元/年
```

#### G. 投资回报指标

**G1. 总投资额**
```
total_investment = monitoring_system_cost + control_system_cost + platform_cost + other_cost
配置参数: 各项投资成本 (从配置表读取)
单位: 元
```

**G2. 年总收益**
```
annual_total_benefit = annual_transfer_benefit + demand_optimization_benefit + total_vpp_revenue
单位: 元/年
```

**G3. 静态投资回收期**
```
payback_period = total_investment / annual_total_benefit
单位: 年
```

**G4. 投资收益率 (ROI)**
```
ROI = annual_total_benefit / total_investment * 100
单位: %
```

---

## 实现任务

### Task 1: 创建数据库表结构

**Files:**
- Create: `backend/app/models/vpp_data.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/xxx_add_vpp_tables.py`

**Step 1: 创建VPP数据模型文件**

```python
# backend/app/models/vpp_data.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Date, Time, Enum
from sqlalchemy.sql import func
from app.db.base_class import Base
import enum

class TimePeriodType(str, enum.Enum):
    PEAK = "peak"
    VALLEY = "valley"
    FLAT = "flat"

class ElectricityBill(Base):
    """电费清单"""
    __tablename__ = "electricity_bills"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(String(7), index=True)  # YYYY-MM format
    total_consumption = Column(Float)  # kWh
    total_cost = Column(Float)  # 元
    peak_consumption = Column(Float)  # kWh
    valley_consumption = Column(Float)  # kWh
    flat_consumption = Column(Float)  # kWh
    max_demand = Column(Float)  # kW
    power_factor = Column(Float)
    basic_fee = Column(Float)  # 元
    market_purchase_fee = Column(Float)  # 元
    transmission_fee = Column(Float)  # 元
    system_operation_fee = Column(Float)  # 元
    government_fund = Column(Float)  # 元
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class LoadCurve(Base):
    """负荷曲线数据"""
    __tablename__ = "load_curves"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True)
    load_value = Column(Float)  # kW
    date = Column(Date, index=True)
    time_period = Column(Enum(TimePeriodType))
    is_workday = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class ElectricityPrice(Base):
    """电价配置"""
    __tablename__ = "electricity_prices"

    id = Column(Integer, primary_key=True, index=True)
    period_type = Column(Enum(TimePeriodType))
    price = Column(Float)  # 元/kWh
    start_time = Column(Time)
    end_time = Column(Time)
    effective_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())

class AdjustableLoad(Base):
    """可调节负荷资源"""
    __tablename__ = "adjustable_loads"

    id = Column(Integer, primary_key=True, index=True)
    equipment_name = Column(String(200))
    equipment_type = Column(String(100))
    rated_power = Column(Float)  # kW
    adjustable_ratio = Column(Float)  # 0-100%
    response_time = Column(Integer)  # 分钟
    adjustment_cost = Column(Float)  # 元/次
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class VPPConfig(Base):
    """VPP配置参数"""
    __tablename__ = "vpp_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, index=True)
    config_value = Column(Float)
    config_unit = Column(String(50))
    description = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

**Step 2: 更新models/__init__.py导入**

在 `backend/app/models/__init__.py` 中添加:
```python
from app.models.vpp_data import (
    ElectricityBill,
    LoadCurve,
    ElectricityPrice,
    AdjustableLoad,
    VPPConfig,
    TimePeriodType
)
```

**Step 3: 运行数据库迁移**

```bash
cd D:\mytest1\backend
alembic revision --autogenerate -m "add vpp tables"
alembic upgrade head
```

**Step 4: 验证表创建成功**

```bash
python -c "from app.db.session import engine; from app.models.vpp_data import *; print('Tables created successfully')"
```

**Step 5: Commit**

```bash
git add backend/app/models/vpp_data.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat: add VPP data models for electricity bills, load curves, prices and adjustable loads"
```

---

### Task 2: 创建VPP计算服务

**Files:**
- Create: `backend/app/services/vpp_calculator.py`

**Step 1: 创建VPP指标计算服务**

```python
# backend/app/services/vpp_calculator.py
from typing import List, Dict, Optional
from datetime import date, datetime
from decimal import Decimal
import statistics
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.vpp_data import ElectricityBill, LoadCurve, ElectricityPrice, AdjustableLoad, VPPConfig

class VPPCalculator:
    """VPP方案计算器 - 所有指标均有明确数据来源和计算公式"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== A. 用电规模指标 ====================

    async def calc_average_price(self, month: str) -> Dict:
        """A1. 计算平均电价
        公式: average_price = total_cost / total_consumption
        数据来源: electricity_bills表
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {"value": 0, "formula": "total_cost / total_consumption", "source": "无数据"}

        value = bill.total_cost / bill.total_consumption if bill.total_consumption > 0 else 0
        return {
            "value": round(value, 4),
            "unit": "元/kWh",
            "formula": "total_cost / total_consumption",
            "data_source": {
                "total_cost": bill.total_cost,
                "total_consumption": bill.total_consumption
            }
        }

    async def calc_fluctuation_rate(self, months: List[str]) -> Dict:
        """A2. 计算月度用电波动率
        公式: (max - min) / avg * 100
        数据来源: electricity_bills表 (多月数据)
        """
        result = await self.db.execute(
            select(ElectricityBill.total_consumption)
            .where(ElectricityBill.month.in_(months))
        )
        consumptions = [r[0] for r in result.fetchall()]

        if len(consumptions) < 2:
            return {"value": 0, "formula": "(max - min) / avg * 100", "source": "数据不足"}

        max_val = max(consumptions)
        min_val = min(consumptions)
        avg_val = statistics.mean(consumptions)
        rate = (max_val - min_val) / avg_val * 100 if avg_val > 0 else 0

        return {
            "value": round(rate, 2),
            "unit": "%",
            "formula": "(max(consumption) - min(consumption)) / avg(consumption) * 100",
            "data_source": {
                "max_consumption": max_val,
                "min_consumption": min_val,
                "avg_consumption": round(avg_val, 2),
                "months_count": len(consumptions)
            }
        }

    async def calc_peak_ratio(self, month: str) -> Dict:
        """A3. 计算峰段用电占比
        公式: peak_consumption / total_consumption * 100
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {"value": 0, "formula": "peak / total * 100", "source": "无数据"}

        ratio = bill.peak_consumption / bill.total_consumption * 100 if bill.total_consumption > 0 else 0
        return {
            "value": round(ratio, 2),
            "unit": "%",
            "formula": "peak_consumption / total_consumption * 100",
            "data_source": {
                "peak_consumption": bill.peak_consumption,
                "total_consumption": bill.total_consumption
            }
        }

    async def calc_valley_ratio(self, month: str) -> Dict:
        """A4. 计算谷段用电占比
        公式: valley_consumption / total_consumption * 100
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {"value": 0, "formula": "valley / total * 100", "source": "无数据"}

        ratio = bill.valley_consumption / bill.total_consumption * 100 if bill.total_consumption > 0 else 0
        return {
            "value": round(ratio, 2),
            "unit": "%",
            "formula": "valley_consumption / total_consumption * 100",
            "data_source": {
                "valley_consumption": bill.valley_consumption,
                "total_consumption": bill.total_consumption
            }
        }

    # ==================== B. 负荷特性指标 ====================

    async def calc_load_metrics(self, start_date: date, end_date: date) -> Dict:
        """B1-B6. 计算所有负荷特性指标
        包括: P_max, P_avg, P_min, 日负荷率, 峰谷差, 负荷标准差
        数据来源: load_curves表
        """
        result = await self.db.execute(
            select(LoadCurve.load_value)
            .where(LoadCurve.date >= start_date)
            .where(LoadCurve.date <= end_date)
        )
        loads = [r[0] for r in result.fetchall() if r[0] is not None]

        if not loads:
            return {"error": "无负荷数据", "date_range": f"{start_date} to {end_date}"}

        P_max = max(loads)
        P_min = min(loads)
        P_avg = statistics.mean(loads)
        load_rate = P_avg / P_max if P_max > 0 else 0
        peak_valley_diff = P_max - P_min
        load_std = statistics.stdev(loads) if len(loads) > 1 else 0

        return {
            "P_max": {
                "value": round(P_max, 2),
                "unit": "kW",
                "formula": "max(load_value)",
                "description": "最大负荷"
            },
            "P_avg": {
                "value": round(P_avg, 2),
                "unit": "kW",
                "formula": "sum(load_value) / count(load_value)",
                "description": "平均负荷"
            },
            "P_min": {
                "value": round(P_min, 2),
                "unit": "kW",
                "formula": "min(load_value)",
                "description": "最小负荷"
            },
            "load_rate": {
                "value": round(load_rate, 4),
                "unit": "-",
                "formula": "P_avg / P_max",
                "description": "日负荷率",
                "typical_range": "0.65-0.85"
            },
            "peak_valley_diff": {
                "value": round(peak_valley_diff, 2),
                "unit": "kW",
                "formula": "P_max - P_min",
                "description": "峰谷差"
            },
            "load_std": {
                "value": round(load_std, 2),
                "unit": "kW",
                "formula": "sqrt(sum((load - P_avg)^2) / n)",
                "description": "负荷标准差"
            },
            "data_source": {
                "table": "load_curves",
                "date_range": f"{start_date} to {end_date}",
                "data_points": len(loads)
            }
        }

    # ==================== C. 电费结构指标 ====================

    async def calc_cost_structure(self, month: str) -> Dict:
        """C1-C3. 计算电费结构占比
        """
        result = await self.db.execute(
            select(ElectricityBill).where(ElectricityBill.month == month)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return {"error": "无电费数据", "month": month}

        total = bill.total_cost
        return {
            "market_ratio": {
                "value": round(bill.market_purchase_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "market_purchase_fee / total_cost * 100",
                "typical_range": "65%-72%"
            },
            "transmission_ratio": {
                "value": round(bill.transmission_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "transmission_fee / total_cost * 100",
                "typical_range": "22%-25%"
            },
            "basic_fee_ratio": {
                "value": round(bill.basic_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "basic_fee / total_cost * 100"
            },
            "system_operation_ratio": {
                "value": round(bill.system_operation_fee / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "system_operation_fee / total_cost * 100",
                "typical_range": "3%-5%"
            },
            "government_fund_ratio": {
                "value": round(bill.government_fund / total * 100, 2) if total > 0 else 0,
                "unit": "%",
                "formula": "government_fund / total_cost * 100",
                "typical_range": "3%-4%"
            },
            "data_source": {
                "table": "electricity_bills",
                "month": month,
                "total_cost": total
            }
        }

    # ==================== D. 峰谷转移潜力指标 ====================

    async def calc_transfer_potential(self) -> Dict:
        """D1-D3. 计算峰谷转移潜力
        """
        # 获取可调节负荷
        result = await self.db.execute(
            select(AdjustableLoad).where(AdjustableLoad.is_active == True)
        )
        loads = result.scalars().all()

        transferable_load = sum(
            load.rated_power * load.adjustable_ratio / 100
            for load in loads
        )

        # 获取峰谷电价差
        price_result = await self.db.execute(select(ElectricityPrice))
        prices = {p.period_type.value: p.price for p in price_result.scalars().all()}

        peak_price = prices.get("peak", 0.85)  # 默认值
        valley_price = prices.get("valley", 0.35)  # 默认值
        price_spread = peak_price - valley_price

        # 获取配置参数
        config_result = await self.db.execute(
            select(VPPConfig).where(VPPConfig.config_key == "daily_shift_hours")
        )
        config = config_result.scalar_one_or_none()
        daily_shift_hours = config.config_value if config else 4  # 默认4小时

        annual_benefit = transferable_load * daily_shift_hours * 365 * price_spread

        return {
            "transferable_load": {
                "value": round(transferable_load, 2),
                "unit": "kW",
                "formula": "sum(rated_power * adjustable_ratio / 100)",
                "description": "可转移负荷量"
            },
            "price_spread": {
                "value": round(price_spread, 4),
                "unit": "元/kWh",
                "formula": "peak_price - valley_price",
                "data_source": {
                    "peak_price": peak_price,
                    "valley_price": valley_price
                }
            },
            "annual_transfer_benefit": {
                "value": round(annual_benefit, 2),
                "unit": "元/年",
                "formula": "transferable_load * daily_shift_hours * 365 * price_spread",
                "parameters": {
                    "daily_shift_hours": daily_shift_hours
                }
            },
            "data_source": {
                "adjustable_loads_count": len(loads),
                "price_table": "electricity_prices"
            }
        }

    # ==================== E. 需量优化指标 ====================

    async def calc_demand_optimization(self, P_max: float) -> Dict:
        """E1-E2. 计算需量优化潜力
        """
        # 获取配置参数
        config_result = await self.db.execute(
            select(VPPConfig).where(VPPConfig.config_key.in_(["target_demand_ratio", "demand_price"]))
        )
        configs = {c.config_key: c.config_value for c in config_result.scalars().all()}

        target_ratio = configs.get("target_demand_ratio", 0.9)  # 默认削减10%
        demand_price = configs.get("demand_price", 40)  # 默认40元/kW/月

        target_demand = P_max * target_ratio
        peak_reduction = P_max - target_demand
        annual_benefit = peak_reduction * demand_price * 12

        return {
            "peak_reduction_potential": {
                "value": round(peak_reduction, 2),
                "unit": "kW",
                "formula": "P_max - target_demand",
                "description": "削峰空间"
            },
            "demand_optimization_benefit": {
                "value": round(annual_benefit, 2),
                "unit": "元/年",
                "formula": "peak_reduction * demand_price * 12",
                "description": "需量优化年收益"
            },
            "parameters": {
                "P_max": P_max,
                "target_demand": round(target_demand, 2),
                "target_ratio": target_ratio,
                "demand_price": demand_price
            }
        }

    # ==================== F. 虚拟电厂收益指标 ====================

    async def calc_vpp_revenue(self, adjustable_capacity: float) -> Dict:
        """F1-F4. 计算VPP各类收益
        """
        # 获取配置参数
        config_result = await self.db.execute(select(VPPConfig))
        configs = {c.config_key: c.config_value for c in config_result.scalars().all()}

        # 需求响应收益
        response_count = configs.get("response_count", 20)  # 年响应次数
        response_price = configs.get("response_price", 4)  # 响应补贴 元/kW
        demand_response_revenue = adjustable_capacity * response_count * response_price

        # 辅助服务收益
        service_hours = configs.get("service_hours", 200)  # 年服务小时数
        service_price = configs.get("service_price", 0.75)  # 服务价格 元/kW·h
        ancillary_service_revenue = adjustable_capacity * service_hours * service_price

        # 现货市场套利
        arbitrage_hours = configs.get("arbitrage_hours", 500)  # 年套利小时数
        price_spread_spot = configs.get("price_spread_spot", 0.3)  # 现货价差
        spot_arbitrage_revenue = adjustable_capacity * arbitrage_hours * price_spread_spot

        total_vpp_revenue = demand_response_revenue + ancillary_service_revenue + spot_arbitrage_revenue

        return {
            "demand_response_revenue": {
                "value": round(demand_response_revenue, 2),
                "unit": "元/年",
                "formula": "adjustable_capacity * response_count * response_price",
                "parameters": {
                    "adjustable_capacity": adjustable_capacity,
                    "response_count": response_count,
                    "response_price": response_price
                }
            },
            "ancillary_service_revenue": {
                "value": round(ancillary_service_revenue, 2),
                "unit": "元/年",
                "formula": "adjustable_capacity * service_hours * service_price",
                "parameters": {
                    "service_hours": service_hours,
                    "service_price": service_price
                }
            },
            "spot_arbitrage_revenue": {
                "value": round(spot_arbitrage_revenue, 2),
                "unit": "元/年",
                "formula": "adjustable_capacity * arbitrage_hours * price_spread_spot",
                "parameters": {
                    "arbitrage_hours": arbitrage_hours,
                    "price_spread_spot": price_spread_spot
                }
            },
            "total_vpp_revenue": {
                "value": round(total_vpp_revenue, 2),
                "unit": "元/年",
                "formula": "demand_response + ancillary_service + spot_arbitrage"
            }
        }

    # ==================== G. 投资回报指标 ====================

    async def calc_roi(self, annual_benefit: float) -> Dict:
        """G1-G4. 计算投资回报指标
        """
        config_result = await self.db.execute(
            select(VPPConfig).where(VPPConfig.config_key.in_([
                "monitoring_system_cost", "control_system_cost",
                "platform_cost", "other_cost"
            ]))
        )
        configs = {c.config_key: c.config_value for c in config_result.scalars().all()}

        monitoring_cost = configs.get("monitoring_system_cost", 500000)
        control_cost = configs.get("control_system_cost", 800000)
        platform_cost = configs.get("platform_cost", 200000)
        other_cost = configs.get("other_cost", 100000)

        total_investment = monitoring_cost + control_cost + platform_cost + other_cost
        payback_period = total_investment / annual_benefit if annual_benefit > 0 else float('inf')
        roi = annual_benefit / total_investment * 100 if total_investment > 0 else 0

        return {
            "total_investment": {
                "value": round(total_investment, 2),
                "unit": "元",
                "formula": "monitoring + control + platform + other",
                "breakdown": {
                    "monitoring_system": monitoring_cost,
                    "control_system": control_cost,
                    "platform": platform_cost,
                    "other": other_cost
                }
            },
            "annual_total_benefit": {
                "value": round(annual_benefit, 2),
                "unit": "元/年"
            },
            "payback_period": {
                "value": round(payback_period, 2),
                "unit": "年",
                "formula": "total_investment / annual_benefit"
            },
            "roi": {
                "value": round(roi, 2),
                "unit": "%",
                "formula": "annual_benefit / total_investment * 100"
            }
        }

    # ==================== 综合分析报告 ====================

    async def generate_full_analysis(
        self,
        months: List[str],
        start_date: date,
        end_date: date
    ) -> Dict:
        """生成完整的VPP方案分析报告
        汇总所有指标及其数据来源和计算公式
        """
        # 获取负荷指标
        load_metrics = await self.calc_load_metrics(start_date, end_date)
        P_max = load_metrics.get("P_max", {}).get("value", 0)

        # 获取峰谷转移潜力
        transfer = await self.calc_transfer_potential()
        transferable_load = transfer.get("transferable_load", {}).get("value", 0)

        # 获取需量优化
        demand_opt = await self.calc_demand_optimization(P_max)

        # 获取VPP收益
        vpp_revenue = await self.calc_vpp_revenue(transferable_load)

        # 计算年总收益
        annual_transfer_benefit = transfer.get("annual_transfer_benefit", {}).get("value", 0)
        demand_benefit = demand_opt.get("demand_optimization_benefit", {}).get("value", 0)
        total_vpp = vpp_revenue.get("total_vpp_revenue", {}).get("value", 0)
        annual_total_benefit = annual_transfer_benefit + demand_benefit + total_vpp

        # 计算ROI
        roi = await self.calc_roi(annual_total_benefit)

        # 电费结构 (使用最近月份)
        cost_structure = await self.calc_cost_structure(months[-1]) if months else {}

        return {
            "analysis_period": {
                "months": months,
                "load_data_range": f"{start_date} to {end_date}"
            },
            "electricity_usage": {
                "average_price": await self.calc_average_price(months[-1]) if months else {},
                "fluctuation_rate": await self.calc_fluctuation_rate(months),
                "peak_ratio": await self.calc_peak_ratio(months[-1]) if months else {},
                "valley_ratio": await self.calc_valley_ratio(months[-1]) if months else {}
            },
            "load_characteristics": load_metrics,
            "cost_structure": cost_structure,
            "transfer_potential": transfer,
            "demand_optimization": demand_opt,
            "vpp_revenue": vpp_revenue,
            "investment_return": roi,
            "summary": {
                "annual_total_benefit": {
                    "value": round(annual_total_benefit, 2),
                    "unit": "元/年",
                    "formula": "transfer_benefit + demand_benefit + vpp_revenue",
                    "breakdown": {
                        "峰谷转移收益": annual_transfer_benefit,
                        "需量优化收益": demand_benefit,
                        "VPP参与收益": total_vpp
                    }
                },
                "payback_period": roi.get("payback_period"),
                "roi": roi.get("roi")
            }
        }
```

**Step 2: 运行测试验证计算器可导入**

```bash
cd D:\mytest1\backend
python -c "from app.services.vpp_calculator import VPPCalculator; print('VPPCalculator imported successfully')"
```

**Step 3: Commit**

```bash
git add backend/app/services/vpp_calculator.py
git commit -m "feat: add VPP calculator service with all metrics and formulas"
```

---

### Task 3: 创建VPP方案API接口

**Files:**
- Create: `backend/app/api/v1/vpp.py`
- Modify: `backend/app/api/v1/__init__.py`

**Step 1: 创建VPP API路由**

```python
# backend/app/api/v1/vpp.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel

from app.api.deps import get_db
from app.services.vpp_calculator import VPPCalculator

router = APIRouter()

class AnalysisRequest(BaseModel):
    months: List[str]  # ["2025-01", "2025-02", ...]
    start_date: date
    end_date: date

@router.post("/analysis", summary="生成VPP方案完整分析")
async def generate_analysis(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    生成完整的VPP方案分析报告
    所有数据指标均包含:
    - value: 计算值
    - unit: 单位
    - formula: 计算公式
    - data_source: 数据来源说明
    """
    calculator = VPPCalculator(db)
    result = await calculator.generate_full_analysis(
        months=request.months,
        start_date=request.start_date,
        end_date=request.end_date
    )
    return {"code": 0, "message": "success", "data": result}

@router.get("/load-metrics", summary="获取负荷特性指标")
async def get_load_metrics(
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取负荷特性指标 (P_max, P_avg, P_min, 负荷率, 峰谷差, 标准差)
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_load_metrics(start_date, end_date)
    return {"code": 0, "message": "success", "data": result}

@router.get("/cost-structure/{month}", summary="获取电费结构分析")
async def get_cost_structure(
    month: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定月份的电费结构分析
    month格式: YYYY-MM
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_cost_structure(month)
    return {"code": 0, "message": "success", "data": result}

@router.get("/transfer-potential", summary="获取峰谷转移潜力")
async def get_transfer_potential(
    db: AsyncSession = Depends(get_db)
):
    """
    获取峰谷转移潜力分析
    包含可转移负荷量、峰谷电价差、年收益潜力
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_transfer_potential()
    return {"code": 0, "message": "success", "data": result}

@router.get("/vpp-revenue", summary="获取VPP收益测算")
async def get_vpp_revenue(
    adjustable_capacity: float = Query(..., description="可调节容量(kW)"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取VPP各类收益测算
    包含需求响应、辅助服务、现货套利收益
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_vpp_revenue(adjustable_capacity)
    return {"code": 0, "message": "success", "data": result}

@router.get("/roi", summary="获取投资回报分析")
async def get_roi(
    annual_benefit: float = Query(..., description="年收益(元)"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取投资回报分析
    包含总投资、回收期、ROI
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_roi(annual_benefit)
    return {"code": 0, "message": "success", "data": result}

@router.get("/formula-reference", summary="获取所有计算公式参考")
async def get_formula_reference():
    """
    返回所有指标的计算公式和数据来源参考
    用于文档展示和数据验证
    """
    return {
        "code": 0,
        "message": "success",
        "data": {
            "用电规模指标": {
                "A1_平均电价": {
                    "formula": "total_cost / total_consumption",
                    "unit": "元/kWh",
                    "source_table": "electricity_bills"
                },
                "A2_波动率": {
                    "formula": "(max - min) / avg * 100",
                    "unit": "%",
                    "source_table": "electricity_bills"
                },
                "A3_峰段占比": {
                    "formula": "peak_consumption / total_consumption * 100",
                    "unit": "%",
                    "source_table": "electricity_bills"
                },
                "A4_谷段占比": {
                    "formula": "valley_consumption / total_consumption * 100",
                    "unit": "%",
                    "source_table": "electricity_bills"
                }
            },
            "负荷特性指标": {
                "B1_最大负荷": {
                    "formula": "max(load_value)",
                    "unit": "kW",
                    "source_table": "load_curves"
                },
                "B2_平均负荷": {
                    "formula": "sum(load_value) / count",
                    "unit": "kW",
                    "source_table": "load_curves"
                },
                "B3_最小负荷": {
                    "formula": "min(load_value)",
                    "unit": "kW",
                    "source_table": "load_curves"
                },
                "B4_日负荷率": {
                    "formula": "P_avg / P_max",
                    "unit": "-",
                    "typical_range": "0.65-0.85"
                },
                "B5_峰谷差": {
                    "formula": "P_max - P_min",
                    "unit": "kW"
                },
                "B6_负荷标准差": {
                    "formula": "sqrt(sum((load - avg)^2) / n)",
                    "unit": "kW"
                }
            },
            "电费结构指标": {
                "C1_市场化购电占比": {
                    "formula": "market_purchase_fee / total_cost * 100",
                    "unit": "%",
                    "typical_range": "65%-72%"
                },
                "C2_输配电费占比": {
                    "formula": "transmission_fee / total_cost * 100",
                    "unit": "%",
                    "typical_range": "22%-25%"
                },
                "C3_基本电费占比": {
                    "formula": "basic_fee / total_cost * 100",
                    "unit": "%"
                }
            },
            "峰谷转移指标": {
                "D1_可转移负荷": {
                    "formula": "sum(rated_power * adjustable_ratio / 100)",
                    "unit": "kW",
                    "source_table": "adjustable_loads"
                },
                "D2_峰谷电价差": {
                    "formula": "peak_price - valley_price",
                    "unit": "元/kWh",
                    "source_table": "electricity_prices"
                },
                "D3_年收益潜力": {
                    "formula": "transferable_load * daily_shift_hours * 365 * price_spread",
                    "unit": "元/年"
                }
            },
            "VPP收益指标": {
                "F1_需求响应收益": {
                    "formula": "capacity * response_count * response_price",
                    "unit": "元/年"
                },
                "F2_辅助服务收益": {
                    "formula": "capacity * service_hours * service_price",
                    "unit": "元/年"
                },
                "F3_现货套利收益": {
                    "formula": "capacity * arbitrage_hours * price_spread",
                    "unit": "元/年"
                },
                "F4_VPP总收益": {
                    "formula": "F1 + F2 + F3",
                    "unit": "元/年"
                }
            },
            "投资回报指标": {
                "G1_总投资": {
                    "formula": "monitoring + control + platform + other",
                    "unit": "元"
                },
                "G2_年总收益": {
                    "formula": "transfer_benefit + demand_benefit + vpp_revenue",
                    "unit": "元/年"
                },
                "G3_回收期": {
                    "formula": "total_investment / annual_benefit",
                    "unit": "年"
                },
                "G4_ROI": {
                    "formula": "annual_benefit / total_investment * 100",
                    "unit": "%"
                }
            }
        }
    }
```

**Step 2: 注册VPP路由**

在 `backend/app/api/v1/__init__.py` 中添加:
```python
from app.api.v1.vpp import router as vpp_router

# 在api_router中添加
api_router.include_router(vpp_router, prefix="/vpp", tags=["VPP方案分析"])
```

**Step 3: 验证API可访问**

```bash
curl http://localhost:18080/api/v1/vpp/formula-reference
```

**Step 4: Commit**

```bash
git add backend/app/api/v1/vpp.py backend/app/api/v1/__init__.py
git commit -m "feat: add VPP analysis API endpoints with formula reference"
```

---

### Task 4: 初始化测试数据和配置

**Files:**
- Create: `backend/app/db/init_vpp_data.py`

**Step 1: 创建VPP数据初始化脚本**

```python
# backend/app/db/init_vpp_data.py
from datetime import date, time, datetime, timedelta
import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.vpp_data import (
    ElectricityBill, LoadCurve, ElectricityPrice,
    AdjustableLoad, VPPConfig, TimePeriodType
)

async def init_vpp_test_data(db: AsyncSession):
    """初始化VPP测试数据"""

    # 1. 初始化电费清单数据 (基于方案1文档中的真实数据)
    bills_data = [
        {"month": "2025-01", "total_consumption": 20970000, "total_cost": 14230000,
         "peak_consumption": 6291000, "valley_consumption": 6291000, "flat_consumption": 8388000,
         "max_demand": 39900, "power_factor": 0.94, "basic_fee": 1200000,
         "market_purchase_fee": 9800000, "transmission_fee": 3100000,
         "system_operation_fee": 500000, "government_fund": 430000},
        {"month": "2025-03", "total_consumption": 24850000, "total_cost": 17170000,
         "peak_consumption": 7455000, "valley_consumption": 7455000, "flat_consumption": 9940000,
         "max_demand": 42000, "power_factor": 0.95, "basic_fee": 1200000,
         "market_purchase_fee": 11800000, "transmission_fee": 3700000,
         "system_operation_fee": 600000, "government_fund": 520000},
        {"month": "2025-06", "total_consumption": 26010000, "total_cost": 18130000,
         "peak_consumption": 7803000, "valley_consumption": 7803000, "flat_consumption": 10404000,
         "max_demand": 41500, "power_factor": 0.94, "basic_fee": 1200000,
         "market_purchase_fee": 12500000, "transmission_fee": 3900000,
         "system_operation_fee": 620000, "government_fund": 550000},
        {"month": "2025-08", "total_consumption": 28070000, "total_cost": 19710000,
         "peak_consumption": 8421000, "valley_consumption": 8421000, "flat_consumption": 11228000,
         "max_demand": 42500, "power_factor": 0.95, "basic_fee": 1200000,
         "market_purchase_fee": 13700000, "transmission_fee": 4200000,
         "system_operation_fee": 680000, "government_fund": 600000},
        {"month": "2025-10", "total_consumption": 27240000, "total_cost": 18430000,
         "peak_consumption": 8172000, "valley_consumption": 8172000, "flat_consumption": 10896000,
         "max_demand": 41800, "power_factor": 0.94, "basic_fee": 1200000,
         "market_purchase_fee": 12800000, "transmission_fee": 3950000,
         "system_operation_fee": 650000, "government_fund": 580000},
    ]

    for bill_data in bills_data:
        bill = ElectricityBill(**bill_data)
        db.add(bill)

    # 2. 初始化电价配置
    prices_data = [
        {"period_type": TimePeriodType.PEAK, "price": 0.85,
         "start_time": time(8, 0), "end_time": time(11, 0), "effective_date": date(2025, 1, 1)},
        {"period_type": TimePeriodType.PEAK, "price": 0.85,
         "start_time": time(18, 0), "end_time": time(21, 0), "effective_date": date(2025, 1, 1)},
        {"period_type": TimePeriodType.VALLEY, "price": 0.35,
         "start_time": time(23, 0), "end_time": time(7, 0), "effective_date": date(2025, 1, 1)},
        {"period_type": TimePeriodType.FLAT, "price": 0.55,
         "start_time": time(7, 0), "end_time": time(8, 0), "effective_date": date(2025, 1, 1)},
        {"period_type": TimePeriodType.FLAT, "price": 0.55,
         "start_time": time(11, 0), "end_time": time(18, 0), "effective_date": date(2025, 1, 1)},
        {"period_type": TimePeriodType.FLAT, "price": 0.55,
         "start_time": time(21, 0), "end_time": time(23, 0), "effective_date": date(2025, 1, 1)},
    ]

    for price_data in prices_data:
        price = ElectricityPrice(**price_data)
        db.add(price)

    # 3. 初始化可调节负荷资源 (基于钢帘线企业典型设备)
    loads_data = [
        {"equipment_name": "拉丝机组A", "equipment_type": "生产设备",
         "rated_power": 2000, "adjustable_ratio": 30, "response_time": 15, "adjustment_cost": 500},
        {"equipment_name": "拉丝机组B", "equipment_type": "生产设备",
         "rated_power": 2000, "adjustable_ratio": 30, "response_time": 15, "adjustment_cost": 500},
        {"equipment_name": "热处理炉", "equipment_type": "热处理设备",
         "rated_power": 5000, "adjustable_ratio": 20, "response_time": 30, "adjustment_cost": 1000},
        {"equipment_name": "中央空调系统", "equipment_type": "辅助设备",
         "rated_power": 3000, "adjustable_ratio": 50, "response_time": 5, "adjustment_cost": 100},
        {"equipment_name": "压缩空气系统", "equipment_type": "辅助设备",
         "rated_power": 1500, "adjustable_ratio": 40, "response_time": 10, "adjustment_cost": 200},
        {"equipment_name": "水泵系统", "equipment_type": "辅助设备",
         "rated_power": 800, "adjustable_ratio": 30, "response_time": 5, "adjustment_cost": 50},
        {"equipment_name": "照明系统", "equipment_type": "照明",
         "rated_power": 500, "adjustable_ratio": 60, "response_time": 1, "adjustment_cost": 20},
    ]

    for load_data in loads_data:
        load = AdjustableLoad(**load_data, is_active=True)
        db.add(load)

    # 4. 初始化VPP配置参数
    configs_data = [
        {"config_key": "daily_shift_hours", "config_value": 4,
         "config_unit": "小时", "description": "每日峰谷转移小时数"},
        {"config_key": "target_demand_ratio", "config_value": 0.9,
         "config_unit": "-", "description": "目标需量比例(削减10%)"},
        {"config_key": "demand_price", "config_value": 40,
         "config_unit": "元/kW/月", "description": "需量电价"},
        {"config_key": "response_count", "config_value": 20,
         "config_unit": "次/年", "description": "年需求响应次数"},
        {"config_key": "response_price", "config_value": 4,
         "config_unit": "元/kW", "description": "需求响应补贴单价"},
        {"config_key": "service_hours", "config_value": 200,
         "config_unit": "小时/年", "description": "辅助服务年小时数"},
        {"config_key": "service_price", "config_value": 0.75,
         "config_unit": "元/kW·h", "description": "辅助服务价格"},
        {"config_key": "arbitrage_hours", "config_value": 500,
         "config_unit": "小时/年", "description": "现货套利年小时数"},
        {"config_key": "price_spread_spot", "config_value": 0.3,
         "config_unit": "元/kWh", "description": "现货市场价差"},
        {"config_key": "monitoring_system_cost", "config_value": 500000,
         "config_unit": "元", "description": "监测系统投资"},
        {"config_key": "control_system_cost", "config_value": 800000,
         "config_unit": "元", "description": "控制系统投资"},
        {"config_key": "platform_cost", "config_value": 200000,
         "config_unit": "元", "description": "平台建设投资"},
        {"config_key": "other_cost", "config_value": 100000,
         "config_unit": "元", "description": "其他投资"},
    ]

    for config_data in configs_data:
        config = VPPConfig(**config_data)
        db.add(config)

    # 5. 生成负荷曲线数据 (模拟15分钟间隔数据)
    base_load = 35000  # 基础负荷 35MW
    start_date = date(2025, 10, 1)

    for day_offset in range(30):  # 生成30天数据
        current_date = start_date + timedelta(days=day_offset)
        is_workday = current_date.weekday() < 5

        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                timestamp = datetime(
                    current_date.year, current_date.month, current_date.day,
                    hour, minute
                )

                # 确定时段类型
                if 8 <= hour < 11 or 18 <= hour < 21:
                    period_type = TimePeriodType.PEAK
                    load_factor = 1.15 if is_workday else 1.05
                elif 23 <= hour or hour < 7:
                    period_type = TimePeriodType.VALLEY
                    load_factor = 0.85
                else:
                    period_type = TimePeriodType.FLAT
                    load_factor = 1.0

                # 计算负荷值
                variation = random.uniform(-0.05, 0.05)
                load_value = base_load * load_factor * (1 + variation)

                if is_workday:
                    load_value *= 1.1

                curve = LoadCurve(
                    timestamp=timestamp,
                    load_value=round(load_value, 2),
                    date=current_date,
                    time_period=period_type,
                    is_workday=is_workday
                )
                db.add(curve)

    await db.commit()
    print("VPP test data initialized successfully!")

async def clear_vpp_data(db: AsyncSession):
    """清除VPP数据"""
    from sqlalchemy import delete

    await db.execute(delete(LoadCurve))
    await db.execute(delete(ElectricityBill))
    await db.execute(delete(ElectricityPrice))
    await db.execute(delete(AdjustableLoad))
    await db.execute(delete(VPPConfig))
    await db.commit()
    print("VPP data cleared!")
```

**Step 2: 添加初始化命令到主程序**

在启动脚本或CLI中添加初始化命令调用。

**Step 3: Commit**

```bash
git add backend/app/db/init_vpp_data.py
git commit -m "feat: add VPP test data initialization script with realistic values"
```

---

### Task 5: 前端VPP方案展示页面

**Files:**
- Create: `frontend/src/views/vpp/VPPAnalysis.vue`
- Create: `frontend/src/api/modules/vpp.ts`

**Step 1: 创建VPP API模块**

```typescript
// frontend/src/api/modules/vpp.ts
import request from '../request'

export interface AnalysisRequest {
  months: string[]
  start_date: string
  end_date: string
}

export const vppApi = {
  // 生成完整分析
  generateAnalysis(data: AnalysisRequest) {
    return request.post('/v1/vpp/analysis', data)
  },

  // 获取负荷指标
  getLoadMetrics(startDate: string, endDate: string) {
    return request.get('/v1/vpp/load-metrics', {
      params: { start_date: startDate, end_date: endDate }
    })
  },

  // 获取电费结构
  getCostStructure(month: string) {
    return request.get(`/v1/vpp/cost-structure/${month}`)
  },

  // 获取峰谷转移潜力
  getTransferPotential() {
    return request.get('/v1/vpp/transfer-potential')
  },

  // 获取VPP收益
  getVPPRevenue(adjustableCapacity: number) {
    return request.get('/v1/vpp/vpp-revenue', {
      params: { adjustable_capacity: adjustableCapacity }
    })
  },

  // 获取ROI分析
  getROI(annualBenefit: number) {
    return request.get('/v1/vpp/roi', {
      params: { annual_benefit: annualBenefit }
    })
  },

  // 获取公式参考
  getFormulaReference() {
    return request.get('/v1/vpp/formula-reference')
  }
}
```

**Step 2: 创建VPP分析页面**

```vue
<!-- frontend/src/views/vpp/VPPAnalysis.vue -->
<template>
  <div class="vpp-analysis">
    <el-card class="header-card">
      <h2>虚拟电厂方案分析</h2>
      <p>所有数据指标均包含计算公式和数据来源</p>
    </el-card>

    <!-- 分析参数配置 -->
    <el-card class="config-card">
      <template #header>
        <span>分析参数配置</span>
      </template>
      <el-form :inline="true">
        <el-form-item label="分析月份">
          <el-date-picker
            v-model="analysisMonths"
            type="months"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
            multiple
          />
        </el-form-item>
        <el-form-item label="负荷数据范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runAnalysis" :loading="loading">
            生成分析报告
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 分析结果展示 -->
    <template v-if="analysisResult">
      <!-- 用电规模指标 -->
      <el-card class="metric-card">
        <template #header>
          <span>A. 用电规模指标</span>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="平均电价">
            <MetricDisplay :metric="analysisResult.electricity_usage?.average_price" />
          </el-descriptions-item>
          <el-descriptions-item label="月度波动率">
            <MetricDisplay :metric="analysisResult.electricity_usage?.fluctuation_rate" />
          </el-descriptions-item>
          <el-descriptions-item label="峰段用电占比">
            <MetricDisplay :metric="analysisResult.electricity_usage?.peak_ratio" />
          </el-descriptions-item>
          <el-descriptions-item label="谷段用电占比">
            <MetricDisplay :metric="analysisResult.electricity_usage?.valley_ratio" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 负荷特性指标 -->
      <el-card class="metric-card">
        <template #header>
          <span>B. 负荷特性指标</span>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="最大负荷 (P_max)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.P_max" />
          </el-descriptions-item>
          <el-descriptions-item label="平均负荷 (P_avg)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.P_avg" />
          </el-descriptions-item>
          <el-descriptions-item label="最小负荷 (P_min)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.P_min" />
          </el-descriptions-item>
          <el-descriptions-item label="日负荷率">
            <MetricDisplay :metric="analysisResult.load_characteristics?.load_rate" />
          </el-descriptions-item>
          <el-descriptions-item label="峰谷差">
            <MetricDisplay :metric="analysisResult.load_characteristics?.peak_valley_diff" />
          </el-descriptions-item>
          <el-descriptions-item label="负荷标准差">
            <MetricDisplay :metric="analysisResult.load_characteristics?.load_std" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 收益汇总 -->
      <el-card class="summary-card">
        <template #header>
          <span>收益汇总与投资回报</span>
        </template>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-statistic
              title="年总收益"
              :value="analysisResult.summary?.annual_total_benefit?.value"
              suffix="元/年"
            />
            <div class="formula-text">
              公式: {{ analysisResult.summary?.annual_total_benefit?.formula }}
            </div>
          </el-col>
          <el-col :span="8">
            <el-statistic
              title="投资回收期"
              :value="analysisResult.investment_return?.payback_period?.value"
              suffix="年"
            />
          </el-col>
          <el-col :span="8">
            <el-statistic
              title="投资收益率"
              :value="analysisResult.investment_return?.roi?.value"
              suffix="%"
            />
          </el-col>
        </el-row>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { vppApi } from '@/api/modules/vpp'
import MetricDisplay from '@/components/MetricDisplay.vue'

const loading = ref(false)
const analysisMonths = ref(['2025-01', '2025-03', '2025-06', '2025-08', '2025-10'])
const dateRange = ref(['2025-10-01', '2025-10-30'])
const analysisResult = ref(null)

const runAnalysis = async () => {
  loading.value = true
  try {
    const response = await vppApi.generateAnalysis({
      months: analysisMonths.value,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1]
    })
    analysisResult.value = response.data.data
  } catch (error) {
    console.error('Analysis failed:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.vpp-analysis {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;
}

.config-card {
  margin-bottom: 20px;
}

.metric-card {
  margin-bottom: 20px;
}

.summary-card {
  margin-bottom: 20px;
}

.formula-text {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>
```

**Step 3: 创建指标展示组件**

```vue
<!-- frontend/src/components/MetricDisplay.vue -->
<template>
  <div class="metric-display" v-if="metric">
    <div class="value">{{ metric.value }} {{ metric.unit }}</div>
    <el-tooltip placement="top">
      <template #content>
        <div>
          <p><strong>计算公式:</strong> {{ metric.formula }}</p>
          <p v-if="metric.data_source">
            <strong>数据来源:</strong>
            {{ JSON.stringify(metric.data_source, null, 2) }}
          </p>
          <p v-if="metric.typical_range">
            <strong>典型范围:</strong> {{ metric.typical_range }}
          </p>
        </div>
      </template>
      <el-icon><InfoFilled /></el-icon>
    </el-tooltip>
  </div>
  <span v-else>-</span>
</template>

<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'

defineProps<{
  metric: {
    value: number
    unit: string
    formula: string
    data_source?: object
    typical_range?: string
  } | null
}>()
</script>

<style scoped>
.metric-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.value {
  font-weight: 500;
}
</style>
```

**Step 4: Commit**

```bash
git add frontend/src/api/modules/vpp.ts frontend/src/views/vpp/VPPAnalysis.vue frontend/src/components/MetricDisplay.vue
git commit -m "feat: add VPP analysis frontend with metric display and formula tooltips"
```

---

## 执行顺序总结

1. **Task 1**: 创建数据库表结构 - 定义所有源数据表
2. **Task 2**: 创建VPP计算服务 - 实现所有指标计算（含公式和数据来源）
3. **Task 3**: 创建API接口 - 暴露计算服务给前端
4. **Task 4**: 初始化测试数据 - 基于方案1文档的真实数据
5. **Task 5**: 前端展示页面 - 展示指标值、公式和数据来源

## 数据流示意

```
源数据表
├── electricity_bills (电费清单)
├── load_curves (负荷曲线)
├── electricity_prices (电价配置)
├── adjustable_loads (可调节负荷)
└── vpp_configs (VPP配置参数)
        │
        ▼
VPPCalculator (计算服务)
├── calc_average_price() → 公式: total_cost / total_consumption
├── calc_load_metrics() → 公式: max/min/avg(load_value)
├── calc_transfer_potential() → 公式: rated_power * adjustable_ratio
├── calc_vpp_revenue() → 公式: capacity * count * price
└── calc_roi() → 公式: investment / annual_benefit
        │
        ▼
API响应 (包含value, unit, formula, data_source)
        │
        ▼
前端展示 (带公式提示的指标卡片)
```
