import sqlite3
import os
import shutil

def reset():
    print("--- Starting Full Data Reset ---")
    db_path = 'hotel.db'
    uploads_path = 'static/uploads'

    # 1. Delete Database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"OK: Deleted {db_path}")

    # 2. Clear Uploads (optional)
    try:
        if os.path.exists(uploads_path):
            shutil.rmtree(uploads_path)
            os.makedirs(uploads_path)
            print(f"OK: Cleared {uploads_path}")
    except Exception as e:
        print(f"Note: Could not clear uploads folder ({e}). Skipping...")

    # 3. Re-initialize Database
    print("FIX: Re-initializing fresh database...")
    try:
        from app import init_db
        init_db()
    except ImportError:
        print("Note: App.py not found or init_db failed. Please run 'python app.py' manually.")
    
    print("\n" + "="*30)
    print("RE-SET COMPLETE")
    print("You can now go to /signup to create your fresh account.")
    print("="*30 + "\n")

if __name__ == '__main__':
    reset()
