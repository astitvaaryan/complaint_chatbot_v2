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
    cursor=db.cursor(dictionary=True)
    cursor.execute('SELECT name, category FROM resources')
    rows = cursor.fetchall()
    with open('resources_out.txt', 'w') as f:
        f.write(f"Total Resources: {len(rows)}\n")
        f.write("SAMPLE:\n")
        for r in rows[:20]:
            f.write(f"{r['name']} | {r['category']}\n")
        f.write("\nUNIQUE CATEGORIES:\n")
        categories = set(r['category'] for r in rows if r['category'])
        for c in categories:
            f.write(f"{c}\n")
except Exception as e:
    with open('resources_out.txt', 'w') as f:
        f.write(str(e))
