import sqlite3
import secrets

def update_schema():
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    
    try:
        # 1. Add housekeeping_token to hotels table
        print("Checking hotels table...")
        # Check if column exists
        c.execute("PRAGMA table_info(hotels)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'housekeeping_token' not in columns:
            print("Adding housekeeping_token column...")
            c.execute("ALTER TABLE hotels ADD COLUMN housekeeping_token TEXT")
            
            # Generate tokens for existing hotels
            c.execute("SELECT id FROM hotels")
            hotels = c.fetchall()
            for hotel in hotels:
                token = secrets.token_urlsafe(16)
                c.execute("UPDATE hotels SET housekeeping_token = ? WHERE id = ?", (token, hotel[0]))
            print(f"Generated tokens for {len(hotels)} hotels.")
        else:
            print("housekeeping_token column already exists.")

        # 2. Create guest_feedback table
        print("Creating guest_feedback table...")
        c.execute('''
            CREATE TABLE IF NOT EXISTS guest_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                message TEXT,
                date TEXT NOT NULL,
                FOREIGN KEY (hotel_id) REFERENCES hotels (id)
            )
        ''')
        print("guest_feedback table ready.")

        conn.commit()
        print("Schema update successful! 🚀")
        
    except Exception as e:
        print(f"Error updating schema: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_schema()
