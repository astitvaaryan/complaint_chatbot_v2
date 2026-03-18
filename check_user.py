import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

try:
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "slotbooking")
    )
    cursor = db.cursor(dictionary=True)
    
    mobile = "8077043887"
    cursor.execute("SELECT * FROM login WHERE mobile=%s", (mobile,))
    rows = cursor.fetchall()
    
    print(f"\n==============================================")
    print(f"FOUND {len(rows)} ACCOUNT(S) WITH MOBILE: {mobile}")
    print(f"==============================================\n")
    
    for i, row in enumerate(rows, 1):
        print(f"Account {i}:")
        print(f"  Name:     {row.get('fname', '')} {row.get('lname', '')}")
        print(f"  Email:    {row.get('email', '')}")
        print(f"  Position: {row.get('position', '')}")
        print("-" * 30)

except Exception as e:
    print(f"Database error: {e}")
