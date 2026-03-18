
from app.chatbot.db import engine, Base
from app.chatbot import models

def create_session_tables():
    print("Creating session tables...")
    # This will only create tables that don't exist
    models.UserSession.__table__.create(engine, checkfirst=True)
    models.PendingEmailVerification.__table__.create(engine, checkfirst=True)
    print("✅ Tables 'user_sessions' and 'pending_email_ver_persistent' created successfully.")

if __name__ == "__main__":
    create_session_tables()
