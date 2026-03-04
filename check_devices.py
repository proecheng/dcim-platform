import sqlite3
conn = sqlite3.connect('dcim.db')
cursor = conn.cursor()
cursor.execute("SELECT id, device_code, device_name, device_type FROM power_devices LIMIT 10")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Code: {row[1]}, Name: {row[2]}, Type: {row[3]}")
conn.close()
