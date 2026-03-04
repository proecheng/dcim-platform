import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('backend/dcim.db')
cursor = conn.cursor()

# 总记录数
cursor.execute('SELECT COUNT(*) FROM point_history')
count = cursor.fetchone()[0]
print(f'PointHistory 记录数: {count}')

if count > 0:
    # 最新 5 条
    cursor.execute('SELECT point_id, value, recorded_at FROM point_history ORDER BY recorded_at DESC LIMIT 5')
    print('\n最新 5 条记录:')
    for r in cursor.fetchall():
        print(f'  point_id={r[0]}, value={r[1]}, time={r[2]}')
    
    # 昨天的记录数
    yesterday = datetime.now() - timedelta(days=1)
    start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_time = (yesterday.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
    
    cursor.execute(
        'SELECT COUNT(*) FROM point_history WHERE recorded_at >= ? AND recorded_at < ?',
        (start_time, end_time)
    )
    yesterday_count = cursor.fetchone()[0]
    print(f'\n昨天的记录数: {yesterday_count}')
else:
    print('\n[WARNING] PointHistory 表为空！')

conn.close()
