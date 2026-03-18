import os
from dotenv import load_dotenv
import pymysql

load_dotenv('.env')

conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'slotbooking'),
    port=int(os.getenv('DB_PORT', 3306))
)
cursor = conn.cursor(pymysql.cursors.DictCursor)

duplicate_mobile = '8077043887'
cursor.execute('SELECT memberid FROM login WHERE mobile = %s ORDER BY memberid DESC', (duplicate_mobile,))
users = cursor.fetchall()

if len(users) > 1:
    # Keep the latest, change the older ones
    for old_user in users[1:]:
        memberid = old_user['memberid']
        cursor.execute("UPDATE login SET mobile = CONCAT('old_', mobile) WHERE memberid = %s", (memberid,))
        print(f"Disabled old duplicate account: memberid {memberid}")

conn.commit()
conn.close()
print("Duplicate cleanup complete.")
