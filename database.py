import sqlite3

DB_NAME = "logistics.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Drivers Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'AVAILABLE'
        )
        """)
        
        # Trucks Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trucks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE NOT NULL,
            model TEXT NOT NULL,
            status TEXT DEFAULT 'AVAILABLE'
        )
        """)
        
        # Consignments / Allotments Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS consignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER REFERENCES drivers(id),
            truck_id INTEGER REFERENCES trucks(id),
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT DEFAULT 'IN_TRANSIT',
            current_lat REAL,
            current_lng REAL
        )
        """)

        # WhatsApp Message Audit Logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consignment_id INTEGER REFERENCES consignments(id),
            wamid TEXT UNIQUE NOT NULL,
            recipient_phone TEXT NOT NULL,
            status TEXT DEFAULT 'sent',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database and schemas initialized successfully.")