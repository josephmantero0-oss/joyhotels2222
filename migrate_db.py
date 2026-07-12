import sqlite3

def migrate():
    print("Starting Migration...")
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()

    # 1. Add hotel_id to ROOMS
    try:
        c.execute("ALTER TABLE rooms ADD COLUMN hotel_id INTEGER")
        print("Added hotel_id to rooms")
    except sqlite3.OperationalError:
        print("hotel_id already in rooms")

    # 2. Add hotel_id to BOOKINGS
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN hotel_id INTEGER")
        print("Added hotel_id to bookings")
    except sqlite3.OperationalError:
        print("hotel_id already in bookings")
        
    # 3. Add hotel_id to GUESTS
    try:
        c.execute("ALTER TABLE guests ADD COLUMN hotel_id INTEGER")
        print("Added hotel_id to guests")
    except sqlite3.OperationalError:
        print("hotel_id already in guests")

    # 4. Add hotel_id to EXPENSES
    try:
        c.execute("ALTER TABLE expenses ADD COLUMN hotel_id INTEGER")
        print("Added hotel_id to expenses")
    except sqlite3.OperationalError:
        print("hotel_id already in expenses")

    conn.commit()
    
    # 5. Fix Primary Key on ROOMS (needs recreation)
    # Check if we need to fix it
    c.execute("PRAGMA table_info(rooms)")
    cols = c.fetchall()
    # Check if PK covers both room_id and hotel_id?
    # SQLite logic is complex to detect PK, simpler to just Re-Create if we are sure.
    # We will recreate to be safe.
    
    print("Recreating ROOMS table for Composite PK...")
    c.execute("ALTER TABLE rooms RENAME TO rooms_old")
    c.execute('''CREATE TABLE rooms
                 (room_id TEXT,
                  hotel_id INTEGER,
                  status TEXT DEFAULT 'available',
                  last_checkout TEXT,
                  room_type TEXT,
                  PRIMARY KEY (room_id, hotel_id),
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
                  
    # Copy data back
    # Default legacy rows to hotel_id = 1 (assuming first hotel is the owner)
    c.execute("INSERT INTO rooms (room_id, hotel_id, status, last_checkout, room_type) SELECT room_id, COALESCE(hotel_id, 1), status, last_checkout, room_type FROM rooms_old")
    c.execute("DROP TABLE rooms_old")
    
    conn.commit()
    print("Migration Complete.")
    conn.close()

if __name__ == '__main__':
    migrate()
