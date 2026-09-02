import sqlite3
from contextlib import contextmanager

DB_NAME = "logistics.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
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
            source_lat REAL,
            source_lng REAL,
            dest_lat REAL,
            dest_lng REAL,
            start_time TEXT,
            reached_time TEXT,
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


# -----------------------------------------------------------------------------
# Drivers
# -----------------------------------------------------------------------------
def create_driver(name: str, phone: str):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO drivers (name, phone) VALUES (?, ?)", (name, phone)
        )
        conn.commit()
        return cur.lastrowid


def list_drivers():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM drivers ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


# -----------------------------------------------------------------------------
# Trucks
# -----------------------------------------------------------------------------
def create_truck(plate_number: str, model: str):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO trucks (plate_number, model) VALUES (?, ?)",
            (plate_number, model),
        )
        conn.commit()
        return cur.lastrowid


def list_trucks():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM trucks ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


# -----------------------------------------------------------------------------
# Allotments / Consignments
# -----------------------------------------------------------------------------
def create_allotment(driver_id, truck_id, source, destination,
                      source_lat, source_lng, dest_lat, dest_lng,
                      start_time, reached_time):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO consignments
                (driver_id, truck_id, source, destination,
                 source_lat, source_lng, dest_lat, dest_lng,
                 start_time, reached_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (driver_id, truck_id, source, destination,
              source_lat, source_lng, dest_lat, dest_lng,
              start_time, reached_time))
        conn.commit()
        return cur.lastrowid


def list_allotments():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT c.*, d.name AS driver_name, d.phone AS driver_phone,
                   t.plate_number, t.model
            FROM consignments c
            LEFT JOIN drivers d ON c.driver_id = d.id
            LEFT JOIN trucks t ON c.truck_id = t.id
            ORDER BY c.id DESC
        """).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print("Database and schemas initialized successfully.")
