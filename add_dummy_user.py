import mysql.connector
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

try:
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "slotbooking")
    )
    cursor = db.cursor(dictionary=True)
    
    # ── 1. Fetch exact table schema to see what's required ──
    cursor.execute("DESCRIBE login")
    columns = cursor.fetchall()
    
    insert_data = {
        "memberid": str(uuid.uuid4())[:18],
        "fname": "Dummy",
        "lname": "User",
        "email": "test.dummy@example.com",
        "mobile": "8077043887",
        "position": "Tester",
        "password": "dummyhash",
        "expiry_date": "2026-12-31",
    }
    
    # Add dummy data for ANY column that is NOT NULL and lacks a DEFAULT
    for col in columns:
        col_name = col['Field']
        is_nullable = col['Null'] == 'YES'
        has_default = col['Default'] is not None
        is_auto_inc = 'auto_increment' in col['Extra'].lower()
        
        if not is_nullable and not has_default and not is_auto_inc:
            if col_name not in insert_data:
                # Give it a generic fake value based on the column name / type
                insert_data[col_name] = "DUMMY123" if "varchar" in str(col['Type']).lower() else 1
    
    # Check if activation_status exists
    all_col_names = [c["Field"] for c in columns]
    if "activation_status" in all_col_names:
        insert_data["activation_status"] = 1
        
    # ── 2. Build the exact dynamic INSERT query ──
    cols = ", ".join(insert_data.keys())
    placeholders = ", ".join(["%s"] * len(insert_data))
    values = tuple(insert_data.values())
    
    query = f"INSERT INTO login ({cols}) VALUES ({placeholders})"
    
    cursor.execute(query, values)
    db.commit()
    
    print(f"\n✅ Successfully added a second account for '8077043887'!")
    print(f"Name: {insert_data['fname']} {insert_data['lname']}")
    print(f"Email: {insert_data['email']}  <-- Use this to verify in WhatsApp")
    print(f"Extra generated fields: {[k for k in insert_data if k not in ['memberid', 'fname', 'lname', 'email', 'mobile', 'position', 'password', 'expiry_date', 'activation_status']]}")
    print("\nRun: python test_chat.py to test the login!")

except Exception as e:
    print(f"Database error: {e}")

