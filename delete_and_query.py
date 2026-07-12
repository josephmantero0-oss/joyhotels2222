import sqlite3
import os
import shutil

db_path = r'c:\Users\JOY\OneDrive\Desktop\joyhotels\hotel.db'
backup_path = r'c:\Users\JOY\OneDrive\Desktop\joyhotels\hotel.db.backup_delete'

# Take a quick backup
shutil.copy2(db_path, backup_path)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get the hotel IDs for 'hotel najuka'
c.execute("SELECT id, name FROM hotels WHERE name LIKE 'hotel najuka' COLLATE NOCASE")
hotels = c.fetchall()
hotel_ids = [h['id'] for h in hotels]

if hotel_ids:
    placeholders = ','.join('?' for _ in hotel_ids)
    
    # Delete from guests
    delete_guests_query = f"""
        DELETE FROM guests 
        WHERE hotel_id IN ({placeholders}) 
        AND (
            name COLLATE NOCASE = 'joseph' OR 
            name COLLATE NOCASE = 'joseph mantero' OR 
            name COLLATE NOCASE = 'yash tambe/tejas shetty' OR
            name COLLATE NOCASE = 'yash tambe tejas shetty'
        )
    """
    c.execute(delete_guests_query, hotel_ids)
    
    # Delete from bookings
    delete_bookings_query = f"""
        DELETE FROM bookings 
        WHERE hotel_id IN ({placeholders}) 
        AND (
            guest_name COLLATE NOCASE = 'joseph' OR 
            guest_name COLLATE NOCASE = 'joseph mantero' OR 
            guest_name COLLATE NOCASE = 'yash tambe/tejas shetty' OR
            guest_name COLLATE NOCASE = 'yash tambe tejas shetty'
        )
    """
    c.execute(delete_bookings_query, hotel_ids)
    
    conn.commit()

# Now re-generate the list
artifact_path = r'C:\Users\JOY\.gemini\antigravity-ide\brain\f3057277-8b17-4391-9686-d1569660f9fe\updated_guest_history.md'

with open(artifact_path, 'w', encoding='utf-8') as f:
    f.write("# Updated Guest History for 'Hotel Najuka'\n\n")
    if not hotels:
        f.write("No hotel found with the name 'Hotel Najuka'.\n")
    else:
        for h in hotels:
            hotel_id = h['id']
            hotel_name = h['name']
            
            f.write(f"## {hotel_name} (ID: {hotel_id})\n\n")
            
            c.execute("SELECT name, phone, email, address, status, id_number FROM guests WHERE hotel_id = ?", (hotel_id,))
            guests = c.fetchall()
            
            f.write("### Registered Guests\n")
            if not guests:
                f.write("No guests found.\n\n")
            else:
                f.write("| Name | Phone | Email | Address | Status | ID Number |\n")
                f.write("|------|-------|-------|---------|--------|-----------|\n")
                for g in guests:
                    email = g['email'] or 'N/A'
                    address = g['address'] or 'N/A'
                    f.write(f"| {g['name']} | {g['phone']} | {email} | {address} | {g['status']} | {g['id_number']} |\n")
                f.write("\n")
                
            c.execute("SELECT guest_name, phone, room_id, checkin_time, checkout_time, status, amount FROM bookings WHERE hotel_id = ? ORDER BY checkin_time DESC", (hotel_id,))
            bookings = c.fetchall()
            
            f.write("### Booking History\n")
            if not bookings:
                f.write("No bookings found.\n\n")
            else:
                f.write("| Guest Name | Phone | Room | Check-in | Check-out | Status | Amount |\n")
                f.write("|------------|-------|------|----------|-----------|--------|--------|\n")
                for b in bookings:
                    cout = b['checkout_time'] or 'N/A'
                    f.write(f"| {b['guest_name']} | {b['phone']} | {b['room_id']} | {b['checkin_time']} | {cout} | {b['status']} | {b['amount']} |\n")
                f.write("\n")

print("Updated artifact written to:", artifact_path)
