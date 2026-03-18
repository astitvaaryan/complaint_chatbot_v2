import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()
try:
    db=mysql.connector.connect(
        host=os.getenv('DB_HOST','localhost'),
        user=os.getenv('DB_USER','root'),
        password=os.getenv('DB_PASSWORD',''),
        database=os.getenv('DB_NAME','slotbooking')
    )
    cursor=db.cursor()
    cursor.execute('DESCRIBE login')
    with open('schema_log.txt', 'w') as f:
        for r in cursor.fetchall():
            f.write(f"{r[0]:<15} | {str(r[1]):<15} | Null: {r[2]} | Default: {r[4]}\n")
except Exception as e:
    with open('schema_log.txt', 'w') as f:
        f.write(str(e))
