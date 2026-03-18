import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def describe_tables():
    try:
        db = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'slotbooking'),
            port=os.getenv('DB_PORT', '3306')
        )
        cursor = db.cursor()
        
        for table in ["resources", "eqp-process_resources", "safety_device"]:
            print(f"\n--- {table} ---")
            try:
                cursor.execute(f"DESCRIBE `{table}`")
                columns = cursor.fetchall()
                for col in columns:
                    print(col)
            except Exception as e:
                print(f"Error describing {table}: {e}")
        
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    describe_tables()
