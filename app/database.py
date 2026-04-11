import pymysql
import pymysql.cursors
import os
from dotenv import load_dotenv

load_dotenv()

# Validate required environment variables at startup
_DB_USER = os.getenv("DB_USER")
_DB_PASSWORD = os.getenv("DB_PASSWORD")
_DB_HOST = os.getenv("DB_HOST", "localhost")
_DB_NAME = os.getenv("DB1", "slotbooking")
_DB_PORT = int(os.getenv("DB_PORT", 3306))

if not _DB_USER:
    raise RuntimeError("FATAL: DB_USER is not set in .env. Server cannot start.")
if not _DB_PASSWORD:
    raise RuntimeError("FATAL: DB_PASSWORD is not set in .env. Server cannot start.")

# Database configuration
DB_CONFIG = {
    "host":      _DB_HOST,
    "user":      _DB_USER,
    "password":  _DB_PASSWORD,
    "database":  _DB_NAME,
    "port":      _DB_PORT,
    "cursorclass": pymysql.cursors.DictCursor,
    "charset":   "utf8mb4",
}


def get_connection():
    """Get a fresh PyMySQL database connection."""
    return pymysql.connect(**DB_CONFIG)


def _clean_mobile(mobile_number: str) -> str:
    """
    Normalise a raw number like 'whatsapp:+919764670987' → '9764670987'.
    Shared by all lookup functions.
    """
    number = mobile_number.strip()

    if number.startswith("whatsapp:"):
        number = number[len("whatsapp:"):]
    if number.startswith("+91"):
        number = number[3:]
    elif number.startswith("+"):
        number = number[1:]

    number = number.replace(" ", "").replace("-", "")

    if len(number) > 10:
        number = number[-10:]

    return number


def get_users_by_mobile(mobile_number: str) -> list:
    """
    Return ALL login rows that share this mobile number.

    - Returns []          → number not registered at all
    - Returns [one_user]  → unique match, no email needed
    - Returns [u1, u2, …] → duplicate numbers, email verification required
    """
    clean_number = _clean_mobile(mobile_number)

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT memberid, email, fname, lname, position, is_admin, "
                "mobile, expiry_date, department "
                "FROM login WHERE mobile = %s",
                (clean_number,)
            )
            users = cursor.fetchall()
        return users or []

    except Exception as e:
        print(f"[DB ERROR] get_users_by_mobile: {e}")
        return []

    finally:
        if conn:
            conn.close()


def get_user_by_mobile_and_email(mobile_number: str, email: str):
    """
    When multiple accounts share a mobile number, resolve the correct user
    by checking the email they provided.

    Returns the matching user dict, or None if no match.
    """
    clean_number = _clean_mobile(mobile_number)
    clean_email  = email.strip().lower()

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT memberid, email, fname, lname, position, is_admin, "
                "mobile, expiry_date, department "
                "FROM login WHERE mobile = %s AND LOWER(email) = %s LIMIT 1",
                (clean_number, clean_email)
            )
            user = cursor.fetchone()
        return user

    except Exception as e:
        print(f"[DB ERROR] get_user_by_mobile_and_email: {e}")
        return None

    finally:
        if conn:
            conn.close()
