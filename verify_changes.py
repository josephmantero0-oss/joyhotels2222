from app import app, init_db
import unittest
import json
import sqlite3
import os

class HotelTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = 'static/uploads_test'
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        self.app = app.test_client()
        with app.app_context():
            init_db()

    def login(self, username, password):
        return self.app.post('/login', json={'username': username, 'password': password})

    def test_rbac(self):
        # Login as Staff
        resp = self.login('staff', 'staff123')
        self.assertEqual(resp.json['success'], True)
        self.assertEqual(resp.json['role'], 'staff')
        
        # Access Financials (Should fail)
        resp = self.app.get('/api/financials')
        self.assertEqual(resp.status_code, 403)
        
        # Login as Admin
        resp = self.login('najuka', 'najuka123')
        self.assertEqual(resp.json['success'], True)
        self.assertEqual(resp.json['role'], 'admin')
        
        # Access Financials (Should succeed)
        resp = self.app.get('/api/financials')
        self.assertEqual(resp.status_code, 200)

    def test_group_booking_and_guest_history(self):
        self.login('najuka', 'najuka123')
        
        # Book Rooms 101 and 102
        data = {
            'room_ids': '101,102',
            'guest_name': 'Test Group',
            'phone': '9998887777',
            'address': 'Test Addr',
            'id_number': 'ID123',
            'amount': 5000
        }
        resp = self.app.post('/api/book', data=data)
        self.assertEqual(resp.json['success'], True)
        
        # Verify DB
        conn = sqlite3.connect('hotel.db')
        c = conn.cursor()
        
        # Check Guests
        c.execute("SELECT name FROM guests WHERE phone='9998887777'")
        guest = c.fetchone()
        self.assertIsNotNone(guest)
        self.assertEqual(guest[0], 'Test Group')
        
        # Check Booking Rooms
        c.execute("SELECT id FROM bookings WHERE phone='9998887777'")
        booking_id = c.fetchone()[0]
        
        c.execute("SELECT count(*) FROM booking_rooms WHERE booking_id=?", (booking_id,))
        count = c.fetchone()[0]
        self.assertEqual(count, 2)
        
        # Check Room Status
        c.execute("SELECT status FROM rooms WHERE room_id IN ('101', '102')")
        statuses = [r[0] for r in c.fetchall()]
        self.assertTrue(all(s == 'occupied' for s in statuses))
        
        conn.close()
        
        # Test Checkout
        resp = self.app.post('/api/checkout', json={'booking_id': booking_id})
        self.assertEqual(resp.json['success'], True)
        
        # Verify Rooms Dirty
        conn = sqlite3.connect('hotel.db')
        c = conn.cursor()
        c.execute("SELECT status FROM rooms WHERE room_id IN ('101', '102')")
        statuses = [r[0] for r in c.fetchall()]
        self.assertTrue(all(s == 'dirty' for s in statuses))
        conn.close()

if __name__ == '__main__':
    unittest.main()
