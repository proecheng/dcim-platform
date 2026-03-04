import sqlite3

conn = sqlite3.connect('backend/dcim.db')
cursor = conn.cursor()

# 获取启用的 AI 类型点位
cursor.execute("SELECT id, point_code, point_name, point_type FROM points WHERE is_enabled = 1 AND point_type = 'AI' LIMIT 5")
points = cursor.fetchall()

print('启用的 AI 点位:')
for r in points:
    print(f'  id={r[0]}, code={r[1]}, name={r[2]}, type={r[3]}')

if points:
    pid = points[0][0]
    print(f'\n测试 point_id={pid} 的统计查询:')
    
    cursor.execute(
        "SELECT MIN(value), MAX(value), AVG(value) FROM point_history WHERE point_id = ? AND recorded_at >= '2026-03-01 00:00:00' AND recorded_at < '2026-03-02 00:00:00'",
        (pid,)
    )
    stats = cursor.fetchone()
    print(f'  min={stats[0]}, max={stats[1]}, avg={stats[2]}')
    
    if stats[0] is None:
        print('\n[WARNING] 统计结果为 NULL！')
        print('检查该点位是否有历史数据...')
        
        cursor.execute(
            "SELECT COUNT(*) FROM point_history WHERE point_id = ?",
            (pid,)
        )
        count = cursor.fetchone()[0]
        print(f'  该点位总历史记录数: {count}')
        
        cursor.execute(
            "SELECT COUNT(*) FROM point_history WHERE point_id = ? AND recorded_at >= '2026-03-01 00:00:00' AND recorded_at < '2026-03-02 00:00:00'",
            (pid,)
        )
        count_yesterday = cursor.fetchone()[0]
        print(f'  昨天的记录数: {count_yesterday}')

conn.close()
