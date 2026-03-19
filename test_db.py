from app.database import get_connection, get_users_by_mobile
import os
from dotenv import load_dotenv

def test_connection():
    load_dotenv()
    print("--- DEBUG INFO ---")
    print(f"DB_HOST loading as: {os.getenv('DB_HOST', 'localhost (default)')}")
    print(f"DB_USER loading as: {os.getenv('DB_USER', 'root (default)')}")
    print(f"DB_NAME loading as: {os.getenv('DB_NAME', 'slotbooking (default)')}")
    print("If DB_NAME says 'slotbooking (default)' when it shouldn't, it means your .env file is missing, misnamed, or not being read!")
    print("------------------\n")

    try:
        # Test raw connection
        conn = get_connection()
        print("[SUCCESS] DB connected successfully!")
        conn.close()
        
        # Test a query
        test_number = input("\nEnter your WhatsApp number to test (e.g. 9876543210): ")
        users = get_users_by_mobile(test_number)
        user = users[0] if users else None
        if user:
            print("\n[SUCCESS] User found!")
            print(f"Name: {user['fname']}")
            print(f"Role: {user['position']}")
            print(f"Expiry Date: {user.get('expiry_date')}")
        else:
            print(f"\n[WARNING] User with number {test_number} not found in the 'login' table.")

        # Test unknown number
        unknown = get_users_by_mobile("0000000000")
        if not unknown:
            print("[SUCCESS] Correctly returned None for unknown number")
            
    except Exception as e:
        print(f"\n[ERROR] DB Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
