import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def list_tables_and_search():
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
        print(f"Tables in 'slotbooking': {tables}")
        
        for table in tables:
            try:
                cursor.execute(f"DESCRIBE `{table}`")
                columns = [col[0] for col in cursor.fetchall()]
                search_clauses = []
                for col in columns:
                    search_clauses.append(f"`{col}` LIKE '%TSE%'")
                
                if search_clauses:
                    query = f"SELECT * FROM `{table}` WHERE " + " OR ".join(search_clauses)
                    cursor.execute(query)
                    results = cursor.fetchall()
                    if results:
                        print(f"\n[FOUND] 'TSE' in table '{table}':")
                        for r in results:
                            print(r)
            except Exception as e:
                print(f"Could not search table {table}: {e}")
        
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_tables_and_search()
