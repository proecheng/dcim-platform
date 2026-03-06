"""
L1 引擎测试脚本 - Story 24.1
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.diagnosis import L1RuleEngine
from app.core.redis import redis_service


async def test_l1_engine():
    """测试 L1 引擎基本功能"""
    print("=== L1 引擎测试 ===\n")

    # 1. 连接 Redis
    print("1. 连接 Redis...")
    await redis_service.connect("redis://localhost:6379/0")
    if not redis_service.is_available:
        print("   警告: Redis 不可用，测试将使用模拟数据")
    else:
        print("   [OK] Redis 连接成功")

    # 2. 初始化 L1 引擎
    print("\n2. 初始化 L1 引擎...")
    l1_engine = L1RuleEngine(redis_service)
    await l1_engine.load_rules()
    print(f"   [OK] 加载了 {sum(len(rules) for rules in l1_engine.rule_index.values())} 条规则")
    print(f"   [OK] 类别: {list(l1_engine.rule_index.keys())}")

    # 3. 测试规则匹配（模拟告警事件）
    print("\n3. 测试规则匹配...")

    # 测试用例 1: UPS 电池低压（应该匹配 L1_R001）
    if redis_service.is_available:
        await redis_service.set("point:ups_battery_voltage:value", "42.5")

    alarm_event_1 = {
        "device_id": "ups_001",
        "device_category": "power/ups",
        "alarm_level": "critical"
    }

    result_1 = await l1_engine.match_rules(alarm_event_1)
    print(f"\n   测试用例 1: UPS 电池低压")
    print(f"   - 匹配结果: {result_1['matched']}")
    if result_1['matched']:
        print(f"   - 规则编码: {result_1['rule_code']}")
        print(f"   - 结论: {result_1['conclusion']}")
        print(f"   - 置信度: {result_1['confidence']}")
        print(f"   - 推理时间: {result_1['inference_time_ms']} ms")

    # 测试用例 2: 机房温度过高（应该匹配 L1_R003）
    if redis_service.is_available:
        await redis_service.set("point:room_temperature:value", "29.5")

    alarm_event_2 = {
        "device_id": "sensor_001",
        "device_category": "environment/temperature",
        "alarm_level": "major"
    }

    result_2 = await l1_engine.match_rules(alarm_event_2)
    print(f"\n   测试用例 2: 机房温度过高")
    print(f"   - 匹配结果: {result_2['matched']}")
    if result_2['matched']:
        print(f"   - 规则编码: {result_2['rule_code']}")
        print(f"   - 结论: {result_2['conclusion']}")
        print(f"   - 置信度: {result_2['confidence']}")
        print(f"   - 推理时间: {result_2['inference_time_ms']} ms")

    # 测试用例 3: 无匹配规则
    alarm_event_3 = {
        "device_id": "unknown_device",
        "device_category": "unknown/category",
        "alarm_level": "info"
    }

    result_3 = await l1_engine.match_rules(alarm_event_3)
    print(f"\n   测试用例 3: 无匹配规则")
    print(f"   - 匹配结果: {result_3['matched']}")
    print(f"   - 结论: {result_3['conclusion']}")

    # 4. 清理
    print("\n4. 清理资源...")
    await redis_service.close()
    print("   [OK] 测试完成")


if __name__ == "__main__":
    asyncio.run(test_l1_engine())
