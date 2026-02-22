#!/usr/bin/env bash
# CI 测试运行脚本 — 分组运行后端测试，防止超时
# 用法: bash scripts/run_tests.sh [--frontend] [--backend] [--all]
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
TOTAL_PASSED=0
TOTAL_FAILED=0

run_backend_group() {
    local group_name="$1"
    shift
    echo -e "${YELLOW}▶ 后端测试组: ${group_name}${NC}"
    cd "$ROOT_DIR/backend"
    if .venv/Scripts/python.exe -m pytest "$@" -q --tb=short 2>&1; then
        echo -e "${GREEN}✓ ${group_name} 通过${NC}"
    else
        echo -e "${RED}✗ ${group_name} 失败${NC}"
        FAILED=1
    fi
    echo ""
}

run_frontend() {
    echo -e "${YELLOW}▶ 前端测试 (Vitest)${NC}"
    cd "$ROOT_DIR/frontend"
    if npx vitest --run 2>&1; then
        echo -e "${GREEN}✓ 前端测试通过${NC}"
    else
        echo -e "${RED}✗ 前端测试失败${NC}"
        FAILED=1
    fi
    echo ""
}

run_backend() {
    # 第1组: API 覆盖测试
    run_backend_group "API 覆盖测试" tests/api/ --timeout=120

    # 第2组: 服务层测试
    run_backend_group "服务层测试" tests/services/ --timeout=60

    # 第3组: 核心模块测试（认证、告警、能源、资产、运维）
    run_backend_group "核心模块测试" \
        tests/test_auth_core.py \
        tests/test_auth_session.py \
        tests/test_alarm_core.py \
        tests/test_alarm_api.py \
        tests/test_alarm_engine.py \
        tests/test_energy_core.py \
        tests/test_asset_core.py \
        tests/test_operations_core.py \
        --timeout=120

    # 第4组: 用户与权限测试
    run_backend_group "用户与权限测试" \
        tests/test_user_management.py \
        tests/test_password_policy.py \
        tests/test_audit_log.py \
        tests/test_site_isolation.py \
        tests/test_write_permission.py \
        --timeout=60

    # 第5组: 设备与网关测试
    run_backend_group "设备与网关测试" \
        tests/test_device_detail.py \
        tests/test_device_status_board.py \
        tests/test_device_template.py \
        tests/test_gateway.py \
        tests/test_gateway_api.py \
        tests/test_gateway_registration.py \
        tests/test_ota.py \
        tests/test_dry_contact.py \
        tests/test_connection_test.py \
        tests/test_config_push.py \
        --timeout=60

    # 第6组: 适配器测试
    run_backend_group "协议适配器测试" \
        tests/test_modbus_tcp.py \
        tests/test_modbus_rtu.py \
        tests/test_snmp.py \
        tests/test_bacnet_ip_adapter.py \
        tests/test_opc_ua_adapter.py \
        tests/test_http_rest_adapter.py \
        tests/test_mqtt_adapter.py \
        tests/test_point_data.py \
        --timeout=60

    # 第7组: 能源与报表测试
    run_backend_group "能源与报表测试" \
        tests/test_energy_aggregator.py \
        tests/test_energy_statistics.py \
        tests/test_energy_report.py \
        tests/test_pue_calculator.py \
        tests/test_report_auto.py \
        tests/test_report_export.py \
        tests/test_effect_tracker.py \
        tests/test_opportunity_detector.py \
        --timeout=60

    # 第8组: 拓扑与容量测试
    run_backend_group "拓扑与容量测试" \
        tests/test_topology_config.py \
        tests/test_smart_site_selection.py \
        tests/test_fault_impact.py \
        tests/test_capacity_monitoring.py \
        tests/test_capacity_trend.py \
        tests/test_racking_recommendation.py \
        tests/test_cabinet_usage.py \
        tests/test_spatial.py \
        --timeout=60

    # 第9组: 联动与诊断测试
    run_backend_group "联动与诊断测试" \
        tests/test_linkage.py \
        tests/test_fire_protection.py \
        tests/test_diagnosis.py \
        tests/test_drift.py \
        tests/test_command.py \
        tests/test_timeline.py \
        tests/test_recovery.py \
        --timeout=60

    # 第10组: 运维测试
    run_backend_group "运维测试" \
        tests/test_work_order.py \
        tests/test_work_order_approval.py \
        tests/test_alarm_workorder_rule.py \
        tests/test_inspection.py \
        tests/test_knowledge.py \
        tests/test_video.py \
        --timeout=60

    # 第11组: 其他测试
    run_backend_group "其他测试" \
        tests/test_data_quality.py \
        tests/test_escalation.py \
        tests/test_graceful_degradation.py \
        tests/test_backup_health.py \
        tests/test_site_management.py \
        tests/test_point_import.py \
        tests/test_asset_import.py \
        tests/test_asset_lifecycle_warranty.py \
        tests/test_integration.py \
        tests/test_proposal_executor.py \
        tests/test_proposal_models.py \
        tests/test_proposal_schemas.py \
        --timeout=60
}

# 解析参数
RUN_FRONTEND=false
RUN_BACKEND=false

if [ $# -eq 0 ] || [ "$1" = "--all" ]; then
    RUN_FRONTEND=true
    RUN_BACKEND=true
elif [ "$1" = "--frontend" ]; then
    RUN_FRONTEND=true
elif [ "$1" = "--backend" ]; then
    RUN_BACKEND=true
fi

echo "============================================"
echo "  DCIM 自动化测试套件"
echo "============================================"
echo ""

if [ "$RUN_FRONTEND" = true ]; then
    run_frontend
fi

if [ "$RUN_BACKEND" = true ]; then
    run_backend
fi

echo "============================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过${NC}"
    exit 0
else
    echo -e "${RED}✗ 部分测试失败${NC}"
    exit 1
fi
