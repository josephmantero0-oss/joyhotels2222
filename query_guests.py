import sqlite3
import json

conn = sqlite3.connect('hotel.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT id, name FROM hotels WHERE name LIKE '%najuka%' COLLATE NOCASE")
hotels = c.fetchall()

res = {}
for h in hotels:
    hotel_id = h['id']
    hotel_name = h['name']
    
    # Query guests table
    c.execute("SELECT * FROM guests WHERE hotel_id = ?", (hotel_id,))
    guests = [dict(row) for row in c.fetchall()]
    
    # Query bookings table as well just in case guest history is there
    c.execute("SELECT * FROM bookings WHERE hotel_id = ?", (hotel_id,))
    bookings = [dict(row) for row in c.fetchall()]
    
    res[hotel_name] = {
        'guests': guests,
        'bookings': bookings
    }

print(json.dumps(res, indent=2))
