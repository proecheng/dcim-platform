import sqlite3

conn = sqlite3.connect(r'D:\mytest1\backend\dcim.db')
cursor = conn.cursor()

# 查询今天各时段的数据分布
cursor.execute("""
    SELECT 
        CAST(strftime('%H', stat_time) AS INTEGER) as hour,
        SUM(total_energy) as total_energy
    FROM energy_hourly
    WHERE DATE(stat_time) = '2026-03-01'
    GROUP BY hour
    ORDER BY hour
""")

print("2026-03-01 各小时电量分布:")
print("\n小时 | 总电量 (kWh)")
print("-" * 30)

total = 0
for row in cursor.fetchall():
    hour, energy = row
    total += energy
    print(f"{hour:02d}:00 | {energy:.2f}")

print(f"\n总计: {total:.2f} kWh")

# 模拟时段分类
pricing_config = [
    ("deep_valley", "00:00", "06:00"),
    ("valley", "06:00", "07:00"),
    ("flat", "07:00", "08:00"),
    ("peak", "08:00", "11:00"),
    ("sharp", "11:00", "12:00"),
    ("peak", "12:00", "14:00"),
    ("flat", "14:00", "18:00"),
    ("sharp", "18:00", "19:00"),
    ("peak", "19:00", "21:00"),
    ("flat", "21:00", "22:00"),
    ("valley", "22:00", "24:00"),
]

def get_period(hour):
    time_str = f"{hour:02d}:00"
    for period_type, start, end in pricing_config:
        if end == "24:00":
            end = "00:00"
            if time_str >= start or time_str < end:
                return period_type
        else:
            if start <= time_str < end:
                return period_type
    return "flat"

# 重新查询并分类
cursor.execute("""
    SELECT 
        CAST(strftime('%H', stat_time) AS INTEGER) as hour,
        SUM(total_energy) as total_energy
    FROM energy_hourly
    WHERE DATE(stat_time) = '2026-03-01'
    GROUP BY hour
    ORDER BY hour
""")

peak_energy = 0
normal_energy = 0
valley_energy = 0

print("\n\n按时段分类:")
print("\n小时 | 时段类型 | 电量 (kWh)")
print("-" * 40)

for row in cursor.fetchall():
    hour, energy = row
    period = get_period(hour)
    
    if period in ("sharp", "peak"):
        category = "peak"
        peak_energy += energy
    elif period in ("valley", "deep_valley"):
        category = "valley"
        valley_energy += energy
    else:
        category = "normal"
        normal_energy += energy
    
    print(f"{hour:02d}:00 | {period:12s} | {energy:.2f} ({category})")

print(f"\n汇总:")
print(f"  峰时电量: {peak_energy:.2f} kWh")
print(f"  平时电量: {normal_energy:.2f} kWh")
print(f"  谷时电量: {valley_energy:.2f} kWh")

conn.close()
