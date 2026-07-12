with open('app.py', 'r', encoding='utf-8') as f:
    app_content = f.read()

users_table_code = """
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password_hash TEXT,
                  role TEXT DEFAULT 'owner',
                  hotel_id INTEGER,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
"""

fixed_users_table_code = """
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password_hash TEXT,
                  role TEXT DEFAULT 'owner',
                  hotel_id INTEGER,
                  is_2fa_enabled INTEGER DEFAULT 0,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
                  
    # Migration: Add is_2fa_enabled to users if not exists
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass
"""

app_content = app_content.replace(users_table_code, fixed_users_table_code)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_content)

print("Fixed users table in app.py")
