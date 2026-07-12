from app import app, init_db
import sqlite3
import os

# Setup test env
app.config['TESTING'] = True
app.config['UPLOAD_FOLDER'] = 'static/uploads_debug'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
client = app.test_client()

with app.app_context():
    init_db()
    
    # Login
    client.post('/login', json={'username': 'najuka', 'password': 'najuka123'})

    # Clean rooms first
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    c.execute("UPDATE rooms SET status='available'")
    c.execute("DELETE FROM bookings")
    c.execute("DELETE FROM booking_rooms")
    conn.commit()
    conn.close()

    # Create Group Booking (103 as initial, 104 as additional)
    # The user says "initial room checkout page is not opening"
    data = {
        'room_ids': '103,104',
        'guest_name': 'Debug Group',
        'phone': '1112223333',
        'address': 'Debug Addr',
        'id_number': 'DBG1',
        'amount': 2000
    }
    resp = client.post('/api/book', data=data)
    print(f"Booking Response: {resp.json}")

    # Fetch Rooms and check 103's booking_id
    resp = client.get('/api/rooms')
    rooms = resp.json
    
    room_103 = next((r for r in rooms if r['room_id'] == '103'), None)
    room_104 = next((r for r in rooms if r['room_id'] == '104'), None)
    
    print("\n--- ROOM 103 (Initial) ---")
    print(room_103)
    
    print("\n--- ROOM 104 (Additional) ---")
    print(room_104)

    if room_103 and not room_103.get('booking_id'):
        print("\n[FAIL] Room 103 is missing booking_id!")
    else:
        print("\n[PASS] Room 103 has booking_id.")
