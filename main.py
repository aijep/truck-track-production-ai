import json
import os
from typing import List
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="Logistics Truck Tracking API")

# Enable CORS for external client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment Variables
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "my_custom_secret_token_123")
META_WA_ACCESS_TOKEN = os.getenv("META_WA_ACCESS_TOKEN", "")
META_WA_PHONE_NUMBER_ID = os.getenv("META_WA_PHONE_NUMBER_ID", "")


# -----------------------------------------------------------------------------
# WebSocket Connection Manager
# -----------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


# -----------------------------------------------------------------------------
# Frontend Routes
# -----------------------------------------------------------------------------
@app.get("/")
async def get_dashboard():
    """Serves the Leaflet/OpenStreetMap admin dashboard."""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return HTMLResponse("<h2>index.html not found in root directory.</h2>", status_code=404)


# -----------------------------------------------------------------------------
# Meta WhatsApp Webhook Endpoints
# -----------------------------------------------------------------------------
@app.get("/webhook")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """Handles the Meta verification handshake."""
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return int(challenge) if challenge and challenge.isdigit() else challenge
    raise HTTPException(status_code=403, detail="Verification failed: Invalid token or mode")


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Receives WhatsApp message status receipts and incoming driver updates."""
    data = await request.json()
    
    # Broadcast status updates to connected WebSocket clients
    try:
        entries = data.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                statuses = value.get("statuses", [])
                for status in statuses:
                    msg_id = status.get("id")
                    recipient_id = status.get("recipient_id")
                    stat = status.get("status")
                    await manager.broadcast({
                        "type": "whatsapp_status",
                        "message_id": msg_id,
                        "recipient": recipient_id,
                        "status": stat
                    })
    except Exception as e:
        print(f"Error parsing webhook payload: {e}")

    return {"status": "success"}


# -----------------------------------------------------------------------------
# Telemetry & Location Telemetry Endpoints
# -----------------------------------------------------------------------------
@app.post("/api/location")
async def update_location(payload: dict):
    """Receives GPS location updates from driver mobile interface."""
    consignment_id = payload.get("consignment_id")
    lat = payload.get("lat")
    lng = payload.get("lng")
    driver_name = payload.get("driver_name", "Driver")

    if not consignment_id or lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Missing required tracking fields")

    location_data = {
        "type": "location_update",
        "consignment_id": consignment_id,
        "lat": float(lat),
        "lng": float(lng),
        "driver_name": driver_name
    }

    # Broadcast location to active dashboard WebSockets
    await manager.broadcast(location_data)
    return {"status": "location_updated", "data": location_data}


# -----------------------------------------------------------------------------
# Real-Time WebSocket Endpoint
# -----------------------------------------------------------------------------
@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open and receive optional ping messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)