# Test Automation Summary

## 生成日期: 2026-03-17

## 背景
对抗性审查修复了 7 个诊断 API 文件中的 34+ 处安全/健壮性问题。本次 QA 自动化生成补充 E2E 测试，覆盖修复引入的新行为。

## Generated Tests

### API Tests
- [x] `tests/api/test_audit_fix_coverage.py` — 28 个测试用例，7 个测试类

## 测试类别覆盖

### 1. Pydantic 模型验证 (5 tests)
- [x] `test_reject_time_window_whitespace_reason` — strip + min_length=1
- [x] `test_reject_time_window_valid_reason` — 正常 reason 通过
- [x] `test_hmac_key_rotate_short_key` — key < 32 字符 → 422
- [x] `test_hmac_key_rotate_missing_key` — 缺少 new_key → 422
- [x] `test_approve_time_window_optional_reason` — reason 可选

### 2. 分页参数边界 (6 tests)
- [x] `test_ab_tests_page_size_exceeds_limit` — page_size > 100 → 422
- [x] `test_ab_tests_page_size_at_limit` — page_size=100 → 200
- [x] `test_ab_tests_page_zero` — page=0 → 422
- [x] `test_fault_tree_versions_page_size_exceeds_limit` — page_size > 100 → 422
- [x] `test_battery_soh_limit_exceeds_max` — limit > 500 → 422
- [x] `test_battery_soh_limit_at_max` — limit=500 → 200

### 3. RBAC 依赖注入替换 (7 tests)
- [x] `test_sensor_metadata_viewer_cannot_create` — viewer → 403
- [x] `test_sensor_metadata_viewer_cannot_delete` — viewer → 403
- [x] `test_sensor_metadata_operator_cannot_delete` — operator → 403
- [x] `test_sensor_metadata_operator_can_update` — operator → 200
- [x] `test_fault_tree_versions_viewer_can_list` — viewer → 200
- [x] `test_probability_adjustments_viewer_can_list` — viewer → 200
- [x] `test_probability_adjustments_no_auth` — 无认证 → 401

### 4. 审计日志写入 (1 test)
- [x] `test_ab_test_create_writes_audit_log` — 创建后验证 OperationLog

### 5. GET→POST 方法变更 (2 tests)
- [x] `test_reload_rules_get_not_200` — GET 不再返回 200
- [x] `test_reload_rules_post_works` — POST 正常工作

### 6. 边界修复 (4 tests)
- [x] `test_export_format_invalid` — Literal["pdf"] → 非 pdf 返回 422
- [x] `test_export_format_pdf_valid` — pdf 格式通过验证
- [x] `test_sensor_check_expired_returns_200` — 202→200 修复
- [x] `test_misdiagnosis_end_date_boundary` — end_date < vs <= 边界

### 7. 通用错误消息 (3 tests)
- [x] `test_probability_approve_error_generic` — 不泄露异常详情
- [x] `test_time_window_approve_nonexistent_generic` — 404 通用消息
- [x] `test_time_window_reject_nonexistent_generic` — 404 通用消息

## Coverage

| 模块 | 新增测试 |
|------|---------|
| ab_testing.py | 4 |
| misdiagnosis_reports.py | 2 |
| fault_tree_versions.py | 2 |
| sensor_metadata.py | 5 |
| probability_tuning.py | 3 |
| diagnosis.py | 12 |
| **总计** | **28** |

## 源码修复（测试中发现）
- `diagnosis.py`: `strip_whitespace=True`（Pydantic V2 废弃）→ 改用 `@field_validator` 实现空白检查

## Next Steps
- 所有 28 个新测试已通过
- 全量回归测试进行中
