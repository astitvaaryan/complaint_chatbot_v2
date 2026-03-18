import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def list_tables():
    try:
        db = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'slotbooking'),
            port=os.getenv('DB_PORT', '3306')
        )
        cursor = db.cursor()
        
        cursor.execute("SHOW TABLES")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables in '{os.getenv('DB_NAME')}': {tables}")
        
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_tables()
