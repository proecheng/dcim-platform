import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('backend/dcim.db')
cursor = conn.cursor()

# 昨天的时间范围
yesterday = datetime.now() - timedelta(days=1)
start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
end = start + timedelta(days=1)

print(f'查询时间范围: {start} 到 {end}')

cursor.execute(
    'SELECT COUNT(*) FROM point_history WHERE recorded_at >= ? AND recorded_at < ?',
    (start.isoformat(), end.isoformat())
)
count = cursor.fetchone()[0]
print(f'该时间范围内的记录数: {count}')

if count > 0:
    cursor.execute(
        'SELECT point_id, value, recorded_at FROM point_history WHERE recorded_at >= ? AND recorded_at < ? LIMIT 5',
        (start.isoformat(), end.isoformat())
    )
    print('\n前 5 条记录:')
    for r in cursor.fetchall():
        print(f'  point_id={r[0]}, value={r[1]}, time={r[2]}')
else:
    print('\n[WARNING] 昨天没有历史数据！')
    
    # 检查所有数据的时间范围
    cursor.execute('SELECT MIN(recorded_at), MAX(recorded_at) FROM point_history')
    min_time, max_time = cursor.fetchone()
    print(f'\n历史数据时间范围: {min_time} 到 {max_time}')

conn.close()
