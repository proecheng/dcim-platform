import sqlite3

conn = sqlite3.connect('dcim.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(points)')
columns = cursor.fetchall()

print("Points 表结构:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()
