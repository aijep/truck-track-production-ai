from fastmcp import FastMCP
import sqlite3
from whatsapp_meta import send_meta_whatsapp_link

mcp = FastMCP("Logistics-Truck-Tracker")
DB_NAME = "logistics.db"
SERVER_BASE_URL = "http://YOUR_SERVER_IP_OR_DOMAIN:8000"

@mcp.tool()
def add_driver(name: str, phone: str) -> str:
    """Add a new driver to the system."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO drivers (name, phone) VALUES (?, ?)", (name, phone))
        conn.commit()
        return f"Driver '{name}' ({phone}) added successfully."

@mcp.tool()
def add_truck(plate_number: str, model: str) -> str:
    """Add a new truck to the system fleet."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trucks (plate_number, model) VALUES (?, ?)", (plate_number, model))
        conn.commit()
        return f"Truck '{plate_number}' ({model}) added to fleet."

@mcp.tool()
def create_allotment_and_notify_whatsapp(driver_id: int, truck_id: int, source: str, destination: str) -> str:
    """
    Create trip consignment, update statuses, and dispatch WhatsApp tracking link via Meta API.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, phone FROM drivers WHERE id = ?", (driver_id,))
        driver = cursor.fetchone()
        if not driver:
            return f"Error: Driver with ID {driver_id} not found."
        
        driver_name, driver_phone = driver
        
        cursor.execute(
            "INSERT INTO consignments (driver_id, truck_id, source, destination, status) VALUES (?, ?, ?, ?, 'IN_TRANSIT')",
            (driver_id, truck_id, source, destination)
        )
        consignment_id = cursor.lastrowid
        
        cursor.execute("UPDATE drivers SET status = 'BUSY' WHERE id = ?", (driver_id,))
        cursor.execute("UPDATE trucks SET status = 'BUSY' WHERE id = ?", (truck_id,))
        conn.commit()
    
    tracking_link = f"{SERVER_BASE_URL}/track/{consignment_id}"
    
    try:
        api_response = send_meta_whatsapp_link(
            recipient_phone=driver_phone,
            driver_name=driver_name,
            consignment_id=consignment_id,
            source=source,
            destination=destination,
            tracking_url=tracking_link
        )
        meta_id = api_response.get("messages", [{}])[0].get("id", "N/A")
        return f"Consignment #{consignment_id} assigned. Meta WhatsApp sent to {driver_phone} (ID: {meta_id})."
    
    except Exception as e:
        return f"Consignment #{consignment_id} created, but WhatsApp dispatch failed: {str(e)}"

@mcp.tool()
def terminate_journey(consignment_id: int) -> str:
    """Terminate journey, complete trip, and set driver & truck to AVAILABLE."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT driver_id, truck_id FROM consignments WHERE id = ?", (consignment_id,))
        row = cursor.fetchone()
        
        if not row:
            return f"Error: Consignment #{consignment_id} not found."
        
        driver_id, truck_id = row
        
        cursor.execute("UPDATE consignments SET status = 'COMPLETED' WHERE id = ?", (consignment_id,))
        cursor.execute("UPDATE drivers SET status = 'AVAILABLE' WHERE id = ?", (driver_id,))
        cursor.execute("UPDATE trucks SET status = 'AVAILABLE' WHERE id = ?", (truck_id,))
        conn.commit()
        
    return f"Journey #{consignment_id} terminated. Driver #{driver_id} and Truck #{truck_id} are now available."

if __name__ == "__main__":
    mcp.run()