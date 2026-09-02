import os
import sqlite3
import httpx

META_ACCESS_TOKEN = os.getenv("META_WA_ACCESS_TOKEN", "YOUR_META_PERMANENT_TOKEN")
META_PHONE_NUMBER_ID = os.getenv("META_WA_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID")
API_VERSION = os.getenv("META_WA_VERSION", "v21.0")
DB_NAME = "logistics.db"

def send_meta_whatsapp_link(recipient_phone: str, driver_name: str, consignment_id: int, source: str, destination: str, tracking_url: str) -> dict:
    """
    Sends a WhatsApp message via Meta Cloud API containing the live GPS tracking link.
    """
    clean_phone = "".join(filter(str.isdigit, recipient_phone))
    endpoint = f"https://graph.facebook.com/{API_VERSION}/{META_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    message_body = (
        f"Hello {driver_name},\n\n"
        f"Trip #{consignment_id} from {source} to {destination} is ready.\n\n"
        f"Click link to start GPS navigation and live tracking:\n{tracking_url}"
    )

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": message_body
        }
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Log to Database
        wamid = data.get("messages", [{}])[0].get("id")
        if wamid:
            log_whatsapp_dispatch(consignment_id, wamid, clean_phone)
            
        return data

def log_whatsapp_dispatch(consignment_id: int, wamid: str, phone: str):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT INTO whatsapp_logs (consignment_id, wamid, recipient_phone, status) VALUES (?, ?, ?, 'sent')",
            (consignment_id, wamid, phone)
        )