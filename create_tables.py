"""
create_tables.py
─────────────────────────────────────────
Creates ONLY the new chatbot tables:
  ✅ complaint          (new - logged complaints)
  ✅ conversation_state (new - multi-step chat tracking)

Tables NOT created here (import from SQL files instead):
  ⏩ resources       ← import facility_resources.sql in HeidiSQL
  ⏩ lab_incharge    ← import lab_incharge.sql in HeidiSQL

Usage:
    python create_tables.py
"""

from sqlalchemy import text
from app.chatbot.db import engine, Base, SessionLocal
from app.chatbot import models  # registers all models

def create_tables():
    print("Recreating chatbot tables with latest schema...")

    # Drop and recreate complaint + conversation_state
    # (resources and lab_incharge come from SQL imports — not touched here)
    models.Complaint.__table__.drop(bind=engine, checkfirst=True)
    models.ConversationState.__table__.drop(bind=engine, checkfirst=True)

    models.Complaint.__table__.create(bind=engine)
    models.ConversationState.__table__.create(bind=engine)

    print("  ✅ complaint  (with location_name, location_id)")
    print("  ✅ conversation_state")
    print("\n✅ Done! Schema updated from teammate's latest version.")


if __name__ == "__main__":
    create_tables()

