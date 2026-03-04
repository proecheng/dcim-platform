import sqlite3

conn = sqlite3.connect('backend/dcim.db')
cursor = conn.cursor()

# 检查 energy_hourly 表
cursor.execute('SELECT COUNT(*) FROM energy_hourly')
count = cursor.fetchone()[0]
print(f'energy_hourly 表记录数: {count}')

if count > 0:
    cursor.execute('SELECT device_id, stat_time, avg_power FROM energy_hourly ORDER BY stat_time DESC LIMIT 5')
    print('\n最新 5 条记录:')
    for r in cursor.fetchall():
        print(f'  device_id={r[0]}, time={r[1]}, power={r[2]}')
else:
    print('\n[WARNING] energy_hourly 表为空！')
    print('这就是为什么显示"模拟数据"的原因。')
    
    # 检查 power_devices 表
    cursor.execute('SELECT COUNT(*) FROM power_devices')
    device_count = cursor.fetchone()[0]
    print(f'\npower_devices 表记录数: {device_count}')
    
    if device_count > 0:
        cursor.execute('SELECT id, device_code, device_name FROM power_devices LIMIT 3')
        print('\n前 3 个设备:')
        for r in cursor.fetchall():
            print(f'  id={r[0]}, code={r[1]}, name={r[2]}')

conn.close()
