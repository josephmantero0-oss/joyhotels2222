import sqlite3
import os
import secrets

def sync_database():
    db_path = 'hotel.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found. Are you in the project directory?")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("Starting VPS Database Synchronization...")

    # --- 1. HOTELS TABLE ---
    print("Checking 'hotels' table...")
    c.execute("PRAGMA table_info(hotels)")
    cols = [col[1] for col in c.fetchall()]
    
    alterations = [
        ('is_restaurant_active', 'INTEGER DEFAULT 0'),
        ('is_hotel_active', 'INTEGER DEFAULT 0'),
        ('currency_symbol', "TEXT DEFAULT '₹'"),
        ('tax_rate', 'REAL DEFAULT 0'),
        ('google_review_url', 'TEXT'),
        ('housekeeping_token', 'TEXT'),
        ('email', 'TEXT'),
        ('phone', 'TEXT'),
        ('is_active', 'INTEGER DEFAULT 0'),
        ('utr_ref', 'TEXT')
    ]
    
    for col_name, col_def in alterations:
        if col_name not in cols:
            print(f"Added {col_name} to hotels...")
            try:
                c.execute(f"ALTER TABLE hotels ADD COLUMN {col_name} {col_def}")
            except Exception as e:
                print(f"⚠️ Warning: Could not add {col_name}: {e}")

    # Generate housekeeping tokens if missing
    c.execute("SELECT id, housekeeping_token FROM hotels")
    rows = c.fetchall()
    for row in rows:
        if not row[1]:
            token = secrets.token_urlsafe(16)
            c.execute("UPDATE hotels SET housekeeping_token = ? WHERE id = ?", (token, row[0]))
            print(f"Generated token for hotel ID {row[0]}")

    # --- 2. USERS TABLE ---
    print("Checking 'users' table...")
    c.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in c.fetchall()]
    
    user_alterations = [
        ('is_2fa_enabled', 'INTEGER DEFAULT 0'),
        ('last_backup_sent', 'TEXT'),
        ('role', "TEXT DEFAULT 'owner'")
    ]
    
    for col_name, col_def in user_alterations:
        if col_name not in user_cols:
            print(f"Added {col_name} to users...")
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

    # --- 3. BOOKINGS TABLE ---
    print("Checking 'bookings' table...")
    c.execute("PRAGMA table_info(bookings)")
    booking_cols = [col[1] for col in c.fetchall()]
    
    booking_alterations = [
        ('extra_charges', 'REAL DEFAULT 0'),
        ('food', 'REAL DEFAULT 0'),
        ('laundry', 'REAL DEFAULT 0'),
        ('water_bottle', 'REAL DEFAULT 0'),
        ('car_wash', 'REAL DEFAULT 0')
    ]
    
    for col_name, col_def in booking_alterations:
        if col_name not in booking_cols:
            print(f"Added {col_name} to bookings...")
            c.execute(f"ALTER TABLE bookings ADD COLUMN {col_name} {col_def}")

    # --- 4. GUESTS TABLE ---
    print("Checking 'guests' table...")
    c.execute("PRAGMA table_info(guests)")
    guest_cols = [col[1] for col in c.fetchall()]
    if 'email' not in guest_cols:
        print("Added email to guests...")
        c.execute("ALTER TABLE guests ADD COLUMN email TEXT")

    # --- 5. ENSURE TABLES EXIST ---
    print("Ensuring all required tables exist...")
    
    # Restaurant Tables
    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_menu
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  item_name TEXT,
                  item_code TEXT,
                  price REAL,
                  UNIQUE(hotel_id, item_code),
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_tables
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  table_number TEXT,
                  status TEXT DEFAULT 'available',
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_bills
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  table_id INTEGER,
                  customer_mobile TEXT,
                  total_amount REAL,
                  payment_status TEXT DEFAULT 'unpaid',
                  created_at TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_bill_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  bill_id INTEGER,
                  item_name TEXT,
                  quantity INTEGER,
                  price REAL,
                  status TEXT DEFAULT 'pending',
                  FOREIGN KEY(bill_id) REFERENCES restaurant_bills(id))''')
    
    # Ensure status column in restaurant_bill_items
    c.execute("PRAGMA table_info(restaurant_bill_items)")
    item_cols = [col[1] for col in c.fetchall()]
    if 'status' not in item_cols:
        c.execute("ALTER TABLE restaurant_bill_items ADD COLUMN status TEXT DEFAULT 'pending'")

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  item_name TEXT,
                  category TEXT,
                  stock_quantity REAL DEFAULT 0,
                  unit TEXT DEFAULT 'pcs',
                  alert_level REAL DEFAULT 5,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    # SaaS & System Tables
    c.execute('''CREATE TABLE IF NOT EXISTS super_transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  amount REAL,
                  utr_ref TEXT,
                  plan TEXT,
                  date TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS announcements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  message TEXT,
                  type TEXT DEFAULT 'info',
                  is_active INTEGER DEFAULT 1,
                  created_at TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  user_id INTEGER,
                  action TEXT,
                  details TEXT,
                  timestamp TEXT,
                  ip_address TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS support_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  subject TEXT,
                  message TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS booking_rooms
                 (booking_id INTEGER,
                  room_id TEXT,
                  FOREIGN KEY(booking_id) REFERENCES bookings(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS guest_feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER NOT NULL,
                  rating INTEGER NOT NULL,
                  message TEXT,
                  date TEXT NOT NULL,
                  FOREIGN KEY (hotel_id) REFERENCES hotels (id))''')

    conn.commit()
    conn.close()
    print("VPS Database is now fully synchronized with Phase 17! ")

if __name__ == '__main__':
    sync_database()
