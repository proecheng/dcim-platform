"""
启用 SQLite WAL 模式的脚本
在后端服务停止时运行
"""
import sqlite3
import sys
from pathlib import Path

db_path = Path(__file__).parent / "dcim.db"

if not db_path.exists():
    print(f"错误: 数据库文件不存在: {db_path}")
    sys.exit(1)

try:
    conn = sqlite3.connect(str(db_path), timeout=5)
    
    # 检查当前模式
    current_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    print(f"当前日志模式: {current_mode}")
    
    if current_mode.lower() == "wal":
        print("✓ 数据库已经是 WAL 模式")
    else:
        # 切换到 WAL 模式
        print("正在切换到 WAL 模式...")
        conn.execute("PRAGMA journal_mode=WAL")
        new_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        print(f"✓ 已切换到: {new_mode}")
        
        # 优化设置
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB
        print("✓ 已应用优化设置")
    
    conn.close()
    print("\n成功！现在可以启动后端服务了。")
    
except sqlite3.OperationalError as e:
    print(f"错误: {e}")
    print("\n请确保:")
    print("1. 后端服务已停止 (运行 stop.bat)")
    print("2. 没有其他程序正在访问数据库")
    sys.exit(1)
