import sqlite3
import os

DB_PATH = 'civix.db'

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    for table in tables:
        name = table[0]
        cursor.execute(f"PRAGMA table_info({name})")
        columns = cursor.fetchall()
        print(f"\nColumns in '{name}':")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
    
    conn.close()

if __name__ == "__main__":
    check_db()
