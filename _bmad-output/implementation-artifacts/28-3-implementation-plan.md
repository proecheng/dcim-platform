# Story 28.3 实施计划

**状态:** 设计完成，待实施
**创建时间:** 2026-03-05

---

## 实施总结

Story 28.3 已完成详细设计和两轮对抗性审查，发现并修复了 30 个潜在问题。由于实施涉及大量代码重构和测试，建议在新的上下文窗口中执行。

---

## 关键实施要点

### 1. MatcherRegistry 实现要点

- 使用 `RLock` 保证线程安全
- `register()` 自动为规则添加 `_source` 标记
- `get_rule()` 返回字典副本防止修改
- `unregister()` 按来源卸载规则

### 2. 缓存实现要点

- 楼层查询使用 1 小时 TTL 缓存
- 提供 `clear_floors_cache()` 手动清除
- 缓存键基于时间戳（每小时）

### 3. 设备类型映射

- 优先从配置文件加载 `DEVICE_TYPE_CATEGORY_MAPPING`
- 降级方案：硬编码默认映射
- 支持运行时动态更新

### 4. 测试要点

- 使用 `pytest.monkeypatch` 隔离环境变量
- 使用 `@pytest.fixture(autouse=True)` 清理注册表
- 测试数据使用事务回滚清理
- 线程安全测试覆盖并发场景

### 5. 迁移检查清单

**building_points.py 导入检查:**
```bash
grep -r "from app.data.building_points" backend/app/
```

**硬编码检查:**
```bash
grep -r "UPS-01\|AC-01\|PDU-01\|F1\|F2\|F3\|F4\|C-CH-01\|C-AC-01" backend/app/services/
```

**Demo seeds 文件更新:**
```bash
grep -r "building_points" backend/app/demo/seeds/
```

---

## 实施顺序

### Phase 1: 点位匹配引擎重构（2-3小时）

1. 实现 `MatcherRegistry` 类（应用第二轮审查修复）
2. 创建 `app/demo/data/legacy_mapping.py`
3. 迁移 `LEGACY_MAPPING_RULES`
4. 修改 `derive_point_prefix()` 和 `identify_point_usage()`
5. 集成到 `demo/lifecycle.py`
6. 单元测试

### Phase 2: device_sync.py 参数化（2-3小时）

1. 实现 `get_floors_from_db()` 带缓存
2. 实现 `match_circuit_from_db()`
3. 从配置加载 `DEVICE_TYPE_CATEGORY_MAPPING`
4. 重构 `sync_devices()` 移除硬编码
5. 单元测试

### Phase 3: building_points.py 迁移（30分钟）

1. 移动文件到 `app/demo/data/`
2. 全局搜索并更新导入
3. 验证只有 demo 模块导入

### Phase 4: 集成测试（1-2小时）

1. Demo 禁用测试
2. Demo 启用测试
3. 规则卸载测试
4. 端到端功能验证

**总计:** 约 6-9 小时

---

## 风险提示

1. **DistributionCircuit 表结构**: 需要验证 `category` 和 `floor_id` 字段存在
2. **main.py 集成**: 确保 `demo_shutdown()` 在 lifespan 中被调用
3. **性能监控**: 实施后监控数据库查询性能
4. **回滚准备**: 保留 feature branch，准备 Feature Flag

---

## 验收检查

- [ ] 所有 6 个 AC 通过
- [ ] 单元测试覆盖率 >= 80%
- [ ] Demo 禁用时无 ImportError
- [ ] Demo 启用时 legacy 规则生效
- [ ] 规则卸载功能正常
- [ ] 性能无明显下降
- [ ] 代码审查通过

---

## 下一步

在新的上下文窗口中执行 `/bmad-bmm-dev-story` 实施此 Story。
