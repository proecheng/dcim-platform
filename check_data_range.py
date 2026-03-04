import sqlite3

conn = sqlite3.connect(r'D:\mytest1\backend\dcim.db')
cursor = conn.cursor()

# 查询小时数据的时间范围
cursor.execute('SELECT MIN(stat_time), MAX(stat_time), COUNT(*) FROM energy_hourly')
min_time, max_time, count = cursor.fetchone()
print(f"小时数据范围: {min_time} 到 {max_time}")
print(f"总记录数: {count}")

# 查询每天的记录数
cursor.execute("""
    SELECT DATE(stat_time) as date, COUNT(*) as count
    FROM energy_hourly
    GROUP BY DATE(stat_time)
    ORDER BY date DESC
    LIMIT 10
""")
print("\n每天的小时数据记录数:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} 条")

conn.close()
