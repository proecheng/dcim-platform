"""测试时段分类修复"""

# 模拟电价配置
class PricingRecord:
    def __init__(self, period_type, start_time, end_time):
        self.period_type = period_type
        self.start_time = start_time
        self.end_time = end_time

pricing_records = [
    PricingRecord("deep_valley", "00:00", "06:00"),
    PricingRecord("valley", "06:00", "07:00"),
    PricingRecord("flat", "07:00", "08:00"),
    PricingRecord("peak", "08:00", "11:00"),
    PricingRecord("sharp", "11:00", "12:00"),
    PricingRecord("peak", "12:00", "14:00"),
    PricingRecord("flat", "14:00", "18:00"),
    PricingRecord("sharp", "18:00", "19:00"),
    PricingRecord("peak", "19:00", "21:00"),
    PricingRecord("flat", "21:00", "22:00"),
    PricingRecord("valley", "22:00", "00:00"),  # 跨日时段
]

def _get_period_type_for_hour_old(hour: int, pricing_records) -> str:
    """旧版本（有 bug）"""
    time_str = f"{hour:02d}:00"
    for p in pricing_records:
        start = p.start_time
        end = p.end_time
        if start <= end:
            if start <= time_str < end:
                pt = p.period_type.lower()
                if pt in ("sharp", "peak"):
                    return "peak"
                elif pt in ("valley", "deep_valley"):
                    return "valley"
                else:
                    return "normal"
        else:
            if time_str >= start or time_str < end:
                pt = p.period_type.lower()
                if pt in ("sharp", "peak"):
                    return "peak"
                elif pt in ("valley", "deep_valley"):
                    return "valley"
                else:
                    return "normal"
    return "normal"

def _get_period_type_for_hour_new(hour: int, pricing_records) -> str:
    """新版本（已修复）"""
    time_str = f"{hour:02d}:00"
    for p in pricing_records:
        start = p.start_time
        end = p.end_time
        
        # 将 00:00 视为 24:00 以正确处理跨日时段
        if end == "00:00":
            end = "24:00"
        
        # 处理跨日时段（如 22:00 - 24:00）
        if start < end:
            if start <= time_str < end:
                pt = p.period_type.lower()
                if pt in ("sharp", "peak"):
                    return "peak"
                elif pt in ("valley", "deep_valley"):
                    return "valley"
                else:
                    return "normal"
        else:
            # 跨日时段（如 23:00 - 07:00，但这种情况现在不应该出现）
            if time_str >= start or time_str < end:
                pt = p.period_type.lower()
                if pt in ("sharp", "peak"):
                    return "peak"
                elif pt in ("valley", "deep_valley"):
                    return "valley"
                else:
                    return "normal"
    return "normal"

print("=" * 60)
print("时段分类测试 - 对比旧版本和新版本")
print("=" * 60)

print("\n小时 | 旧版本结果 | 新版本结果 | 预期结果")
print("-" * 60)

expected = {
    0: "valley", 1: "valley", 2: "valley", 3: "valley", 4: "valley", 5: "valley",
    6: "valley", 7: "normal", 8: "peak", 9: "peak", 10: "peak", 11: "peak",
    12: "peak", 13: "peak", 14: "normal", 15: "normal", 16: "normal", 17: "normal",
    18: "peak", 19: "peak", 20: "peak", 21: "normal", 22: "valley", 23: "valley"
}

old_results = {}
new_results = {}
for hour in range(24):
    old = _get_period_type_for_hour_old(hour, pricing_records)
    new = _get_period_type_for_hour_new(hour, pricing_records)
    exp = expected[hour]
    
    old_results[old] = old_results.get(old, 0) + 1
    new_results[new] = new_results.get(new, 0) + 1
    
    status = "OK" if new == exp else "FAIL"
    print(f"{hour:2d}   | {old:6s}     | {new:6s}     | {exp:6s}  {status}")

print("\n" + "=" * 60)
print("统计结果")
print("=" * 60)

print("\n旧版本分布：")
for period, count in sorted(old_results.items()):
    print(f"  {period}: {count} 小时")

print("\n新版本分布：")
for period, count in sorted(new_results.items()):
    print(f"  {period}: {count} 小时")

print("\n预期分布：")
expected_dist = {}
for v in expected.values():
    expected_dist[v] = expected_dist.get(v, 0) + 1
for period, count in sorted(expected_dist.items()):
    print(f"  {period}: {count} 小时")
