import sqlite3
import os

def check_db():
    db_path = 'hotel.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found in {os.getcwd()}")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    print("\n" + "="*50)
    print("--- JOYHOTELS DEEP DATABASE INSPECTION ---")
    print("="*50)

    # 1. Check 'hotel_id' column in rooms table
    print("\n[1] Rooms Table Schema Check:")
    c.execute("PRAGMA table_info(rooms)")
    columns = c.fetchall()
    has_hotel_id = False
    for col in columns:
        if col[1] == 'hotel_id':
            has_hotel_id = True
            break

    if not has_hotel_id:
        print("CRITICAL: 'hotel_id' column is MISSING from rooms table!")
        print("FIX: You MUST run: python3 migrate_db.py")
    else:
        print("SUCCESS: 'hotel_id' column is present.")

    # 2. Check Hotels
    c.execute("SELECT id, name FROM hotels")
    hotels = c.fetchall()
    print(f"\n[2] Hotels Found ({len(hotels)}):")
    for h in hotels:
        print(f" - ID: {h[0]}, Name: {h[1]}")

    # 3. Check Users & their Hotel IDs
    c.execute("SELECT username, role, hotel_id FROM users")
    users = c.fetchall()
    print(f"\n[3] Users Found ({len(users)}):")
    for u in users:
        print(f" - User: {u[0]}, Role: {u[1]}, Hotel_ID: {u[2]}")

    # 4. Check Root Cause: Orphaned Rooms
    c.execute("SELECT count(*) FROM rooms WHERE hotel_id IS NULL OR hotel_id = 0")
    orphans = c.fetchone()[0]
    print(f"\n[4] Data Check:")
    print(f" - Total rooms: {len(conn.execute('SELECT * FROM rooms').fetchall())}")
    print(f" - Rooms with NO Hotel ID: {orphans}")

    if orphans > 0:
        print("WARNING: You have rooms that don't belong to any hotel.")
        print("FIX: Run migrate_db.py to assign them to Hotel #1.")

    conn.close()
    print("\n" + "="*50)
    print("INSPECTION COMPLETE")
    print("="*50 + "\n")

if __name__ == "__main__":
    check_db()
