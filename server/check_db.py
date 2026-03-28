import sqlite3
import os

DB_PATH = r'd:\jerin\civix\server\civix.db'

def check_schema():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(surveys)")
    columns = cursor.fetchall()
    
    print("Columns in 'surveys' table:")
    for col in columns:
        print(f" - {col[1]} ({col[2]})")
    
    conn.close()

if __name__ == "__main__":
    check_schema()
