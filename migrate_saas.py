import sqlite3

def migrate():
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    
    # Add SaaS/Tax fields to hotels if missing
    c.execute("PRAGMA table_info(hotels)")
    cols = [col_info[1] for col_info in c.fetchall()]

    # Existing columns from original list, now checked explicitly
    if 'email' not in cols:
        c.execute("ALTER TABLE hotels ADD COLUMN email TEXT")
        print("Added column email to hotels")
    if 'phone' not in cols:
        c.execute("ALTER TABLE hotels ADD COLUMN phone TEXT")
        print("Added column phone to hotels")
    if 'is_active' not in cols:
        c.execute("ALTER TABLE hotels ADD COLUMN is_active INTEGER DEFAULT 0")
        print("Added column is_active to hotels")
    if 'utr_ref' not in cols:
        c.execute("ALTER TABLE hotels ADD COLUMN utr_ref TEXT")
        print("Added column utr_ref to hotels")

    # New columns for hotels
    if 'tax_percentage' not in cols:
        c.execute("ALTER TABLE hotels ADD COLUMN tax_percentage REAL DEFAULT 0.0")
        print("Added column tax_percentage to hotels")
    if 'currency_symbol' not in cols:
        c.execute("ALTER TABLE hotels ADD COLUMN currency_symbol TEXT DEFAULT '₹'")
        print("Added column currency_symbol to hotels")
    
    # Add role to users if missing
    # First, ensure the 'users' table exists. This is a common pattern for migrations.
    # If the users table is created elsewhere, this check might be redundant or need adjustment.
    # Assuming 'users' table might not exist yet, or we need to ensure it has 'id' for foreign keys.
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')

    c.execute("PRAGMA table_info(users)")
    user_cols = [col_info[1] for col_info in c.fetchall()]
    if 'role' not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'manager'") # 'manager' or 'housekeeper'
        print("Added column role to users")

    # Create transactions table
    c.execute('''CREATE TABLE IF NOT EXISTS super_transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  amount REAL,
                  utr_ref TEXT,
                  plan TEXT,
                  date TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    # Create support messages table
    c.execute('''CREATE TABLE IF NOT EXISTS support_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  subject TEXT,
                  message TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == '__main__':
    migrate()
