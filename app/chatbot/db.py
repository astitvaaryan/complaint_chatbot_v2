"""
app/chatbot/db.py
─────────────────────────────────────────
SQLAlchemy database engine for the chatbot logic.
Uses the same MySQL DB as the login system.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

# Validate required environment variables at startup
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "slotbooking")

if not DB_USER:
    raise RuntimeError("FATAL: DB_USER is not set in .env. Server cannot start.")
if not DB_PASSWORD:
    raise RuntimeError("FATAL: DB_PASSWORD is not set in .env. Server cannot start.")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
