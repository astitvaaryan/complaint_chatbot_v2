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
            # SAFETY: Ensure persistence tables exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_phone VARCHAR(40) UNIQUE NOT NULL,
                    user_data TEXT NOT NULL,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX (user_phone)
                ) ENGINE=InnoDB;
            """)
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
import json
from datetime import datetime



def get_session(mobile_number: str):
    """Retrieve persistent session from MySQL."""
    clean_number = _clean_mobile(mobile_number)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_data FROM user_sessions WHERE user_phone = %s", (clean_number,))
            res = cursor.fetchone()
            if res:
                return json.loads(res['user_data'])
        return None
    except Exception as e:
        print(f"[DB ERROR] get_session: {e}")
        return None
    finally:
        if conn: conn.close()

def save_session(mobile_number: str, user_dict: dict):
    """Save or update persistent session in MySQL."""
    clean_number = _clean_mobile(mobile_number)
    user_json = json.dumps(user_dict, default=str)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Upsert logic
            cursor.execute("SELECT id FROM user_sessions WHERE user_phone = %s", (clean_number,))
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE user_sessions SET user_data = %s, last_active = NOW() WHERE user_phone = %s",
                    (user_json, clean_number)
                )
            else:
                cursor.execute(
                    "INSERT INTO user_sessions (user_phone, user_data) VALUES (%s, %s)",
                    (clean_number, user_json)
                )
        conn.commit()
    except Exception as e:
        print(f"[DB ERROR] save_session: {e}")
    finally:
        if conn: conn.close()

def delete_session(mobile_number: str):
    """Remove persistent session (logout)."""
    clean_number = _clean_mobile(mobile_number)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM user_sessions WHERE user_phone = %s", (clean_number,))
        conn.commit()
    except Exception as e:
        print(f"[DB ERROR] delete_session: {e}")
    finally:
        if conn: conn.close()

def get_pending_ver(mobile_number: str):
    """Retrieve pending email verification state from MySQL."""
    clean_number = _clean_mobile(mobile_number)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT candidates_data, attempts FROM pending_email_ver_persistent WHERE user_phone = %s", (clean_number,))
            res = cursor.fetchone()
            if res:
                return {
                    "candidates": json.loads(res['candidates_data']),
                    "attempts": res['attempts']
                }
        return None
    except Exception as e:
        print(f"[DB ERROR] get_pending_ver: {e}")
        return None
    finally:
        if conn: conn.close()

def save_pending_ver(mobile_number: str, candidates: list, attempts: int):
    """Save or update pending verification state."""
    clean_number = _clean_mobile(mobile_number)
    cand_json = json.dumps(candidates, default=str)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM pending_email_ver_persistent WHERE user_phone = %s", (clean_number,))
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE pending_email_ver_persistent SET candidates_data = %s, attempts = %s WHERE user_phone = %s",
                    (cand_json, attempts, clean_number)
                )
            else:
                cursor.execute(
                    "INSERT INTO pending_email_ver_persistent (user_phone, candidates_data, attempts) VALUES (%s, %s, %s)",
                    (clean_number, cand_json, attempts)
                )
        conn.commit()
    except Exception as e:
        print(f"[DB ERROR] save_pending_ver: {e}")
    finally:
        if conn: conn.close()

def delete_pending_ver(mobile_number: str):
    """Remove pending verification state."""
    clean_number = _clean_mobile(mobile_number)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM pending_email_ver_persistent WHERE user_phone = %s", (clean_number,))
        conn.commit()
    except Exception as e:
        print(f"[DB ERROR] delete_pending_ver: {e}")
    finally:
        if conn: conn.close()
