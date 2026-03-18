import os
import pymysql
from dotenv import load_dotenv

load_dotenv('.env')

try:
    conn = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'slotbooking'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    cursor = conn.cursor()
    cursor.execute("DESCRIBE resources")
    columns = cursor.fetchall()
    print("\n--- Resources Table Columns ---")
    for col in columns:
        print(col)
    
    cursor.execute("SELECT machid, name, location FROM resources WHERE name LIKE '%RIE%' LIMIT 10")
    machines = cursor.fetchall()
    print("\n--- Samples of RIE machines ---")
    for m in machines:
        print(m)
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
