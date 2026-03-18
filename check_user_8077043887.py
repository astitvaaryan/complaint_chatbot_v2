
from app.database import get_connection

def check_user_details():
    mobile = "8077043887"
    conn = get_connection()
    if not conn:
        print("Could not connect to database.")
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT memberid, email, fname, lname, is_admin FROM login WHERE mobile = %s", (mobile,))
            users = cursor.fetchall()
            if users:
                print(f"✅ Found {len(users)} users for mobile {mobile}:")
                for i, user in enumerate(users, 1):
                    print(f"   [{i}] Member ID:  {user.get('memberid')}")
                    print(f"       Email:      {user.get('email')}")
                    print(f"       Full Name:  {user.get('fname')} {user.get('lname')}")
                    print(f"       Is Admin:   {user.get('is_admin')}")
                    print("-" * 20)
            else:
                print(f"❌ No user found for mobile {mobile}")
    except Exception as e:
        print(f"❌ Error checking user: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_user_details()
