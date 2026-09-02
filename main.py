import json
import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

import database

app = FastAPI(title="Logistics Truck Tracking API")

# Enable CORS for external client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    database.init_db()


# -----------------------------------------------------------------------------
# Request models for the sidebar management menu
# -----------------------------------------------------------------------------
class DriverIn(BaseModel):
    name: str
    phone: str


class TruckIn(BaseModel):
    plate_number: str
    model: str


class AllotmentIn(BaseModel):
    driver_id: int
    truck_id: int
    source: str
    destination: str
    source_lat: Optional[float] = None
    source_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    start_time: Optional[str] = None      # "HH:MM:SS DD/MM/YYYY"
    reached_time: Optional[str] = None    # "HH:MM:SS DD/MM/YYYY"

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
# Driver / Truck / Allotment Management (Sidebar Menu)
# -----------------------------------------------------------------------------
@app.post("/api/drivers")
async def add_driver(payload: DriverIn):
    try:
        driver_id = database.create_driver(payload.name, payload.phone)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not create driver: {e}")
    return {"status": "driver_created", "id": driver_id}


@app.get("/api/drivers")
async def get_drivers():
    return database.list_drivers()


@app.post("/api/trucks")
async def add_truck(payload: TruckIn):
    try:
        truck_id = database.create_truck(payload.plate_number, payload.model)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not create truck: {e}")
    return {"status": "truck_created", "id": truck_id}


@app.get("/api/trucks")
async def get_trucks():
    return database.list_trucks()


@app.post("/api/allotments")
async def add_allotment(payload: AllotmentIn):
    allotment_id = database.create_allotment(
        payload.driver_id, payload.truck_id, payload.source, payload.destination,
        payload.source_lat, payload.source_lng, payload.dest_lat, payload.dest_lng,
        payload.start_time, payload.reached_time,
    )

    # Notify connected dashboards so the route can be drawn live
    await manager.broadcast({
        "type": "allotment_created",
        "id": allotment_id,
        "source": payload.source,
        "destination": payload.destination,
        "source_lat": payload.source_lat,
        "source_lng": payload.source_lng,
        "dest_lat": payload.dest_lat,
        "dest_lng": payload.dest_lng,
        "start_time": payload.start_time,
        "reached_time": payload.reached_time,
    })

    return {"status": "allotment_created", "id": allotment_id}


@app.get("/api/allotments")
async def get_allotments():
    return database.list_allotments()


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