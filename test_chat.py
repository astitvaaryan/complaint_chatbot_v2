"""
test_chat.py
─────────────────────────────────────
Terminal-based chatbot tester.
Simulates WhatsApp messages without needing Twilio.

Usage:
    python test_chat.py
    python test_chat.py --phone 9764670987
"""

import sys
import argparse
from app.chatbot.engine import get_chatbot_reply
from app.chatbot.db import SessionLocal
from app.chatbot import models

# ── Pick a test user from the DB ──────────────────────────────────
def get_test_user(db, phone: str) -> dict:
    """Fetch a user from the login table by mobile number."""
    from app.database import get_users_by_mobile
    users = get_users_by_mobile(phone)
    if not users:
        print(f"\n❌ No user found with mobile: {phone}")
        print("   Run: python check_db.py  to see available users.\n")
        sys.exit(1)
    return users[0]


def main():
    parser = argparse.ArgumentParser(description="Test chatbot in terminal")
    parser.add_argument(
        "--phone", "-p",
        default=None,
        help="10-digit mobile number of the test user (e.g. 9764670987)"
    )
    args = parser.parse_args()

    # ── Get phone number ──────────────────────────────────────────
    phone = args.phone
    if not phone:
        phone = input("Enter test user mobile number (10 digits): ").strip()

    # ── Lookup user ───────────────────────────────────────────────
    db = SessionLocal()
    try:
        user = get_test_user(db, phone)
    finally:
        db.close()

    print(f"\n{'='*50}")
    print(f"  Chatbot Terminal Tester")
    print(f"  Logged in as: {user['fname']} {user['lname']} ({user['position']})")
    print(f"  Mobile: {phone}")
    print(f"  Type 'cancel' to reset state, 'exit' to quit")
    print(f"{'='*50}\n")

    # ── Chat loop ─────────────────────────────────────────────────
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye! 👋")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "q"]:
            print("\nGoodbye! 👋")
            break

        # Get chatbot reply
        try:
            reply = get_chatbot_reply(user, user_input)
            print(f"\nBot: {reply}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
