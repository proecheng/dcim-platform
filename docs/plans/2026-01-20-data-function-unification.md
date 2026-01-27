# 数据与功能统一整合实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复系统中数据与功能不协调的问题，确保演示数据、配电拓扑、大屏导航、交互功能全部正常工作

**Architecture:** 清理残留数据 → 验证后端代码 → 重启服务 → 测试功能 → 更新文档

**Tech Stack:** Python/FastAPI, Vue 3, SQLite, TypeScript

---

## 问题现状分析

经调研确认以下问题：

| 问题 | 现状 | 根因 |
|------|------|------|
| 点位数量不一致 | 379总点位，330演示点位，49残留点位 | 数据库存在 A1_, A2_ 开头的旧点位未清理 |
| 配电拓扑已有数据 | 2变压器，3计量点，7配电柜 | 数据已创建但后端代码未重启 |
| 大屏导航 | 前端代码已修改 | 需重新构建并重启前端服务 |
| 大屏交互 | 前端代码已修改 | 需重新构建并验证 |

---

## Task 1: 清理残留点位数据

**Files:**
- Execute: 数据库清理脚本

**Step 1: 创建清理脚本**

创建 `backend/cleanup_legacy_points.py`:
```python
"""清理非演示数据的残留点位"""
import asyncio
from sqlalchemy import select, delete, func
from app.core.database import async_session, init_db
from app.models import Point, PointRealtime, PointHistory, AlarmThreshold

async def cleanup():
    await init_db()
    async with async_session() as session:
        # 查找非演示点位 (不以 B1_, F1_, F2_, F3_ 开头)
        result = await session.execute(
            select(Point.id).where(
                ~Point.point_code.like("B1_%") &
                ~Point.point_code.like("F1_%") &
                ~Point.point_code.like("F2_%") &
                ~Point.point_code.like("F3_%")
            )
        )
        legacy_ids = [r[0] for r in result.fetchall()]

        if not legacy_ids:
            print("没有发现残留点位")
            return

        print(f"发现 {len(legacy_ids)} 个残留点位，开始清理...")

        # 删除相关数据
        await session.execute(delete(PointHistory).where(PointHistory.point_id.in_(legacy_ids)))
        await session.execute(delete(AlarmThreshold).where(AlarmThreshold.point_id.in_(legacy_ids)))
        await session.execute(delete(PointRealtime).where(PointRealtime.point_id.in_(legacy_ids)))
        await session.execute(delete(Point).where(Point.id.in_(legacy_ids)))

        await session.commit()
        print(f"清理完成，删除了 {len(legacy_ids)} 个残留点位")

if __name__ == "__main__":
    asyncio.run(cleanup())
```

**Step 2: 运行清理脚本**

Run: `cd backend && python cleanup_legacy_points.py`
Expected: "清理完成，删除了 49 个残留点位"

**Step 3: 验证清理结果**

Run: `curl -s http://localhost:18080/api/v1/demo/status`
Expected: `point_count` 和 `demo_point_count` 相等 (都是 330)

---

## Task 2: 验证并修复后端演示数据服务

**Files:**
- Verify: `backend/app/services/demo_data_service.py`

**Step 1: 检查配电系统集成代码是否存在**

验证 `_create_distribution_system` 方法存在于 `demo_data_service.py`

**Step 2: 检查清理逻辑是否包含配电系统表**

验证 `_clear_demo_data` 方法包含删除配电系统表的代码

**Step 3: 如果缺失则添加代码**

确保以下表在清理时被删除:
- Demand15MinData
- EnergyHourly
- EnergyDaily
- ElectricityPricing
- PowerDevice
- DistributionCircuit
- DistributionPanel
- MeterPoint
- Transformer

---

## Task 3: 重启后端服务

**Files:**
- Execute: 服务重启

**Step 1: 提示用户关闭后端窗口**

用户需手动关闭 DCIM-Backend 窗口

**Step 2: 启动后端服务**

Run: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 18080`

**Step 3: 验证后端启动成功**

Run: `curl -s http://localhost:18080/api/v1/demo/status`
Expected: 返回 JSON，无错误

---

## Task 4: 重新构建前端

**Files:**
- Build: `frontend/`

**Step 1: 构建前端**

Run: `cd frontend && npm run build`
Expected: "✓ built in XXs"，无错误

**Step 2: 验证构建产物包含修复代码**

Run: `grep -o "normal_count" frontend/dist/assets/*.js | head -1`
Expected: 找到 `normal_count` 字符串

---

## Task 5: 重启前端服务

**Files:**
- Execute: 服务重启

**Step 1: 提示用户关闭前端窗口**

用户需手动关闭 DCIM-Frontend 窗口

**Step 2: 启动前端服务**

Run: `cd frontend && npx serve dist -s -l 3000`

---

## Task 6: 功能测试 - 点位数量

**Step 1: 通过API验证点位数量**

Run: `curl -s http://localhost:18080/api/v1/demo/status`
Expected: `point_count` = `demo_point_count` = 330

**Step 2: 登录系统验证仪表盘**

1. 打开 http://localhost:3000
2. 登录 (admin/admin123)
3. 查看仪表盘点位统计
Expected: 显示 330 个点位

---

## Task 7: 功能测试 - 配电拓扑

**Step 1: 获取登录Token**

```bash
curl -s -X POST http://localhost:18080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.data.access_token'
```

**Step 2: 验证配电拓扑API**

```bash
TOKEN="<上一步获取的token>"
curl -s http://localhost:18080/api/v1/energy/topology \
  -H "Authorization: Bearer $TOKEN" | jq '.data.transformers | length'
```
Expected: 返回 2 (两个变压器)

**Step 3: 在界面验证**

1. 导航到 能源管理 → 配电拓扑
2. 查看拓扑树是否显示数据
Expected: 显示变压器、计量点、配电柜等层级结构

---

## Task 8: 功能测试 - 大屏导航

**Step 1: 打开数字孪生大屏**

1. 点击顶部导航栏的 "数字孪生大屏" 按钮
2. 大屏在新标签页打开

**Step 2: 测试返回功能**

1. 在大屏页面点击 "返回" 按钮
2. 如果是新标签页打开，窗口应关闭
3. 如果是同窗口打开，应返回仪表盘页面
Expected: 正确返回，不出现页面异常

---

## Task 9: 功能测试 - 大屏交互

**Step 1: 测试左侧面板交互**

1. 在大屏中，悬停在左侧环境监测面板的各区域
2. 应显示 "点击查看监控详情 →" 提示
3. 点击温湿度区域
Expected: 打开新标签页显示 /monitor 页面

**Step 2: 测试右侧面板交互**

1. 悬停在右侧能耗统计面板
2. 点击 PUE 趋势区域
Expected: 打开新标签页显示 /energy/analysis 页面

**Step 3: 测试告警导航**

1. 点击左侧的实时告警区域
Expected: 打开新标签页显示 /alarm 页面

---

## Task 10: 更新文档

**Files:**
- Update: `findings.md`
- Update: `progress.md`

**Step 1: 更新 findings.md**

添加本次修复的详细记录:
- 问题分析
- 修复方案
- 验证结果

**Step 2: 更新 progress.md**

添加会话进度:
- 完成的任务
- 测试结果
- 版本更新为 V3.5

**Step 3: 提交变更**

```bash
git add -A
git commit -m "fix: 数据与功能统一整合 V3.5

- 清理残留点位数据
- 修复仪表盘点位统计字段映射
- 修复大屏返回导航使用Vue Router
- 集成配电拓扑数据到演示数据服务
- 添加大屏面板点击导航功能

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## 验证清单

- [ ] 点位数量一致 (330)
- [ ] 仪表盘正确显示点位统计
- [ ] 配电拓扑显示数据
- [ ] 大屏返回导航正常
- [ ] 大屏面板可点击导航
- [ ] 文档已更新

---

## 回滚方案

如果出现问题:
1. 恢复 `demo_data_service.py` 原始版本
2. 重新加载演示数据
3. 检查数据库完整性
