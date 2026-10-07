import json
import sqlite3

def test_public_announcement(client, init_test_data):
    """Test public announcement endpoint returns successfully."""
    response = client.get('/api/public/announcement')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'has_announcement' in data

def test_protected_route_without_login(client):
    """Test accessing protected route without login redirects or returns 4xx."""
    response = client.get('/dashboard')
    # Since login_required redirects to login
    assert response.status_code == 302
    assert '/login' in response.headers.get('Location', '')

def test_super_admin_route_without_login(client):
    """Test super admin route protection."""
    response = client.get('/super_admin')
    assert response.status_code in [403, 302]


def test_guest_profile_includes_member_names(client, init_test_data):
    """Guest profile API must include additional member names from the booking JSON."""
    with client.application.app_context():
        conn = sqlite3.connect(client.application.config['DATABASE'])
        c = conn.cursor()
        c.execute(
            "INSERT INTO bookings (hotel_id, room_id, guest_name, phone, address, id_number, id_photo, members, amount, checkin_time, checkout_time, extra_charges, food, laundry, water_bottle, car_wash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '2026-08-30 12:00:00', '', 0, 0, 0, 0, 0, 'active')",
            (
                init_test_data['hotel_id'],
                '101',
                'Jane Doe',
                '9998887777',
                'Test address',
                'ID-123',
                'img.jpg',
                json.dumps(['Alice', {'name': 'Bob'}]),
            ),
        )
        conn.commit()
        conn.close()

    login_response = client.post('/login', data={
        'username': init_test_data['username'],
        'password': init_test_data['password']
    }, follow_redirects=False)
    assert login_response.status_code in (200, 302)

    response = client.get('/api/guest/1')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'members' in data
    assert 'Alice' in data['members']
    assert 'Bob' in data['members']
