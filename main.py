from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import sqlite3
import json
from database import init_db
from webhook_router import router as webhook_router

# Initialize SQLite database schema
init_db()

app = FastAPI(title="Truck Tracking Logistics API")

# Mount Meta Webhook Endpoints
app.include_router(webhook_router)

# In-memory mapping: consignment_id -> List of WebSockets
active_connections: dict[int, list[WebSocket]] = {}

def update_truck_location(consignment_id: int, lat: float, lng: float):
    with sqlite3.connect("logistics.db") as conn:
        conn.execute(
            "UPDATE consignments SET current_lat = ?, current_lng = ? WHERE id = ?",
            (lat, lng, consignment_id)
        )

# Mobile Web Interface accessed via WhatsApp link
@app.get("/track/{consignment_id}", response_class=HTMLResponse)
def get_driver_tracker(consignment_id: int):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Driver Navigation & GPS</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: sans-serif; text-align: center; padding: 20px;">
        <h2>Trip #{consignment_id} Active</h2>
        <p id="status">Connecting GPS...</p>
        <script>
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${{wsProtocol}}//${{window.location.host}}/ws/location/{consignment_id}`);
            
            navigator.geolocation.watchPosition(
                (pos) => {{
                    const payload = {{ lat: pos.coords.latitude, lng: pos.coords.longitude }};
                    ws.send(JSON.stringify(payload));
                    document.getElementById('status').innerText = `Transmitting Location: ${{payload.lat.toFixed(4)}}, ${{payload.lng.toFixed(4)}}`;
                }},
                (err) => {{ document.getElementById('status').innerText = "Location Error: " + err.message; }},
                {{ enableHighAccuracy: true }}
            );
        </script>
    </body>
    </html>
    """

# Real-time WebSocket Endpoint
@app.websocket("/ws/location/{consignment_id}")
async def websocket_location(websocket: WebSocket, consignment_id: int):
    await websocket.accept()
    if consignment_id not in active_connections:
        active_connections[consignment_id] = []
    active_connections[consignment_id].append(websocket)
    
    try:
        while True:
            data_str = await websocket.receive_text()
            data = json.loads(data_str)
            lat, lng = data["lat"], data["lng"]
            
            update_truck_location(consignment_id, lat, lng)
            
            # Broadcast to dashboard interfaces tracking this consignment
            for conn in active_connections.get(consignment_id, []):
                if conn != websocket:
                    await conn.send_json({"consignment_id": consignment_id, "lat": lat, "lng": lng})
    except WebSocketDisconnect:
        active_connections[consignment_id].remove(websocket)