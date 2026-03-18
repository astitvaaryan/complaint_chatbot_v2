
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def force_tables():
    DB_CONFIG = {
        "host":     os.getenv("DB_HOST", "localhost"),
        "user":     os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "slotbooking"),
        "port":     int(os.getenv("DB_PORT", 3306)),
        "charset":  "utf8mb4",
    }
    
    print("Connecting to DB...")
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            print("Creating user_sessions...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_phone VARCHAR(40) UNIQUE NOT NULL,
                    user_data TEXT NOT NULL,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX (user_phone)
                ) ENGINE=InnoDB;
            """)
            
            print("Creating pending_email_ver_persistent...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_email_ver_persistent (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_phone VARCHAR(40) UNIQUE NOT NULL,
                    candidates_data TEXT NOT NULL,
                    attempts INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX (user_phone)
                ) ENGINE=InnoDB;
            """)
        conn.commit()
        print("✅ Tables initialized!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    force_tables()
