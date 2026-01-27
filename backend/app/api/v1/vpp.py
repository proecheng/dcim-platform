"""
VPP Analysis API Endpoints
虚拟电厂方案分析接口

This module exposes the VPP calculator service through REST API endpoints.
All endpoints return data with formulas and data sources for transparency.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.services.vpp_calculator import VPPCalculator


router = APIRouter()


# ==================== Request Models ====================


class AnalysisRequest(BaseModel):
    """完整分析请求模型"""
    months: List[str] = Field(..., description="月份列表")
    start_date: date = Field(..., description="负荷数据开始日期")
    end_date: date = Field(..., description="负荷数据结束日期")


# ==================== API Endpoints ====================


@router.post("/analysis", summary="生成VPP方案完整分析")
async def generate_analysis(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    生成完整的VPP方案分析报告

    **功能说明:**
    - 综合计算所有VPP相关指标
    - 包含用电规模、负荷特性、电费结构、峰谷转移、需量优化、VPP收益、投资回报
    - 所有数据指标均包含计算公式和数据来源

    **请求示例:**
    ```json
    {
        "months": ["2025-01", "2025-03", "2025-06", "2025-08", "2025-10"],
        "start_date": "2025-10-01",
        "end_date": "2025-10-30"
    }
    ```

    **响应格式:**
    ```json
    {
        "code": 0,
        "message": "success",
        "data": {
            "analysis_period": {...},
            "electricity_usage": {...},
            "load_characteristics": {...},
            "cost_structure": {...},
            "transfer_potential": {...},
            "demand_optimization": {...},
            "vpp_revenue": {...},
            "investment_return": {...},
            "summary": {...}
        }
    }
    ```

    **返回说明:**
    每个指标包含:
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
    获取负荷特性指标 (B1-B6)

    **包含指标:**
    - P_max: 最大负荷 (kW)
    - P_avg: 平均负荷 (kW)
    - P_min: 最小负荷 (kW)
    - load_rate: 日负荷率 (典型范围: 0.65-0.85)
    - peak_valley_diff: 峰谷差 (kW)
    - load_std: 负荷标准差 (kW)

    **数据来源:** load_curves表

    **请求示例:**
    ```
    GET /api/v1/vpp/load-metrics?start_date=2025-10-01&end_date=2025-10-30
    ```

    **响应示例:**
    ```json
    {
        "code": 0,
        "message": "success",
        "data": {
            "P_max": {
                "value": 44317.5,
                "unit": "kW",
                "formula": "max(load_value)",
                "description": "最大负荷"
            },
            "P_avg": {...},
            "data_source": {
                "table": "load_curves",
                "date_range": "2025-10-01 to 2025-10-30",
                "data_points": 2880
            }
        }
    }
    ```
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_load_metrics(start_date, end_date)
    return {"code": 0, "message": "success", "data": result}


@router.get("/cost-structure/{month}", summary="获取电费结构分析")
async def get_cost_structure(
    month: str = Path(..., description="月份 (YYYY-MM格式)"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定月份的电费结构分析 (C1-C3)

    **包含指标:**
    - market_ratio: 市场化购电占比 (典型范围: 65%-72%)
    - transmission_ratio: 输配电费占比 (典型范围: 22%-25%)
    - basic_fee_ratio: 基本电费占比
    - system_operation_ratio: 系统运行费占比 (典型范围: 3%-5%)
    - government_fund_ratio: 政府性基金占比 (典型范围: 3%-4%)

    **数据来源:** electricity_bills表

    **Path参数:**
    - month: 月份，格式 YYYY-MM (例如: "2025-01")

    **请求示例:**
    ```
    GET /api/v1/vpp/cost-structure/2025-01
    ```

    **响应示例:**
    ```json
    {
        "code": 0,
        "message": "success",
        "data": {
            "market_ratio": {
                "value": 68.87,
                "unit": "%",
                "formula": "market_purchase_fee / total_cost * 100",
                "typical_range": "65%-72%"
            },
            "transmission_ratio": {...},
            "data_source": {
                "table": "electricity_bills",
                "month": "2025-01",
                "total_cost": 14230000
            }
        }
    }
    ```
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_cost_structure(month)
    return {"code": 0, "message": "success", "data": result}


@router.get("/transfer-potential", summary="获取峰谷转移潜力")
async def get_transfer_potential(
    db: AsyncSession = Depends(get_db)
):
    """
    获取峰谷转移潜力分析 (D1-D3)

    **包含指标:**
    - transferable_load: 可转移负荷量 (kW)
      - 公式: sum(rated_power * adjustable_ratio / 100)
      - 数据来源: adjustable_loads表
    - price_spread: 峰谷电价差 (元/kWh)
      - 公式: peak_price - valley_price
      - 数据来源: electricity_prices表
    - annual_transfer_benefit: 峰谷转移年收益潜力 (元/年)
      - 公式: transferable_load * daily_shift_hours * 365 * price_spread
      - 参数: daily_shift_hours (默认4小时，来自vpp_configs表)

    **数据来源:** adjustable_loads表, electricity_prices表, vpp_configs表

    **请求示例:**
    ```
    GET /api/v1/vpp/transfer-potential
    ```

    **响应示例:**
    ```json
    {
        "code": 0,
        "message": "success",
        "data": {
            "transferable_load": {
                "value": 4500.0,
                "unit": "kW",
                "formula": "sum(rated_power * adjustable_ratio / 100)",
                "description": "可转移负荷量"
            },
            "price_spread": {
                "value": 0.5,
                "unit": "元/kWh",
                "formula": "peak_price - valley_price",
                "data_source": {
                    "peak_price": 0.85,
                    "valley_price": 0.35
                }
            },
            "annual_transfer_benefit": {
                "value": 3285000.0,
                "unit": "元/年",
                "formula": "transferable_load * daily_shift_hours * 365 * price_spread",
                "parameters": {
                    "daily_shift_hours": 4
                }
            }
        }
    }
    ```
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
    获取VPP各类收益测算 (F1-F4)

    **包含指标:**
    - demand_response_revenue: 需求响应收益 (元/年)
      - 公式: adjustable_capacity * response_count * response_price
      - 参数: response_count (年响应次数, 默认20次), response_price (响应补贴, 默认4元/kW)
    - ancillary_service_revenue: 辅助服务收益 (元/年)
      - 公式: adjustable_capacity * service_hours * service_price
      - 参数: service_hours (年服务小时数, 默认200小时), service_price (服务价格, 默认0.75元/kW·h)
    - spot_arbitrage_revenue: 现货市场套利收益 (元/年)
      - 公式: adjustable_capacity * arbitrage_hours * price_spread_spot
      - 参数: arbitrage_hours (年套利小时数, 默认500小时), price_spread_spot (现货价差, 默认0.3元/kWh)
    - total_vpp_revenue: VPP年总收益 (元/年)
      - 公式: demand_response + ancillary_service + spot_arbitrage

    **数据来源:** vpp_configs表

    **Query参数:**
    - adjustable_capacity: 可调节容量，单位kW

    **请求示例:**
    ```
    GET /api/v1/vpp/vpp-revenue?adjustable_capacity=4500.0
    ```

    **响应示例:**
    ```json
    {
        "code": 0,
        "message": "success",
        "data": {
            "demand_response_revenue": {
                "value": 360000.0,
                "unit": "元/年",
                "formula": "adjustable_capacity * response_count * response_price",
                "parameters": {
                    "adjustable_capacity": 4500.0,
                    "response_count": 20,
                    "response_price": 4
                }
            },
            "ancillary_service_revenue": {...},
            "spot_arbitrage_revenue": {...},
            "total_vpp_revenue": {
                "value": 1710000.0,
                "unit": "元/年",
                "formula": "demand_response + ancillary_service + spot_arbitrage"
            }
        }
    }
    ```
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_vpp_revenue(adjustable_capacity)
    return {"code": 0, "message": "success", "data": result}


@router.get("/roi", summary="获取投资回报分析")
async def get_roi(
    annual_benefit: float = Query(..., description="年总收益(元)"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取投资回报分析 (G1-G4)

    **包含指标:**
    - total_investment: 总投资额 (元)
      - 公式: monitoring + control + platform + other
      - 包含明细: 监测系统、控制系统、平台建设、其他投资
    - annual_total_benefit: 年总收益 (元/年)
    - payback_period: 静态投资回收期 (年)
      - 公式: total_investment / annual_benefit
    - roi: 投资收益率 (%)
      - 公式: annual_benefit / total_investment * 100

    **数据来源:** vpp_configs表

    **Query参数:**
    - annual_benefit: 年总收益，单位元

    **请求示例:**
    ```
    GET /api/v1/vpp/roi?annual_benefit=5000000.0
    ```

    **响应示例:**
    ```json
    {
        "code": 0,
        "message": "success",
        "data": {
            "total_investment": {
                "value": 1600000.0,
                "unit": "元",
                "formula": "monitoring + control + platform + other",
                "breakdown": {
                    "monitoring_system": 500000,
                    "control_system": 800000,
                    "platform": 200000,
                    "other": 100000
                }
            },
            "annual_total_benefit": {
                "value": 5000000.0,
                "unit": "元/年"
            },
            "payback_period": {
                "value": 0.32,
                "unit": "年",
                "formula": "total_investment / annual_benefit"
            },
            "roi": {
                "value": 312.5,
                "unit": "%",
                "formula": "annual_benefit / total_investment * 100"
            }
        }
    }
    ```
    """
    calculator = VPPCalculator(db)
    result = await calculator.calc_roi(annual_benefit)
    return {"code": 0, "message": "success", "data": result}


@router.get("/formula-reference", summary="获取所有计算公式参考")
async def get_formula_reference():
    """
    返回所有指标的计算公式和数据来源参考

    **功能说明:**
    - 用于文档展示和数据验证
    - 包含所有VPP指标的公式、单位、数据来源表
    - 提供典型值范围参考

    **无需参数**

    **请求示例:**
    ```
    GET /api/v1/vpp/formula-reference
    ```

    **响应结构:**
    - 用电规模指标 (A1-A4)
    - 负荷特性指标 (B1-B6)
    - 电费结构指标 (C1-C3)
    - 峰谷转移指标 (D1-D3)
    - VPP收益指标 (F1-F4)
    - 投资回报指标 (G1-G4)
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
                    "typical_range": "65%-72%",
                    "source_table": "electricity_bills"
                },
                "C2_输配电费占比": {
                    "formula": "transmission_fee / total_cost * 100",
                    "unit": "%",
                    "typical_range": "22%-25%",
                    "source_table": "electricity_bills"
                },
                "C3_基本电费占比": {
                    "formula": "basic_fee / total_cost * 100",
                    "unit": "%",
                    "source_table": "electricity_bills"
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
                    "unit": "元/年",
                    "source_table": "vpp_configs",
                    "parameters": "daily_shift_hours (默认4小时)"
                }
            },
            "VPP收益指标": {
                "F1_需求响应收益": {
                    "formula": "capacity * response_count * response_price",
                    "unit": "元/年",
                    "source_table": "vpp_configs",
                    "parameters": "response_count (默认20次), response_price (默认4元/kW)"
                },
                "F2_辅助服务收益": {
                    "formula": "capacity * service_hours * service_price",
                    "unit": "元/年",
                    "source_table": "vpp_configs",
                    "parameters": "service_hours (默认200小时), service_price (默认0.75元/kW·h)"
                },
                "F3_现货套利收益": {
                    "formula": "capacity * arbitrage_hours * price_spread",
                    "unit": "元/年",
                    "source_table": "vpp_configs",
                    "parameters": "arbitrage_hours (默认500小时), price_spread_spot (默认0.3元/kWh)"
                },
                "F4_VPP总收益": {
                    "formula": "F1 + F2 + F3",
                    "unit": "元/年"
                }
            },
            "投资回报指标": {
                "G1_总投资": {
                    "formula": "monitoring + control + platform + other",
                    "unit": "元",
                    "source_table": "vpp_configs"
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
