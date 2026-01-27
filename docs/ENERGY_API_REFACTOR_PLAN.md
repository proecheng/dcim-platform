# Energy API 重构计划

## 背景

`backend/app/api/v1/energy.py` 文件有 **3428 行**，远超推荐的 800 行限制。
需要拆分为多个模块以提高可维护性。

## 目标结构

```
backend/app/api/v1/energy/
├── __init__.py          # 主路由聚合
├── devices.py           # 用电设备 CRUD (~300行)
├── realtime.py          # 实时电力数据 (~200行)
├── pue.py               # PUE 计算和趋势 (~200行)
├── statistics.py        # 能耗统计 (日/月) (~400行)
├── cost.py              # 电费计算 (~150行)
├── pricing.py           # 电价配置 CRUD (~150行)
├── suggestions.py       # 节能建议 (~500行)
├── topology.py          # 配电拓扑 (~300行)
├── exports.py           # 数据导出 (~250行)
├── transformers.py      # 变压器 CRUD (~150行)
├── meter_points.py      # 计量点 CRUD (~300行)
└── _common.py           # 共享依赖和工具函数
```

## 端点分组

### 1. devices.py (行 53-310)
- `GET /devices` - 获取用电设备列表
- `GET /devices/tree` - 获取用电设备树
- `POST /devices` - 创建用电设备
- `GET /devices/shiftable` - 获取可转移负荷设备
- `GET /devices/adjustable` - 获取可调节参数设备
- `POST /devices/generate-configs` - 批量生成设备配置
- `GET /devices/{device_id}` - 获取用电设备详情
- `PUT /devices/{device_id}` - 更新用电设备
- `DELETE /devices/{device_id}` - 删除用电设备

### 2. realtime.py (行 311-478)
- `GET /realtime` - 获取实时电力数据
- `GET /realtime/summary` - 获取电力汇总
- `GET /realtime/{device_id}` - 获取设备实时电力

### 3. pue.py (行 480-617)
- `GET /pue` - 获取当前 PUE
- `GET /pue/trend` - 获取 PUE 趋势

### 4. statistics.py (行 619-948)
- `GET /statistics/daily` - 获取日能耗统计
- `GET /statistics/monthly` - 获取月能耗统计
- `GET /statistics/summary` - 获取能耗汇总
- `GET /statistics/trend` - 获取能耗趋势
- `GET /statistics/comparison` - 获取能耗对比

### 5. cost.py (行 949-1064)
- `GET /cost/daily` - 获取日电费统计
- `GET /cost/monthly` - 获取月电费统计

### 6. pricing.py (行 1065-1144)
- `GET /pricing` - 获取电价配置列表
- `POST /pricing` - 创建电价配置
- `PUT /pricing/{pricing_id}` - 更新电价配置
- `DELETE /pricing/{pricing_id}` - 删除电价配置
- `GET /pricing/current` - 获取当前电价

### 7. suggestions.py (行 1145-1585)
- `GET /suggestions` - 获取节能建议列表
- `GET /suggestions/templates` - 获取建议模板
- `POST /suggestions/analyze` - 触发建议分析
- `GET /suggestions/enhanced` - 获取增强建议
- `GET /suggestions/summary` - 获取建议汇总
- `GET /suggestions/enhanced/{id}` - 获取增强建议详情
- `GET /suggestions/detail/{id}` - 获取建议完整详情
- `GET /suggestions/{id}` - 获取建议详情
- `PUT /suggestions/{id}/accept` - 接受建议
- `PUT /suggestions/{id}/reject` - 拒绝建议
- `PUT /suggestions/{id}/complete` - 完成建议
- `POST /suggestions/{id}/recalculate` - 重新计算

### 8. topology.py (行 1586-1655, 2400+)
- `GET /distribution` - 获取配电图数据
- 其他拓扑相关端点

### 9. exports.py (行 1656-1870)
- `GET /export/daily` - 导出日能耗数据
- `GET /export/monthly` - 导出月能耗数据

### 10. transformers.py (行 1871-1968)
- `GET /transformers` - 获取变压器列表
- `POST /transformers` - 创建变压器
- `GET /transformers/{id}` - 获取变压器详情
- `PUT /transformers/{id}` - 更新变压器
- `DELETE /transformers/{id}` - 删除变压器

### 11. meter_points.py (行 1969+)
- `GET /meter-points` - 获取计量点列表
- `POST /meter-points` - 创建计量点
- `GET /meter-points/{id}` - 获取计量点详情
- 更多计量点相关端点

## 迁移步骤

### 阶段 1：准备工作
1. [x] 创建 `energy/` 目录结构
2. [x] 创建 `__init__.py` 路由聚合
3. [x] 创建本重构计划文档

### 阶段 2：渐进式迁移
每次迁移一个子模块：

1. [ ] 创建 `_common.py` - 提取共享依赖
2. [ ] 迁移 `devices.py`
3. [ ] 迁移 `realtime.py`
4. [ ] 迁移 `pue.py`
5. [ ] 迁移 `statistics.py`
6. [ ] 迁移 `cost.py`
7. [ ] 迁移 `pricing.py`
8. [ ] 迁移 `suggestions.py`
9. [ ] 迁移 `topology.py`
10. [ ] 迁移 `exports.py`
11. [ ] 迁移 `transformers.py`
12. [ ] 迁移 `meter_points.py`

### 阶段 3：清理
1. [ ] 删除原 `energy.py`
2. [ ] 更新 `__init__.py` 移除 legacy 导入
3. [ ] 更新相关测试

## 迁移单个模块的模板

```python
# backend/app/api/v1/energy/devices.py
"""
用电设备管理 API
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ._common import (
    get_db, require_viewer, require_operator, require_admin,
    User, PowerDevice, ResponseModel
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["用电设备"])


@router.get("", response_model=ResponseModel[List[PowerDeviceResponse]])
async def get_power_devices(
    # ... 参数
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    # ... 实现
    pass
```

## 注意事项

1. **保持 API 兼容性** - 路由路径不变
2. **共享依赖提取** - 避免循环导入
3. **测试覆盖** - 每次迁移后运行测试
4. **渐进式迁移** - 不要一次性重构全部

## 预计工作量

- 每个子模块迁移：30-60 分钟
- 总工作量：约 8-10 小时
- 建议分多次完成，每次 2-3 个模块
