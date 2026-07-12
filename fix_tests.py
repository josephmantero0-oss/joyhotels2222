import re

# 1. Update conftest.py
conftest_content = """import pytest
import os
import sys
import sqlite3
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app as flask_app, init_db

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    flask_app.config.update({
        "TESTING": True,
        "DATABASE": db_path,
        "SECRET_KEY": "test_secret_key"
    })

    with flask_app.app_context():
        init_db()

    yield flask_app

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except Exception:
        pass

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def init_test_data(app):
    with app.app_context():
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        
        c.execute("INSERT INTO hotels (name, email, phone, plan, is_active, housekeeping_token, is_hotel_active) VALUES ('Test Hotel', 'test@example.com', '1234567890', 'monthly', 1, 'token123', 1)")
        hotel_id = c.lastrowid
        
        from werkzeug.security import generate_password_hash
        hashed_pw = generate_password_hash('password123')
        c.execute("INSERT INTO users (username, password_hash, role, hotel_id) VALUES ('testuser', ?, 'owner', ?)", (hashed_pw, hotel_id))
        
        c.execute("INSERT INTO rooms (room_id, hotel_id, status, room_type) VALUES ('101', ?, 'available', 'Standard')", (hotel_id,))
        
        conn.commit()
        conn.close()
        
        return {"hotel_id": hotel_id, "username": "testuser", "password": "password123"}
"""

with open('tests/conftest.py', 'w', encoding='utf-8') as f:
    f.write(conftest_content)

# 2. Add announcements table to init_db in app.py
with open('app.py', 'r', encoding='utf-8') as f:
    app_content = f.read()

announcement_table = '''
    c.execute("""CREATE TABLE IF NOT EXISTS announcements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  message TEXT,
                  type TEXT DEFAULT 'info',
                  is_active INTEGER DEFAULT 1,
                  created_at TEXT)""")
    conn.commit()
    conn.close()
'''

app_content = app_content.replace('conn.commit()\n    conn.close()', announcement_table, 1)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_content)

print("Fixed tests and app.py")
