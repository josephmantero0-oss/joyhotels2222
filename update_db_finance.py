import sqlite3

def update_schema():
    conn = sqlite3.connect('hotel.db')
    c = conn.cursor()
    
    try:
        print("Checking hotels table finance columns...")
        # Check if column exists
        c.execute("PRAGMA table_info(hotels)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'currency_symbol' not in columns:
            print("Adding currency_symbol column...")
            c.execute("ALTER TABLE hotels ADD COLUMN currency_symbol TEXT DEFAULT '₹'")
        
        if 'tax_rate' not in columns:
            print("Adding tax_rate column...")
            c.execute("ALTER TABLE hotels ADD COLUMN tax_rate REAL DEFAULT 0.0")

        conn.commit()
        print("Schema update successful! 💰")
        
    except Exception as e:
        print(f"Error updating schema: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_schema()
