import sys
import sqlite3
import os

def force_reset_admin(db_path):
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        sys.exit(1)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_credentials;")
        conn.commit()
        print("已清空 admin_credentials 表的数据。")
    except Exception as e:
        print(f"操作失败: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python force_reset_admin.py <sqlite数据库文件路径>")
        sys.exit(1)
    db_path = sys.argv[1]
    force_reset_admin(db_path)
