from app.database import get_db_connection, get_user_by_mobile

def test_connection():
    try:
        conn = get_db_connection()
        print("✅ DB connected successfully!")
        
        # Test a query
        user = get_user_by_mobile(conn, "9894254006")
        if user:
            print("✅ User found!")
            print(f"Name: {user['fname']}")
            print(f"Role: {user['position']}")
        else:
            print("⚠️ User not found. Did you add the test user?")

        # Test unknown number
        unknown = get_user_by_mobile(conn, "0000000000")
        if not unknown:
            print("✅ Correctly returned None for unknown number")
            
        conn.close()
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
