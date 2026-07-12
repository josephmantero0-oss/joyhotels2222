import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add get_db_connection() function after app configuration
helper_code = """
# Secure stable secret key for sessions
"""
new_helper = """
# Secure stable secret key for sessions
def get_db_connection():
    db_path = app.config.get('DATABASE', 'hotel.db')
    return sqlite3.connect(db_path)
"""

content = content.replace(helper_code, new_helper)

# Replace sqlite3.connect('hotel.db') with get_db_connection()
content = re.sub(r"sqlite3\.connect\(['\"]hotel\.db['\"]\)", "get_db_connection()", content)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Refactored app.py")
