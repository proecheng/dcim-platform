# Story 26.3: 闭环学习自动调参

**Epic**: Epic 26 - 智能诊断高级功能 (Phase 3)
**Story ID**: 26.3
**Story Key**: 26-3-closed-loop-learning-probability-tuning
**优先级**: P3 (愿景阶段)
**估算**: 5 天
**状态**: ready-for-dev
**创建日期**: 2026-03-08

---

## 1. Story 概述

### 1.1 业务价值

为智能诊断系统添加"闭环学习自动调参"功能，系统基于运维标注数据自动优化故障树概率参数，使诊断准确率随使用时间持续提升。

**用户故事**: 作为管理员，我希望系统基于运维标注数据自动优化故障树概率参数，以便诊断准确率随使用时间持续提升。

**业务价值**:
- 自动化参数优化，减少人工调参工作量
- 基于真实运维数据持续改进诊断准确率
- 提供审批机制，确保参数调整可控可追溯
- 支持一键回滚，降低调参风险
- 为 ISO 27001/SOC 2 审计提供持续改进证据

### 1.2 前置条件

**必须完成的 Story**:
- Story 24.4: 故障树版本管理与HMAC签名（已完成）
- Story 24.6: 诊断结果存储与分级推送（已完成）
- Story 24.8: 诊断结果标注与RBAC（已完成）
- Story 26.2: 误诊反馈报告（已完成）

**数据要求**:
- 至少有 50 条针对同一故障树根因节点的运维标注数据
  - 50 样本阈值基于二项分布统计学最小样本量要求
  - 假设准确率 p=0.5（最保守估计），95% 置信度，误差边界 ±14%
  - 计算公式: n = (Z^2 * p * (1-p)) / E^2 = (1.96^2 * 0.5 * 0.5) / 0.14^2 ≈ 49
  - 实际业务中，14% 误差可接受，因为调参有 ±10% 幅度限制和人工审批机制
- 标注数据包含"准确"和"不准确"两种类型
- 故障树已建立并有活跃版本

**技术要求**:
- APScheduler 定时任务已配置
- PostgreSQL 数据库已配置
- 故障树版本管理系统已实现（Story 24.4）
- 邮件/WebSocket 通知服务已配置

### 1.3 验收标准

**功能验收**:
- [ ] APScheduler 每周定时任务执行概率调参分析
- [ ] 对于根因节点：计算诊断准确率，根据准确率与先验概率的差值决定调整方向
- [ ] 对于中间/叶节点：统计该节点参与的所有诊断中最终结论被标注为"准确"的比例
- [ ] 调整量限制：|调整量| ≤ 先验概率 × 10%
- [ ] 生成"概率调参审批工单"存储到 `probability_adjustment_logs` 表
- [ ] 通知管理员审批（通过邮件/WebSocket 推送，失败时记录日志）
- [ ] 管理员审批确认后，更新故障树节点先验概率，创建新故障树版本
- [ ] 支持一键回滚到上一版参数（激活上一个 archived 版本，若无可回滚版本则返回错误）
- [ ] 调参记录可追溯（包含调整前后概率、样本数、审批人、审批时间）

**性能验收**:
- [ ] 单次调参分析耗时 < 60 秒（基于 1000 条标注数据）
- [ ] 调参分析不影响正常诊断流程（异步执行）

**安全验收**:
- [ ] 调参审批按 RBAC 权限控制（仅管理员可审批）
- [ ] 调参操作记录审计日志（满足 ISO 27001/SOC 2 要求）
- [ ] 新版本故障树自动生成 HMAC 签名（复用 Story 24.4 逻辑）

**测试验收**:
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试覆盖核心场景（根因节点调参、中间节点调参、审批流程、回滚）

---

## 2. 技术设计

### 2.1 架构设计

**模块位置**: `backend/app/services/diagnosis/probability_tuning_service.py`

**依赖关系**:
```
ProbabilityTuningService
  ├── DiagnosisResult (读取诊断结果，包含推理过程中各节点的后验概率)
  ├── DiagnosisAnnotation (读取标注数据)
  ├── FaultTree (读取故障树)
  ├── FaultTreeNode (读取/更新节点概率)
  ├── ProbabilityAdjustmentLog (存储调参记录)
  └── FaultTreeVersionService (创建新版本，复用 Story 24.4)

注意: DiagnosisResult 表需存储推理过程数据（如 inference_trace JSON 字段），
包含各节点的后验概率，用于判断节点是否"参与诊断"（后验概率 > 0）
```

**执行流程**:
```
1. APScheduler 每周日 02:00 触发调参分析任务
2. 查询所有活跃故障树（status='active'）
3. 对每个故障树：
   a. 查询所有节点的标注数据统计
   b. 筛选样本数 ≥ 50 的节点（50 样本阈值基于统计学最小样本量要求）
   c. 对于根因节点：
      - 计算准确率 = 标注"准确"次数 / 总标注次数
      - 调整方向 = 准确率 - 先验概率
      - 若 |调整方向| > 先验概率 × 10%，截断到 ±10%
   d. 对于中间/叶节点：
      - 查询该节点参与的所有诊断（推理过程中后验概率 > 0）
      - 统计这些诊断中，最终根因结论被标注为"准确"的比例
      - 若与当前先验概率偏差 > 10%，标记为"建议调参"
   e. 生成调参建议记录（probability_adjustment_log 表）
4. 通知管理员审批（邮件 + WebSocket 推送，失败时记录日志但不阻塞流程）
5. 管理员审批后：
   a. 使用数据库事务确保原子性（更新调参记录状态 + 更新节点概率 + 创建版本 + 激活版本）
   b. 使用乐观锁防止并发审批冲突（UPDATE ... WHERE id=? AND version=? AND status='pending'）
   c. 更新调参记录状态为 'approved'，记录 approved_by 和 approved_at
   d. 更新节点先验概率
   e. 调用 FaultTreeVersionService 创建新版本
   f. 新版本自动生成 HMAC 签名
   g. 激活新版本
6. 记录审计日志
```

### 2.2 数据库设计

**新增表**: `probability_adjustment_logs`

```sql
CREATE TABLE probability_adjustment_logs (
    id SERIAL PRIMARY KEY,
    tree_id INTEGER NOT NULL REFERENCES fault_trees(id) ON DELETE CASCADE,
    node_id INTEGER NOT NULL REFERENCES fault_tree_nodes(id) ON DELETE CASCADE,
    node_name VARCHAR(200) NOT NULL,
    node_type VARCHAR(20) NOT NULL,  -- 'root', 'intermediate', 'leaf'
    current_probability FLOAT NOT NULL,
    proposed_probability FLOAT NOT NULL,
    adjustment_percent FLOAT NOT NULL,  -- 调整百分比 = (adjustment / current_prior) * 100，表示相对于先验概率的百分比变化
    sample_count INTEGER NOT NULL,  -- 样本数
    accurate_count INTEGER NOT NULL,  -- 准确标注次数
    inaccurate_count INTEGER NOT NULL,  -- 不准确标注次数
    accuracy_rate FLOAT NOT NULL,  -- 准确率
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    reason TEXT,  -- 审批理由或拒绝原因
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,  -- 乐观锁版本号，每次更新 +1
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_adjustment_logs_tree (tree_id),
    INDEX idx_adjustment_logs_node (node_id),
    INDEX idx_adjustment_logs_status (status),
    INDEX idx_adjustment_logs_created (created_at),
    INDEX idx_adjustment_logs_approved_by (approved_by)
);

-- 注意: SQLite 不支持 ON DELETE CASCADE 语法，需在应用层处理级联删除
-- 生产环境使用 PostgreSQL，开发/测试环境使用 SQLite 时需注意兼容性

-- 自动更新 updated_at 和 version 触发器
CREATE OR REPLACE FUNCTION update_adjustment_logs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_adjustment_logs_updated_at
BEFORE UPDATE ON probability_adjustment_logs
FOR EACH ROW
EXECUTE FUNCTION update_adjustment_logs_updated_at();
```

### 2.3 API 设计

**调参分析 API**:
```
POST /api/v1/diagnosis/probability-tuning/analyze
权限: admin
描述: 手动触发调参分析（也可由定时任务自动触发）
请求体: { "tree_id": 1 }  # 可选，不指定则分析所有活跃故障树
响应: {
  "analyzed_trees": 2,
  "total_adjustments": 5,
  "pending_approvals": 5
}
```

**查询调参记录 API**:
```
GET /api/v1/diagnosis/probability-tuning/adjustments
权限: admin
描述: 查询调参记录列表（通过 JOIN fault_trees 表获取 tree_name）
查询参数:
  - tree_id: 故障树ID（可选）
  - status: 状态筛选（pending/approved/rejected，可选）
  - page: 页码（默认1）
  - page_size: 每页数量（默认20）
响应: {
  "items": [
    {
      "id": 1,
      "tree_id": 1,
      "tree_name": "UPS故障树",  # 通过 JOIN fault_trees 获取
      "node_id": 10,
      "node_name": "电池组故障",
      "node_type": "root",
      "current_probability": 0.15,
      "proposed_probability": 0.165,
      "adjustment_percent": 10.0,  # (0.015 / 0.15) * 100 = 10.0%
      "sample_count": 120,
      "accurate_count": 95,
      "inaccurate_count": 25,
      "accuracy_rate": 0.792,
      "status": "pending",
      "created_at": "2026-03-08T02:00:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

**审批调参 API**:
```
POST /api/v1/diagnosis/probability-tuning/adjustments/{id}/approve
权限: admin
描述: 审批调参建议
请求体: { "reason": "审批理由（可选）" }
响应: {
  "message": "调参已审批，新版本故障树已创建",
  "adjustment_id": 1,
  "new_tree_version": "v1.2.0"
}
```

**拒绝调参 API**:
```
POST /api/v1/diagnosis/probability-tuning/adjustments/{id}/reject
权限: admin
描述: 拒绝调参建议
请求体: { "reason": "拒绝理由" }
响应: {
  "message": "调参已拒绝",
  "adjustment_id": 1
}
```

**回滚故障树版本 API**:
```
POST /api/v1/fault-trees/{id}/rollback
权限: admin
描述: 回滚到最近一个 archived 版本（按 created_at 降序排序取第一个）
     若无可回滚版本（无 archived 版本或只有一个版本）则返回 400 错误
响应: {
  "message": "故障树已回滚到版本 v1.1.0",
  "tree_id": 1,
  "active_version": "v1.1.0",
  "previous_version": "v1.2.0"
}
错误响应 (无可回滚版本): {
  "detail": "无可回滚的版本"
}
```

### 2.4 核心算法

**根因节点调参逻辑**:
```python
def calculate_root_node_adjustment(
    node_id: int,
    current_prior: float,
    accurate_count: int,
    total_count: int
) -> tuple[float, float]:
    """
    计算根因节点的调参建议

    Returns:
        (proposed_probability, adjustment_percent)
    """
    # 防止除零错误
    if total_count == 0:
        logger.warning(f"节点 {node_id} 标注总数为 0，跳过调参")
        return current_prior, 0.0

    # 计算准确率
    accuracy_rate = accurate_count / total_count

    # 调整方向 = 准确率 - 先验概率
    # 准确率 > 先验 → 上调（该故障比预期更常见）
    # 准确率 < 先验 → 下调（该故障被高估）
    adjustment = accuracy_rate - current_prior

    # 限制调整幅度：最多 ±10%
    max_adjustment = current_prior * 0.10
    if abs(adjustment) > max_adjustment:
        adjustment = max_adjustment if adjustment > 0 else -max_adjustment

    proposed_probability = current_prior + adjustment

    # 确保概率在 [0.01, 0.99] 范围内
    proposed_probability = max(0.01, min(0.99, proposed_probability))

    # 重新计算实际调整量（因为可能被边界截断）
    actual_adjustment = proposed_probability - current_prior

    # 防止除零错误
    if current_prior == 0:
        adjustment_percent = 0.0
    else:
        adjustment_percent = (actual_adjustment / current_prior) * 100

    return proposed_probability, adjustment_percent
```

**中间/叶节点调参逻辑**:
```python
def calculate_intermediate_node_adjustment(
    node_id: int,
    current_prior: float,
    diagnoses_with_node: list[DiagnosisResult]
) -> tuple[float, float, bool]:
    """
    计算中间/叶节点的调参建议

    "参与诊断"定义: 该节点在推理过程中被激活（后验概率 > 0）
    "准确诊断"定义: 该节点参与的诊断，其最终根因结论被标注为"准确"

    Returns:
        (proposed_probability, adjustment_percent, should_adjust)
    """
    # 统计该节点参与的所有诊断中，最终结论被标注为"准确"的比例
    accurate_diagnoses = [
        d for d in diagnoses_with_node
        if d.annotation and d.annotation.annotation == 'accurate'
    ]

    if not diagnoses_with_node:
        logger.info(f"节点 {node_id} 未参与任何诊断，跳过调参")
        return current_prior, 0.0, False

    participation_accuracy = len(accurate_diagnoses) / len(diagnoses_with_node)

    # 若与当前先验概率偏差 > 10%，标记为"建议调参"
    deviation = abs(participation_accuracy - current_prior)
    should_adjust = deviation > 0.10

    if should_adjust:
        # 调整方向：向参与准确率靠拢
        adjustment = participation_accuracy - current_prior

        # 限制调整幅度：最多 ±10%
        max_adjustment = current_prior * 0.10
        if abs(adjustment) > max_adjustment:
            adjustment = max_adjustment if adjustment > 0 else -max_adjustment

        proposed_probability = current_prior + adjustment
        proposed_probability = max(0.01, min(0.99, proposed_probability))

        # 重新计算实际调整量（因为可能被边界截断）
        actual_adjustment = proposed_probability - current_prior

        # 防止除零错误
        if current_prior == 0:
            adjustment_percent = 0.0
        else:
            adjustment_percent = (actual_adjustment / current_prior) * 100
    else:
        proposed_probability = current_prior
        adjustment_percent = 0.0

    return proposed_probability, adjustment_percent, should_adjust
```

### 2.5 定时任务配置

```python
# backend/app/main.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.diagnosis.probability_tuning_service import ProbabilityTuningService

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', day_of_week='sun', hour=2, minute=0, misfire_grace_time=300)
async def weekly_probability_tuning():
    """每周日凌晨2点执行概率调参分析

    misfire_grace_time=300: 如果任务错过执行时间（如服务重启），
    在 300 秒内仍会执行，超过则跳过本次任务
    """
    logger.info("开始执行每周概率调参分析")

    tuning_service = ProbabilityTuningService()

    try:
        result = await tuning_service.analyze_all_trees()
        logger.info(f"概率调参分析完成: {result}")

        # 如果有待审批的调参建议，发送通知
        if result['pending_approvals'] > 0:
            try:
                await tuning_service.notify_admins(result)
            except Exception as notify_error:
                logger.error(f"通知管理员失败: {notify_error}", exc_info=True)
                # 通知失败不阻塞流程，调参记录已保存
    except Exception as e:
        logger.error(f"概率调参分析失败: {e}", exc_info=True)
```

---

## 3. 实现任务

### Task 1: 数据库迁移
- [x] 创建 `probability_adjustment_logs` 表（包含 version 字段用于乐观锁）
- [x] 添加索引和触发器（自动更新 updated_at 和 version）
- [x] 创建回滚脚本（`alembic downgrade -1`）
  - 回滚内容: DROP TABLE probability_adjustment_logs, DROP TRIGGER, DROP FUNCTION

### Task 2: 后端服务实现
- [x] 实现 `ProbabilityTuningService` 核心逻辑
- [x] 实现根因节点调参算法
- [x] 实现中间/叶节点调参算法
- [x] 实现调参记录生成和存储
- [ ] 实现审批流程（approve/reject）
- [ ] 实现故障树版本回滚功能
- [ ] 集成 FaultTreeVersionService（复用 Story 24.4）

### Task 3: 后端 API 实现
- [x] 实现 POST `/diagnosis/probability-tuning/analyze` 手动触发分析
- [x] 实现 GET `/diagnosis/probability-tuning/adjustments` 查询调参记录
  - 使用 JOIN fault_trees 表获取 tree_name
- [x] 实现 POST `/diagnosis/probability-tuning/adjustments/{id}/approve` 审批
  - 使用统一权限装饰器 `@require_role('admin')`（如不存在则创建）
- [x] 实现 POST `/diagnosis/probability-tuning/adjustments/{id}/reject` 拒绝
- [ ] 实现 POST `/fault-trees/{id}/rollback` 回滚版本
  - 查询最近一个 archived 版本（ORDER BY created_at DESC LIMIT 1）
- [ ] 添加权限控制装饰器（仅管理员）

### Task 4: APScheduler 定时任务
- [ ] 配置每周定时任务（周日凌晨2点）
- [ ] 实现调参分析任务逻辑
- [ ] 实现管理员通知逻辑（邮件 + WebSocket）
  - 邮件主题: "智能诊断系统 - 概率调参审批通知"
  - 邮件正文: 包含待审批调参数量、故障树名称、节点名称、调整建议
  - WebSocket 消息: { "type": "probability_tuning_approval", "pending_count": 5 }
  - 通知对象: 所有 role='admin' 的用户
- [ ] 添加任务失败重试机制（APScheduler misfire_grace_time=300 秒）

### Task 5: 后端测试
- [ ] 单元测试：根因节点调参算法
- [ ] 单元测试：中间/叶节点调参算法
- [ ] 单元测试：调参记录生成
- [ ] 集成测试：完整调参流程（分析→审批→版本创建）
- [ ] 集成测试：审批拒绝流程
- [ ] 集成测试：版本回滚流程
- [ ] 集成测试：并发审批场景（两个管理员同时审批同一调参记录，验证乐观锁）
- [ ] 边界测试：样本数不足场景
- [ ] 边界测试：调整幅度限制

### Task 6: 前端页面
- [ ] 创建调参管理页面（`frontend/src/views/diagnosis/ProbabilityTuning.vue`）
  - 参考 `frontend/src/views/diagnosis/Reports.vue` 的布局模式
  - 路由路径: `/diagnosis/probability-tuning`
  - 权限要求: admin only（在路由 meta 中配置 `requiresRole: ['admin']`）
- [ ] 实现调参记录列表展示
  - 表格列: 故障树名称、节点名称、节点类型、当前概率、建议概率、调整百分比、样本数、准确率、状态、创建时间
  - 筛选条件: 故障树ID、状态（pending/approved/rejected）
- [ ] 实现调参详情查看（对比调整前后概率、样本数、准确率）
  - 使用 el-dialog 弹窗展示详情
- [ ] 实现审批/拒绝操作
  - 审批按钮: 二次确认对话框（el-message-box.confirm）
  - 拒绝按钮: 输入拒绝理由（el-message-box.prompt）
- [ ] 实现版本回滚功能
  - 回滚按钮: 二次确认对话框，提示"将回滚到上一个版本，是否继续？"
- [ ] 实现手动触发分析按钮
- [ ] 添加路由配置到 `frontend/src/router/index.ts`
  - 添加菜单项到侧边栏（在"智能诊断"分组下）

### Task 7: 文档更新
- [ ] API 文档更新
- [ ] 用户手册更新（调参审批流程说明）
- [ ] 运维手册更新（定时任务配置说明）

---

## 4. 测试用例

### 测试用例 1: 根因节点调参 - 准确率高于先验

**前置条件**:
- 故障树节点 "UPS电池组故障"（root 节点）先验概率 = 0.15
- 标注数据: 120 条，其中 95 条"准确"，25 条"不准确"

**执行步骤**:
1. 触发调参分析: `POST /api/v1/diagnosis/probability-tuning/analyze`

**预期结果**:
- 准确率 = 95/120 = 0.792
- 调整方向 = 0.792 - 0.15 = 0.642（超过 10% 限制）
- 调整量截断 = 0.15 × 0.10 = 0.015
- 建议概率 = 0.15 + 0.015 = 0.165
- 调整百分比 = (0.015 / 0.15) × 100 = 10.0%
- 生成调参记录，status='pending'

---

### 测试用例 2: 中间节点调参 - 偏差超过 10%

**前置条件**:
- 故障树节点 "温度传感器异常"（intermediate 节点）先验概率 = 0.30
- 该节点参与的诊断: 80 条，其中 50 条最终结论被标注为"准确"

**执行步骤**:
1. 触发调参分析

**预期结果**:
- 参与准确率 = 50/80 = 0.625
- 偏差 = |0.625 - 0.30| = 0.325 > 0.10
- 标记为"建议调参"
- 调整方向 = 0.625 - 0.30 = 0.325（超过 10% 限制）
- 调整量截断 = 0.30 × 0.10 = 0.03
- 建议概率 = 0.30 + 0.03 = 0.33
- 生成调参记录

---

### 测试用例 3: 审批流程 - 创建新版本

**前置条件**:
- 调参记录 ID=1，status='pending'
- 当前故障树版本 = v1.1.0

**执行步骤**:
1. 审批调参: `POST /api/v1/diagnosis/probability-tuning/adjustments/1/approve`
2. 查询故障树版本: `GET /api/v1/fault-trees/1/versions`

**预期结果**:
- 调参记录 status 更新为 'approved'
- 节点先验概率更新为建议值
- 创建新版本 v1.2.0，status='active'
- 旧版本 v1.1.0 status 更新为 'archived'
- 新版本自动生成 HMAC 签名
- 审计日志记录审批操作

---

### 测试用例 4: 版本回滚

**前置条件**:
- 当前活跃版本 = v1.2.0
- 上一个 archived 版本 = v1.1.0

**执行步骤**:
1. 回滚版本: `POST /api/v1/fault-trees/1/rollback`
2. 查询故障树版本

**预期结果**:
- v1.1.0 status 更新为 'active'
- v1.2.0 status 更新为 'archived'
- 节点先验概率恢复为 v1.1.0 的值
- 审计日志记录回滚操作

---

### 测试用例 5: 样本数不足场景

**前置条件**:
- 故障树节点 "新增故障类型" 标注数据仅 30 条

**执行步骤**:
1. 触发调参分析

**预期结果**:
- 该节点不生成调参建议（样本数 < 50）
- 分析日志记录: "节点 X 样本数不足（30 < 50），跳过调参"

---

## 5. 开发者上下文

### 5.1 架构约束

**来源**: Architecture 18.6 闭环学习

- 调参必须基于 ≥50 条标注数据（基于二项分布统计学最小样本量，95% 置信度，误差 ±14%）
- 调整幅度限制：最多 ±10%（实际调整量可能因边界截断而小于 10%）
- 新版本故障树必须生成 HMAC 签名（复用 Story 24.4）
- 审批流程必须记录审计日志（满足 ISO 27001/SOC 2）
- 审批操作使用数据库事务 + 乐观锁（version 字段）防止并发冲突

### 5.2 技术栈约束

**来源**: project-context.md

- Python 3.11+, FastAPI 0.109.0
- SQLAlchemy 2.0.25 异步模式
- APScheduler 3.10.4 定时任务
- PostgreSQL + asyncpg 异步驱动
- Pydantic 2.5.3 数据验证

### 5.3 代码规范

**来源**: project-context.md

- 使用 `async/await` 异步模式
- 数据库操作使用 `async with async_session() as session`
- 配置通过 `get_settings()` 单例获取
- 日志使用 `logger.info/warning/error`
- 异常处理使用 `try/except` 并记录日志

### 5.4 前置 Story 学习

**来源**: Story 26-2 实现经验

- APScheduler 定时任务配置模式：
  ```python
  @scheduler.scheduled_job('cron', day_of_week='sun', hour=2, minute=0)
  async def weekly_task():
      pass
  ```

- 邮件通知模式：
  ```python
  from app.services.email_service import email_service
  if email_service.is_available:
      await email_service.send_html_email(...)
  ```

- 审计日志记录模式：
  ```python
  logger.info(f"操作: {action}, 用户: {user_id}, 时间: {datetime.now()}")
  ```

- 权限控制装饰器：
  ```python
  # backend/app/core/security.py
  from functools import wraps
  from fastapi import HTTPException

  def require_role(*allowed_roles):
      """权限控制装饰器，限制只有特定角色可访问"""
      def decorator(func):
          @wraps(func)
          async def wrapper(*args, current_user: User, **kwargs):
              if current_user.role not in allowed_roles:
                  raise HTTPException(status_code=403, detail="权限不足")
              return await func(*args, current_user=current_user, **kwargs)
          return wrapper
      return decorator

  # 使用示例
  @router.post("/adjustments/{id}/approve")
  @require_role('admin')
  async def approve_adjustment(
      id: int,
      current_user: User = Depends(get_current_active_user)
  ):
      pass
  ```

### 5.5 故障树版本管理集成

**来源**: Story 24.4

- 创建新版本时必须调用 `FaultTreeVersionService.create_new_version()`
- 新版本自动生成 HMAC 签名
- 激活新版本时，旧版本自动 archived
- 版本回滚通过激活 archived 版本实现

### 5.6 数据库查询优化

**来源**: Story 26-2 实现经验

- 使用 JOIN 减少查询次数
- 使用 GROUP BY 聚合统计
- 添加索引加速查询（tree_id, node_id, status, created_at）
- 大数据量查询使用分页

### 5.7 测试模式

**来源**: Story 26-2 测试经验

- 单元测试使用 pytest + pytest-asyncio
- 集成测试使用 TestClient
- 测试数据库使用 SQLite 内存模式
- 测试覆盖率目标 ≥ 80%

---

## 6. 文件清单

**后端文件**:
- `backend/alembic/versions/20260308_0100_create_probability_adjustment_logs.py` - 数据库迁移脚本
- `backend/app/models/diagnosis.py` - 添加 ProbabilityAdjustmentLog 模型
- `backend/app/models/__init__.py` - 导出新模型
- `backend/app/schemas/probability_tuning.py` - 调参 Schema
- `backend/app/services/diagnosis/probability_tuning_service.py` - 核心服务
- `backend/app/api/v1/diagnosis.py` - 添加调参 API 端点
- `backend/app/api/v1/fault_trees.py` - 添加回滚 API 端点
- `backend/app/main.py` - 添加 APScheduler 定时任务
- `backend/tests/services/diagnosis/test_probability_tuning_service.py` - 服务测试
- `backend/tests/api/test_probability_tuning.py` - API 集成测试

**前端文件**:
- `frontend/src/views/diagnosis/ProbabilityTuning.vue` - 调参管理页面
- `frontend/src/api/modules/diagnosis.ts` - 添加调参 API 接口定义
- `frontend/src/router/index.ts` - 添加路由配置

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Tasks/Subtasks

**已完成**:
- Task 1: 数据库迁移（完整）
  - 创建迁移脚本 `20260308_0100_create_probability_adjustment_logs.py`
  - 添加 ProbabilityAdjustmentLog 模型到 `backend/app/models/diagnosis.py`
  - 导出模型到 `backend/app/models/__init__.py`
  - 包含乐观锁版本号字段、索引、触发器、回滚脚本

- Task 2: 后端服务实现（部分）
  - 创建 Pydantic Schema `backend/app/schemas/probability_tuning.py`
  - 实现 `ProbabilityTuningService` 核心逻辑
  - 实现根因节点和中间/叶节点调参算法
  - 包含除零错误处理、边界截断、日志记录

- Task 3: 后端 API 实现（部分）
  - 添加 4 个 API 端点到 `backend/app/api/v1/diagnosis.py`
  - POST `/diagnosis/probability-tuning/analyze` - 手动触发分析
  - GET `/diagnosis/probability-tuning/adjustments` - 查询调参记录
  - POST `/diagnosis/probability-tuning/adjustments/{id}/approve` - 审批
  - POST `/diagnosis/probability-tuning/adjustments/{id}/reject` - 拒绝

**待完成**:
- Task 2: 审批流程完整实现（需集成 FaultTreeVersionService）
- Task 3: 回滚 API、权限装饰器
- Task 4: APScheduler 定时任务配置
- Task 5: 后端测试
- Task 6: 前端页面
- Task 7: 文档更新

### File List

**后端文件**:
- `backend/alembic/versions/20260308_0100_create_probability_adjustment_logs.py` - 数据库迁移脚本（新建）
- `backend/app/models/diagnosis.py` - 添加 ProbabilityAdjustmentLog 模型（修改）
- `backend/app/models/__init__.py` - 导出新模型（修改）
- `backend/app/schemas/probability_tuning.py` - 调参 Schema（新建）
- `backend/app/services/diagnosis/probability_tuning_service.py` - 核心服务（新建）
- `backend/app/api/v1/diagnosis.py` - 添加调参 API 端点（修改）

### Change Log

- 2026-03-08: 创建数据库迁移脚本，包含 probability_adjustment_logs 表定义
- 2026-03-08: 添加 ProbabilityAdjustmentLog 模型，支持乐观锁版本控制
- 2026-03-08: 实现 ProbabilityTuningService 核心逻辑，包含根因节点和中间/叶节点调参算法
- 2026-03-08: 添加 4 个调参 API 端点（分析、查询、审批、拒绝）
- 2026-03-08: 创建 Pydantic Schema 用于 API 请求/响应验证

### Implementation Notes

**技术决策**:
1. 使用乐观锁（version 字段）防止并发审批冲突
2. 调整量计算考虑边界截断，重新计算实际调整百分比
3. 数据库迁移脚本兼容 SQLite 和 PostgreSQL
4. API 使用 require_admin 装饰器限制权限

**待解决问题**:
1. FaultTree 和 FaultTreeNode 模型尚未实现（依赖 Story 24.4）
2. DiagnosisResult 需要 inference_trace JSON 字段存储后验概率
3. 邮件和 WebSocket 通知服务需要集成
4. 前端页面和路由配置待实现

**测试策略**:
- 单元测试：调参算法、除零处理、边界截断
- 集成测试：完整审批流程、并发审批、版本回滚
- 边界测试：样本数不足、概率边界值

---

**Story 创建日期**: 2026-03-08
**Story 创建者**: Bob (Scrum Master)
**Story 状态**: in-progress (blocked)
**阻塞原因**: 依赖 Story 24.4（故障树版本管理与HMAC签名）尚未实现，缺少 FaultTree、FaultTreeNode、FaultTreeVersionService 等核心组件
**最后更新**: 2026-03-08
