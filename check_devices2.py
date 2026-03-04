import sqlite3
conn = sqlite3.connect('dcim.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM power_devices")
count = cursor.fetchone()[0]
print(f"Total devices: {count}")
if count > 0:
    cursor.execute("SELECT id, device_code, device_name, device_type FROM power_devices LIMIT 5")
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Code: {row[1]}, Name: {row[2]}, Type: {row[3]}")
conn.close()
