import sqlite3
from datetime import datetime

conn = sqlite3.connect('D:\\mytest1\\backend\\dcim.db')
cursor = conn.cursor()

# 查询 2026-02-28 的小时数据
cursor.execute("""
    SELECT stat_time, total_energy 
    FROM energy_hourly 
    WHERE device_id=1 
      AND stat_time >= '2026-02-28 00:00:00' 
      AND stat_time < '2026-03-01 00:00:00' 
    ORDER BY stat_time
""")

rows = cursor.fetchall()
print(f"找到 {len(rows)} 条小时数据")
print("\n时间 | 电量")
print("-" * 30)
for row in rows:
    stat_time = datetime.fromisoformat(row[0])
    energy = row[1]
    print(f"{stat_time.hour:02d}:00 | {energy:.4f} kWh")

conn.close()
