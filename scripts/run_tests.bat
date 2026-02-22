@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   DCIM 自动化测试套件
echo ============================================
echo.

set FAILED=0
set ROOT=%~dp0..

:: ========== 前端测试 ==========
if "%1"=="--backend" goto :backend_only

echo [前端] Vitest 单元测试...
cd /d "%ROOT%\frontend"
call npx vitest --run
if errorlevel 1 (
    echo [失败] 前端测试
    set FAILED=1
) else (
    echo [通过] 前端测试
)
echo.

:backend_only
if "%1"=="--frontend" goto :summary

:: ========== 后端测试 ==========
cd /d "%ROOT%\backend"

echo [后端] API 覆盖测试...
.venv\Scripts\python.exe -m pytest tests/api/ -q --tb=short --timeout=120
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 服务层测试...
.venv\Scripts\python.exe -m pytest tests/services/ -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 核心模块测试...
.venv\Scripts\python.exe -m pytest tests/test_auth_core.py tests/test_auth_session.py tests/test_alarm_core.py tests/test_alarm_api.py tests/test_alarm_engine.py tests/test_energy_core.py tests/test_asset_core.py tests/test_operations_core.py -q --tb=short --timeout=120
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 用户与权限测试...
.venv\Scripts\python.exe -m pytest tests/test_user_management.py tests/test_password_policy.py tests/test_audit_log.py tests/test_site_isolation.py tests/test_write_permission.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 设备与网关测试...
.venv\Scripts\python.exe -m pytest tests/test_device_detail.py tests/test_device_status_board.py tests/test_device_template.py tests/test_gateway.py tests/test_gateway_api.py tests/test_gateway_registration.py tests/test_ota.py tests/test_dry_contact.py tests/test_connection_test.py tests/test_config_push.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 协议适配器测试...
.venv\Scripts\python.exe -m pytest tests/test_modbus_tcp.py tests/test_modbus_rtu.py tests/test_snmp.py tests/test_bacnet_ip_adapter.py tests/test_opc_ua_adapter.py tests/test_http_rest_adapter.py tests/test_mqtt_adapter.py tests/test_point_data.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 能源与报表测试...
.venv\Scripts\python.exe -m pytest tests/test_energy_aggregator.py tests/test_energy_statistics.py tests/test_energy_report.py tests/test_pue_calculator.py tests/test_report_auto.py tests/test_report_export.py tests/test_effect_tracker.py tests/test_opportunity_detector.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 拓扑与容量测试...
.venv\Scripts\python.exe -m pytest tests/test_topology_config.py tests/test_smart_site_selection.py tests/test_fault_impact.py tests/test_capacity_monitoring.py tests/test_capacity_trend.py tests/test_racking_recommendation.py tests/test_cabinet_usage.py tests/test_spatial.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 联动与诊断测试...
.venv\Scripts\python.exe -m pytest tests/test_linkage.py tests/test_fire_protection.py tests/test_diagnosis.py tests/test_drift.py tests/test_command.py tests/test_timeline.py tests/test_recovery.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 运维测试...
.venv\Scripts\python.exe -m pytest tests/test_work_order.py tests/test_work_order_approval.py tests/test_alarm_workorder_rule.py tests/test_inspection.py tests/test_knowledge.py tests/test_video.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

echo [后端] 其他测试...
.venv\Scripts\python.exe -m pytest tests/test_data_quality.py tests/test_escalation.py tests/test_graceful_degradation.py tests/test_backup_health.py tests/test_site_management.py tests/test_point_import.py tests/test_asset_import.py tests/test_asset_lifecycle_warranty.py tests/test_integration.py tests/test_proposal_executor.py tests/test_proposal_models.py tests/test_proposal_schemas.py -q --tb=short --timeout=60
if errorlevel 1 (set FAILED=1 & echo [失败]) else (echo [通过])
echo.

:summary
echo ============================================
if %FAILED%==0 (
    echo   所有测试通过
    exit /b 0
) else (
    echo   部分测试失败
    exit /b 1
)
