import pymysql
import pymysql.cursors
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "internship_db"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "cursorclass": pymysql.cursors.DictCursor,  # Returns rows as dicts
    "charset":  "utf8mb4",
}


def get_connection():
    """Get a fresh PyMySQL database connection."""
    return pymysql.connect(**DB_CONFIG)


def get_user_by_mobile(mobile_number: str):
    """
    Lookup user in the login table by mobile number.
    Handles both '9764670987' and '+919764670987' formats.
    Returns a dict with user info, or None if not found.
    """
    clean_number = mobile_number.strip()

    # Remove whatsapp: prefix
    if clean_number.startswith("whatsapp:"):
        clean_number = clean_number[len("whatsapp:"):]

    # Remove country code
    if clean_number.startswith("+91"):
        clean_number = clean_number[3:]
    elif clean_number.startswith("+"):
        clean_number = clean_number[1:]

    # Remove spaces/dashes
    clean_number = clean_number.replace(" ", "").replace("-", "")

    # Take last 10 digits as safety net
    if len(clean_number) > 10:
        clean_number = clean_number[-10:]

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT memberid, email, fname, lname, position, is_admin, "
                "mobile, expiry_date, department "
                "FROM login WHERE mobile = %s LIMIT 1",
                (clean_number,)
            )
            user = cursor.fetchone()
        return user

    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None

    finally:
        if conn:
            conn.close()
