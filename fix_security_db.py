import sqlite3

conn = sqlite3.connect('hotel.db')
c = conn.cursor()

# Check if audit_logs table exists
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
result = c.fetchone()
print("audit_logs table exists:", result is not None)

if result is None:
    print("Creating audit_logs table...")
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
    print("Table created successfully!")

# Check users table for 2FA and backup columns
c.execute("PRAGMA table_info(users)")
columns = [col[1] for col in c.fetchall()]
print("\nUsers table columns:", columns)

if 'is_2fa_enabled' not in columns:
    print("Adding is_2fa_enabled column...")
    c.execute("ALTER TABLE users ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0")
    conn.commit()

if 'last_backup_sent' not in columns:
    print("Adding last_backup_sent column...")
    c.execute("ALTER TABLE users ADD COLUMN last_backup_sent TEXT")
    conn.commit()

conn.close()
print("\nDatabase schema updated!")
