import sqlite3

def check_data():
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    
    print("--- USERS ---")
    c.execute("SELECT id, username, role, hotel_id FROM users")
    for r in c.fetchall():
        print(r)
        
    print("\n--- HOTELS ---")
    c.execute("SELECT id, name FROM hotels")
    for r in c.fetchall():
        print(r)
        
    print("\n--- ROOMS ---")
    c.execute("SELECT room_id, hotel_id, status FROM rooms")
    rooms = c.fetchall()
    for r in rooms:
        print(r)
        
    if not rooms:
        print("(No rooms found)")

    conn.close()

if __name__ == '__main__':
    check_data()
