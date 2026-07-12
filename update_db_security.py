import sqlite3
import datetime

def update_schema():
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    
    try:
        print("Checking security tables...")
        
        # 1. Create Audit Logs Table
        c.execute('''CREATE TABLE IF NOT EXISTS audit_logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      hotel_id INTEGER,
                      user_id INTEGER,
                      action TEXT,
                      details TEXT,
                      timestamp TEXT,
                      ip_address TEXT,
                      FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
        print("Created audit_logs table.")

        # 2. Update Users Table
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'is_2fa_enabled' not in columns:
            print("Adding is_2fa_enabled column...")
            c.execute("ALTER TABLE users ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0")
            
        if 'last_backup_sent' not in columns:
            print("Adding last_backup_sent column...")
            c.execute("ALTER TABLE users ADD COLUMN last_backup_sent TEXT")

        # 3. Create Guest Portal Access Table (Optional but good for token management)
        # For now, we use a simple hash of the booking ID or room ID, but let's stick to the plan.
        
        conn.commit()
        print("Security schema update successful! 🛡️")
        
    except Exception as e:
        print(f"Error updating schema: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_schema()
