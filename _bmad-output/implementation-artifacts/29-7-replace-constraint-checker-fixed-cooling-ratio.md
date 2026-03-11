# Story 29.7: 替换 constraint_checker 固定 0.4 制冷比例

Status: done

## Story

As a 系统运维人员,
I want 系统使用 TCL/THM 动态计算替代固定 0.4 制冷可转移比例,
So that 负荷转移功率评估更准确、更安全。

## 依赖

- Story 29.2（RC 模型）— done
- Story 29.3（THM 兜底）— done
- Story 29.4（预测 API）— done

## Acceptance Criteria

1. Given `constraint_checker.py` 第 489 行现有代码:
   ```python
   cooling_transferable_ratio = float(cfg.get("cooling_transferable_ratio", 0.40))
   ```
   When 系统计算制冷可转移功率
   Then 替换为动态计算逻辑:
   - 将动态比例获取逻辑抽取为独立方法 `async _get_dynamic_cooling_ratio(self, zone_id: Optional[int]) -> Optional[float]`，便于单独测试
   - 在 `_get_dynamic_cooling_ratio` 中:
     - 参数 `zone_id` 由调用方从 `cfg.get("cooling_zone_id")` 提取并传入
     - 如果 zone_id 为 None: 返回 None（由调用方回退到固定值）
     - 将 zone_id 转为 `int(zone_id)`（cfg 返回值可能是字符串）
     - 查询 `CoolingLinkageConfig` 表检查 `precool_enabled`
     - 如果无记录或 `precool_enabled=False`: 返回 None
     - 如果 `precool_enabled=True`: 调用 `calculate_shiftable_power_for_zone(zone_id, self.db)` 获取动态比例
     - `calculate_shiftable_power_for_zone` 内部已实现 TCL/THM 自动切换（Story 29.3 已完成）
     - 如果动态计算返回 error: 记录警告日志，返回 None
     - 成功时返回 `result["shiftable_ratio"]`（0~1 的小数，与原 `cooling_transferable_ratio` 语义一致）
   - 在原循环中调用: `dynamic_ratio = await self._get_dynamic_cooling_ratio(cfg.get("cooling_zone_id"))`
   - `cooling_transferable_ratio = dynamic_ratio if dynamic_ratio is not None else float(cfg.get("cooling_transferable_ratio", 0.40))`
   - `other_transferable_ratio` 保持不变（默认 0.60）

2. Given `_check_safety_constraints` 方法是 `async` 方法
   When 需要调用异步函数 `calculate_shiftable_power_for_zone`
   Then 注意以下集成要点:
   - `_check_safety_constraints` 已经是 `async` 方法，可以直接 `await`
   - 新增的 `_get_dynamic_cooling_ratio` 也声明为 `async`
   - 动态比例仅替换 `cooling_transferable_ratio`，计算公式 `max_transfer_power` 不变

3. Given 需要导入新依赖
   When 修改 `constraint_checker.py`
   Then 添加以下导入:
   - `from app.services.datacenter_shift_strategy import calculate_shiftable_power_for_zone`
   - 在现有 `from app.models.load_shift import ShiftConstraint` 行中追加 `CoolingLinkageConfig`
   - 使用 `import logging; logger = logging.getLogger(__name__)` 记录日志

4. Given 需要验证替换逻辑
   When 编写单元测试
   Then 主要测试 `_get_dynamic_cooling_ratio` 方法，覆盖以下场景:
   - 无 `cooling_zone_id` → 返回 None
   - `precool_enabled=False` → 返回 None
   - `precool_enabled=True` + 动态计算成功（返回 `shiftable_ratio=0.35`）→ 返回 0.35
   - `precool_enabled=True` + 动态计算返回 error → 返回 None
   - 无 `CoolingLinkageConfig` 记录 → 返回 None
   - 查询异常 → 返回 None（不传播异常）

## 涉及文件

- 修改 `backend/app/services/load_shift/algorithms/constraint_checker.py` — 替换第 489 行固定比例
- 新建 `backend/tests/services/load_shift/test_constraint_checker_dynamic_ratio.py` — 单元测试

## 技术说明

- `constraint_checker.py` 的 `ConstraintChecker` 类通过 `__init__(self, db: AsyncSession)` 持有数据库会话 `self.db`
- `_check_safety_constraints` 是 `async` 方法，可以直接 `await` 异步调用
- `calculate_shiftable_power_for_zone(zone_id, session)` 返回 `Dict`，成功时包含 `shiftable_ratio`（0~1 小数），失败时包含 `error` 键
- `shiftable_ratio` 与原 `cooling_transferable_ratio` 语义一致（均为 0~1 比例），无需额外转换
- `CoolingLinkageConfig` 表有 `cooling_zone_id` 和 `precool_enabled` 字段
- 新增 `_get_dynamic_cooling_ratio` 方法抽取动态计算逻辑，便于独立测试
- 如果一个站点有多个 zone，每个 datacenter_load constraint 可各自配置 `cooling_zone_id`

## Tasks

- [x] 1. 修改 constraint_checker.py 替换固定 0.40 为动态计算
- [x] 2. 编写单元测试
- [x] 3. 运行测试验证 — 10/10 通过
