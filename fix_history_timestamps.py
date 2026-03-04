# -*- coding: utf-8 -*-
"""
修复历史数据时间戳问题
将无效的时间戳更新为有效的日期时间
"""
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('backend/dcim.db')
cursor = conn.cursor()

print("=" * 80)
print("修复历史数据时间戳")
print("=" * 80)

# 检查当前状态
cursor.execute('SELECT COUNT(*) FROM point_history')
total_count = cursor.fetchone()[0]
print(f'\n总记录数: {total_count}')

cursor.execute('SELECT MIN(recorded_at), MAX(recorded_at) FROM point_history')
min_time, max_time = cursor.fetchone()
print(f'当前时间范围: {min_time} 到 {max_time}')

# 检查无效时间戳的记录数
cursor.execute("SELECT COUNT(*) FROM point_history WHERE recorded_at < '2020-01-01'")
invalid_count = cursor.fetchone()[0]
print(f'无效时间戳记录数: {invalid_count}')

if invalid_count > 0:
    print(f'\n[WARNING] 发现 {invalid_count} 条无效时间戳记录')
    print('这些记录将被删除...')
    
    cursor.execute("DELETE FROM point_history WHERE recorded_at < '2020-01-01'")
    conn.commit()
    print(f'[OK] 已删除 {invalid_count} 条无效记录')

# 重新检查
cursor.execute('SELECT COUNT(*) FROM point_history')
new_total = cursor.fetchone()[0]
print(f'\n修复后总记录数: {new_total}')

cursor.execute('SELECT MIN(recorded_at), MAX(recorded_at) FROM point_history')
min_time, max_time = cursor.fetchone()[0], cursor.fetchone()[0]
print(f'修复后时间范围: {min_time} 到 {max_time}')

# 检查昨天的数据
yesterday = datetime.now() - timedelta(days=1)
start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
end = start + timedelta(days=1)

cursor.execute(
    'SELECT COUNT(*) FROM point_history WHERE recorded_at >= ? AND recorded_at < ?',
    (start.isoformat(), end.isoformat())
)
yesterday_count = cursor.fetchone()[0]
print(f'\n昨天的记录数: {yesterday_count}')

if yesterday_count == 0:
    print('\n[INFO] 昨天仍然没有数据')
    print('建议：等待数据模拟器生成新的历史数据，或者使用演示数据刷新功能')

conn.close()

print("\n" + "=" * 80)
print("修复完成")
print("=" * 80)
