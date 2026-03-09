"""
修复精密空调设备命名错误
将 device_type=AC 但使用 CA- 前缀的设备改为 CH- 前缀
"""

import sqlite3
import sys

def fix_cooling_device_names():
    conn = sqlite3.connect('dcim.db')
    cursor = conn.cursor()

    try:
        # 查找所有需要修复的设备
        cursor.execute('''
            SELECT id, device_code, device_name
            FROM devices
            WHERE device_type = 'AC' AND device_code LIKE 'CA-%'
            ORDER BY device_code
        ''')
        devices = cursor.fetchall()

        if not devices:
            print("没有需要修复的设备")
            return

        print(f"找到 {len(devices)} 台需要修复的设备\n")

        # 修复每个设备
        for device_id, old_code, old_name in devices:
            # 将 CA- 改为 CH-（Chiller 制冷机）
            new_code = old_code.replace('CA-', 'CH-')
            # 将"冷通道"改为"制冷机"
            new_name = old_name.replace('冷通道', '制冷机')

            print(f"修复设备 ID={device_id}:")
            print(f"  旧编码: {old_code} -> 新编码: {new_code}")
            print(f"  旧名称: {old_name} -> 新名称: {new_name}")

            cursor.execute('''
                UPDATE devices
                SET device_code = ?, device_name = ?
                WHERE id = ?
            ''', (new_code, new_name, device_id))

        # 提交更改
        conn.commit()
        print(f"\n✅ 成功修复 {len(devices)} 台设备")

    except Exception as e:
        conn.rollback()
        print(f"❌ 修复失败: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    fix_cooling_device_names()
