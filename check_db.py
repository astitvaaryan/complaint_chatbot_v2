import os
from dotenv import load_dotenv
import pymysql

load_dotenv('.env')

try:
    conn = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'slotbooking'),
        port=int(os.getenv('DB_PORT', 3306))
    )
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute('SELECT memberid, fname, lname, mobile, email, position, expiry_date FROM login')
    users = cursor.fetchall()
    print(f"\n--- Found {len(users)} users in the database ---\n")
    for u in users:
        print(f"ID: {u['memberid']:<2} | Name: {u['fname']} {u['lname']:<10} | Mobile: {u['mobile']:<13} | Email: {u['email']:<20} | Expires: {u['expiry_date']}")
    print("\n-------------------------------------------")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
