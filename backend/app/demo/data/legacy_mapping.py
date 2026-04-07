"""Demo 环境的 Legacy 映射规则

Story 28.3: 将硬编码的 demo 设备映射规则从主系统迁移到 demo 模块
"""

import logging

logger = logging.getLogger(__name__)

# Demo 环境的设备编码到点位前缀的映射规则
# 编码已统一为 datacenter_seed 的 {PREFIX}-{FLOOR}-{SEQ:02d} 格式
DEMO_LEGACY_RULES = {
    # 服务器机柜 SRV-001~004 -> A1_SRV_AI_001~012
    "SRV-001": {"prefix": "A1_SRV_AI_", "power": "001", "current": "002", "energy": "003", "_source": "demo"},
    "SRV-002": {"prefix": "A1_SRV_AI_", "power": "004", "current": "005", "energy": "006", "_source": "demo"},
    "SRV-003": {"prefix": "A1_SRV_AI_", "power": "007", "current": "008", "energy": "009", "_source": "demo"},
    "SRV-004": {"prefix": "A1_SRV_AI_", "power": "010", "current": "011", "energy": "012", "_source": "demo"},
    # 网络机柜 NET-001 -> A1_NET_AI_001~003
    "NET-001": {"prefix": "A1_NET_AI_", "power": "001", "current": "002", "energy": "003", "_source": "demo"},
    # 存储机柜 STO-001 -> A1_STO_AI_001~003
    "STO-001": {"prefix": "A1_STO_AI_", "power": "001", "current": "002", "energy": "003", "_source": "demo"},
    # UPS主机（统一编码）
    "UPS-F1-01": {"prefix": "A1_UPS_AI_", "power": "002", "current": "003", "_source": "demo"},
    "UPS-F1-02": {"prefix": "A1_UPS_AI_", "power": "006", "current": "007", "_source": "demo"},
    # 照明 LIGHT-001 -> A1_LIGHT_AI_001~003
    "LIGHT-001": {"prefix": "A1_LIGHT_AI_", "power": "001", "current": "002", "_source": "demo"},
    # 冷水机组（统一编码）
    "CH-F1-01": {"prefix": "B1_CH_AI_", "power": "005", "current": "007", "_source": "demo"},
    "CH-F1-02": {"prefix": "B1_CH_AI_", "power": "015", "current": "017", "_source": "demo"},
    # 冷却塔（统一编码）
    "CT-F1-01": {"prefix": "B1_CT_AI_", "power": "005", "_source": "demo"},
    "CT-F1-02": {"prefix": "B1_CT_AI_", "power": "006", "_source": "demo"},
    # 冷冻水泵（统一编码）
    "PMP-F1-01": {"prefix": "B1_CHWP_AI_", "power": "005", "current": "002", "_source": "demo"},
    "PMP-F1-02": {"prefix": "B1_CHWP_AI_", "power": "006", "current": "004", "_source": "demo"},
    # 冷却水泵（统一编码）
    "PMP-F1-07": {"prefix": "B1_CWP_AI_", "power": "005", "current": "002", "_source": "demo"},
    "PMP-F1-08": {"prefix": "B1_CWP_AI_", "power": "006", "current": "004", "_source": "demo"},
    # F1 UPS（统一编码）
    "UPS-F1-03": {"prefix": "F1_UPS_AI_", "power": "0013", "_source": "demo"},
    "UPS-F1-04": {"prefix": "F1_UPS_AI_", "power": "0023", "_source": "demo"},
    "F2-UPS-001": {"prefix": "F2_UPS_AI_", "power": "0013", "_source": "demo"},
    "F2-UPS-002": {"prefix": "F2_UPS_AI_", "power": "0023", "_source": "demo"},
    "F3-UPS-001": {"prefix": "F3_UPS_AI_", "power": "0013", "_source": "demo"},
    # F1/F2/F3 精密空调使用回风温度点位
    "F1-AC-001": {"prefix": "F1_AC_AI_", "power": "0011", "_source": "demo"},
    "F1-AC-002": {"prefix": "F1_AC_AI_", "power": "0021", "_source": "demo"},
    "F1-AC-003": {"prefix": "F1_AC_AI_", "power": "0031", "_source": "demo"},
    "F1-AC-004": {"prefix": "F1_AC_AI_", "power": "0041", "_source": "demo"},
    "F2-AC-001": {"prefix": "F2_AC_AI_", "power": "0011", "_source": "demo"},
    "F2-AC-002": {"prefix": "F2_AC_AI_", "power": "0021", "_source": "demo"},
    "F2-AC-003": {"prefix": "F2_AC_AI_", "power": "0031", "_source": "demo"},
    "F2-AC-004": {"prefix": "F2_AC_AI_", "power": "0041", "_source": "demo"},
    "F3-AC-001": {"prefix": "F3_AC_AI_", "power": "0011", "_source": "demo"},
    "F3-AC-002": {"prefix": "F3_AC_AI_", "power": "0021", "_source": "demo"},
}


def register_demo_rules():
    """注册 Demo 规则到主系统"""
    try:
        from app.services.point_device_matcher import MatcherRegistry

        MatcherRegistry.register(DEMO_LEGACY_RULES, source="demo")
        logger.info("✓ Demo legacy 规则注册成功")
    except Exception as e:
        logger.error(f"✗ Demo legacy 规则注册失败: {e}")
        # 不抛出异常，允许 demo 继续启动


def unregister_demo_rules():
    """卸载 Demo 规则"""
    try:
        from app.services.point_device_matcher import MatcherRegistry

        MatcherRegistry.unregister(source="demo")
        logger.info("✓ Demo legacy 规则卸载成功")
    except Exception as e:
        logger.error(f"✗ Demo legacy 规则卸载失败: {e}")
