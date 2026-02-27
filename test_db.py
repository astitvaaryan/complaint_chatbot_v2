from app.database import get_connection, get_user_by_mobile

def test_connection():
    try:
        # Test raw connection
        conn = get_connection()
        print("[SUCCESS] DB connected successfully!")
        conn.close()
        
        # Test a query
        user = get_user_by_mobile("9894254006")
        if user:
            print("[SUCCESS] User found!")
            print(f"Name: {user['fname']}")
            print(f"Role: {user['position']}")
        else:
            print("[WARNING] User not found. Did you add the test user?")

        # Test unknown number
        unknown = get_user_by_mobile("0000000000")
        if not unknown:
            print("[SUCCESS] Correctly returned None for unknown number")
            
    except Exception as e:
        print(f"[ERROR] DB Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
