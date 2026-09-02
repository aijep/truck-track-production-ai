import os
import sqlite3
from fastapi import APIRouter, Request, Response, Query, HTTPException

router = APIRouter()

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "YOUR_CUSTOM_VERIFY_TOKEN")
DB_NAME = "logistics.db"

@router.get("/webhook")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """
    Handles Meta's initial webhook handshake verification.
    """
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return Response(content=challenge, status_code=200)
    
    raise HTTPException(status_code=403, detail="Verification failed: Invalid token or mode")

@router.post("/webhook")
async def receive_meta_webhook(request: Request):
    """
    Receives push notifications for message statuses (sent, delivered, read) 
    and inbound driver responses.
    """
    payload = await request.json()
    
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                
                # Delivery/Read receipts
                statuses = value.get("statuses", [])
                for status_event in statuses:
                    wamid = status_event.get("id")
                    status = status_event.get("status")
                    update_message_status(wamid, status)
                    print(f"[Meta Status Log] Message {wamid} updated to status: {status}")

                # Incoming messages from driver
                messages = value.get("messages", [])
                for msg in messages:
                    sender = msg.get("from")
                    msg_body = msg.get("text", {}).get("body", "")
                    print(f"[Driver Reply Log] Reply from {sender}: {msg_body}")

    except Exception as e:
        print(f"Error parsing Meta webhook payload: {str(e)}")
        
    return Response(content="EVENT_RECEIVED", status_code=200)

def update_message_status(wamid: str, status: str):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "UPDATE whatsapp_logs SET status = ? WHERE wamid = ?",
            (status, wamid)
        )