import sqlite3
import os

def migrate():
    db_path = 'hotel.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("--- Starting Phase 14 Migration ---")

    # 1. Update hotels table
    c.execute("PRAGMA table_info(hotels)")
    hotel_cols = [col[1] for col in c.fetchall()]
    
    if 'google_review_url' not in hotel_cols:
        print("Adding google_review_url to hotels...")
        c.execute("ALTER TABLE hotels ADD COLUMN google_review_url TEXT")
    
    if 'housekeeping_token' not in hotel_cols:
        print("Adding housekeeping_token to hotels...")
        import secrets
        c.execute("ALTER TABLE hotels ADD COLUMN housekeeping_token TEXT")
        # Initialize tokens for existing hotels
        c.execute("SELECT id FROM hotels")
        for h_id in [h[0] for h in c.fetchall()]:
            token = secrets.token_urlsafe(16)
            c.execute("UPDATE hotels SET housekeeping_token = ? WHERE id = ?", (token, h_id))
            
    if 'currency_symbol' not in hotel_cols:
        print("Adding currency_symbol to hotels...")
        c.execute("ALTER TABLE hotels ADD COLUMN currency_symbol TEXT DEFAULT '₹'")

    if 'tax_rate' not in hotel_cols:
        print("Adding tax_rate to hotels...")
        c.execute("ALTER TABLE hotels ADD COLUMN tax_rate REAL DEFAULT 0.0")
    
    # 2. Update users table
    c.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in c.fetchall()]
    
    if 'is_2fa_enabled' not in user_cols:
        print("Adding is_2fa_enabled to users...")
        c.execute("ALTER TABLE users ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0")
    
    if 'last_backup_sent' not in user_cols:
        print("Adding last_backup_sent to users...")
        c.execute("ALTER TABLE users ADD COLUMN last_backup_sent TEXT")

    # 3. Update bookings table
    c.execute("PRAGMA table_info(bookings)")
    booking_cols = [col[1] for col in c.fetchall()]
    for col_name in ['extra_charges', 'food', 'laundry', 'water_bottle', 'car_wash']:
        if col_name not in booking_cols:
            print(f"Adding {col_name} to bookings...")
            c.execute(f"ALTER TABLE bookings ADD COLUMN {col_name} REAL DEFAULT 0")

    # 4. Create announcements table
    print("Ensuring announcements table exists...")
    c.execute('''CREATE TABLE IF NOT EXISTS announcements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  message TEXT,
                  type TEXT DEFAULT 'info',
                  is_active INTEGER DEFAULT 1,
                  created_at TEXT)''')

    # 5. Create audit_logs table
    print("Ensuring audit_logs table exists...")
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  user_id INTEGER,
                  action TEXT,
                  details TEXT,
                  timestamp TEXT,
                  ip_address TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    conn.commit()
    conn.close()
    print("--- Migration Successful! ---")

if __name__ == '__main__':
    migrate()
