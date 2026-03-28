import sqlite3
import os

DB_PATH = 'civix.db'

def check_db():
    output = []
    if not os.path.exists(DB_PATH):
        output.append(f"Error: Database not found at {DB_PATH}")
    else:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        output.append(f"Tables: {tables}")
        
        for table in tables:
            name = table[0]
            cursor.execute(f"PRAGMA table_info({name})")
            columns = cursor.fetchall()
            output.append(f"\nColumns in '{name}':")
            for col in columns:
                output.append(f"  - {col[1]} ({col[2]})")
        
        conn.close()
    
    with open('db_info.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))

if __name__ == "__main__":
    check_db()
