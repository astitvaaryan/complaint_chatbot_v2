
import pymysql
import os
import json
from dotenv import load_dotenv

load_dotenv()

def fix():
    DB_CONFIG = {
        "host":     os.getenv("DB_HOST", "localhost"),
        "user":     os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "slotbooking"),
        "port":     int(os.getenv("DB_PORT", 3306)),
        "charset":  "utf8mb4",
    }
    
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            # 1. Ensure tables exist
            cursor.execute("DROP TABLE IF EXISTS user_sessions")
            cursor.execute("DROP TABLE IF EXISTS pending_email_ver_persistent")
            
            cursor.execute("""
                CREATE TABLE user_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_phone VARCHAR(40) UNIQUE NOT NULL,
                    user_data TEXT NOT NULL,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
            """)
            
            cursor.execute("""
                CREATE TABLE pending_email_ver_persistent (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_phone VARCHAR(40) UNIQUE NOT NULL,
                    candidates_data TEXT NOT NULL,
                    attempts INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
            """)
            
            # 2. Fix the email address for Astitva
            # Let's see what the current emails are first
            cursor.execute("SELECT email, fname FROM login WHERE mobile = '8077043887'")
            users = cursor.fetchall()
            print(f"Current users: {users}")
            
            # Update both to be safe or just the right one
            cursor.execute("UPDATE login SET email = 'astitvaaryan08@gmail.com' WHERE mobile = '8077043887' AND fname = 'Astitva'")
            
        conn.commit()
        print("✅ DB Fixed and Cleaned!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix()
