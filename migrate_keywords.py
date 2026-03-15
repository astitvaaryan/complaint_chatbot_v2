
from app.chatbot.db import engine, SessionLocal
from app.chatbot import models
from app.chatbot.classifier import _migrate_csv_to_db
import os

def run_migration():
    print("--- KEYWORD MIGRATION START ---")
    
    # 1. Ensure the table exists (Alternative to running SQL manually)
    print("Connecting to database and checking table...")
    models.ComplaintKeyword.__table__.create(bind=engine, checkfirst=True)
    
    # 2. Run the extraction logic
    db = SessionLocal()
    try:
        # Check if already populated to avoid duplicates
        existing_count = db.query(models.ComplaintKeyword).count()
        if existing_count > 0:
            print(f"Table already contains {existing_count} keywords. Filtering new ones...")
        
        print("Extracting keywords from CSV files in 'data/' folder...")
        _migrate_csv_to_db(db)
        
        # Verify result
        new_count = db.query(models.ComplaintKeyword).count()
        print(f"\nSUCCESS: Migration finished.")
        print(f"Total keywords now in DB: {new_count}")
        print(f"Newly added: {new_count - existing_count}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Make sure pandas is available (needed for CSV extraction)
    try:
        import pandas
    except ImportError:
        print("Pandas is required for this. Run: pip install pandas")
    else:
        run_migration()
