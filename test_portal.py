import sqlite3
conn = sqlite3.connect('hotel.db')
c = conn.cursor()

# Check if table exists
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='self_checkin_requests'")
table = c.fetchone()
print('Table exists:', bool(table))

# Get hotel token
c.execute('SELECT id, name, housekeeping_token FROM hotels LIMIT 1')
hotel = c.fetchone()
if hotel:
    print(f'Hotel: id={hotel[0]}, name={hotel[1]}, token={hotel[2]}')
else:
    print('No hotels found')

# Test guest checkin page URL
if hotel and hotel[2]:
    print(f'Guest form URL: http://localhost:5000/guest-checkin/{hotel[2]}')

conn.close()
