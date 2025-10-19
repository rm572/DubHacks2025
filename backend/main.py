
from fastapi import FastAPI, APIRouter, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Set
from db import (
    geocode_address,
    calculate_route_minutes_seconds,
    create_ride,
    get_all_rides,
    update_ride_status,
    get_all_drivers,
    update_driver_location,
    get_driver_by_id,
    get_ride_by_id
)
import asyncio
import json

app = FastAPI(title="Campus Escort Backend")
router = APIRouter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections per ride
active_connections: Dict[str, Set[WebSocket]] = {}

class RideRequest(BaseModel):
    name: str
    uw_id: str
    pickup_address: str
    destination_address: str
    notes: Optional[str] = ""

class LocationUpdate(BaseModel):
    driver_id: str
    lat: float
    lon: float
    current_ride_id: Optional[str] = None

@app.post("/request_ride")
def request_ride_endpoint(ride_req: RideRequest):
    pickup = geocode_address(ride_req.pickup_address)
    destination = geocode_address(ride_req.destination_address)
    if not pickup or not destination:
        return {"error": "Invalid pickup or destination address"}
    ride = create_ride(ride_req.name, ride_req.uw_id, pickup, destination, ride_req.notes)
    return ride

@app.get("/client_status/{ride_id}")
def client_status(ride_id: str):
    ride = get_ride_by_id(ride_id)
    if not ride:
        return {"error": "Ride not found"}

    # Get all waiting rides in queue order
    rides = [r for r in get_all_rides() if r["status"] == "waiting"]
    if ride["status"] == "waiting":
        position = next((i for i, r in enumerate(rides) if r["ride_id"] == ride_id), None)
        if position is None:
            return {"error": "Ride not in queue"}

        # Find a driver to base the ETA on
        # (Here we just pick the *first available driver* — you might want smarter assignment logic)
        drivers = get_all_drivers()
        available_drivers = [d for d in drivers if d.get("available", True)]
        if not available_drivers:
            return {"error": "No drivers available"}

        driver = available_drivers[0]  # For now, just take the first one
        current_latlon = {"lat": float(driver["lat"]), "lon": float(driver["lon"])}

        total_eta_seconds = 0
        current_point = current_latlon

        # Go through each ride ahead in the queue, accumulating:
        # driver → pickup → destination
        for r in rides[:position]:
            # Driver to this pickup
            m1, s1 = calculate_route_minutes_seconds(current_point, r["pickup"])
            if m1 is not None:
                total_eta_seconds += m1 * 60 + s1

            # Pickup to this destination
            m2, s2 = calculate_route_minutes_seconds(r["pickup"], r["destination"])
            if m2 is not None:
                total_eta_seconds += m2 * 60 + s2

            # Update the current point to this dropoff
            current_point = r["destination"]

        # Finally, add ETA from last dropoff to this ride’s pickup
        m3, s3 = calculate_route_minutes_seconds(current_point, ride["pickup"])
        if m3 is not None:
            total_eta_seconds += m3 * 60 + s3

        return {
            "queue_position": position + 1,
            "eta": f"{total_eta_seconds // 60} min {total_eta_seconds % 60} sec",
            "status": "waiting",
            "driver_location": current_latlon
        }

    elif ride["status"] == "in_car":
        driver_id = ride.get("driver_id")
        if not driver_id:
            return {"error": "No driver assigned"}
        
        driver = get_driver_by_id(driver_id)
        if not driver:
            return {"error": "Driver not found"}

        current_pos = {"lat": float(driver.get("lat", 0)), "lon": float(driver.get("lon", 0))}
        m, s = calculate_route_minutes_seconds(current_pos, ride["destination"])
        eta_seconds = (m * 60 + s) if m is not None else 0

        return {
            "queue_position": None,
            "eta": f"{eta_seconds // 60} min {eta_seconds % 60} sec",
            "status": "in_car",
            "driver_location": current_pos,
            "driver_id": driver_id
        }

    elif ride["status"] == "completed":
        return {
            "status": "completed",
            "eta": None,
            "queue_position": None,
            "driver_location": None
        }

    return {"error": "Ride status unknown"}


@app.websocket("/ws/ride/{ride_id}")
async def websocket_ride_updates(websocket: WebSocket, ride_id: str):
    await websocket.accept()
    
    if ride_id not in active_connections:
        active_connections[ride_id] = set()
    active_connections[ride_id].add(websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except Exception as e:
        active_connections[ride_id].discard(websocket)
        if not active_connections[ride_id]:
            del active_connections[ride_id]

@app.post("/update_driver_location")
async def update_driver_location_endpoint(location: LocationUpdate):
    """Driver sends real-time location updates"""
    update_driver_location(
        location.driver_id,
        location.lat,
        location.lon,
        current_ride_id=location.current_ride_id
    )
    
    # If driver has an active ride, notify the student
    if location.current_ride_id:
        ride = get_ride_by_id(location.current_ride_id)
        if ride and location.current_ride_id in active_connections:
            status_data = client_status(location.current_ride_id)
            
            # Send update to all connected clients for this ride
            for connection in active_connections[location.current_ride_id]:
                try:
                    await connection.send_json(status_data)
                except Exception as e:
                    print(f"Error sending update: {e}")
    
    return {"status": "location updated"}

@app.get("/driver_view/{driver_id}")
def driver_view(driver_id: str):
    driver = get_driver_by_id(driver_id)
    current_ride = None
    if driver and driver.get("current_ride_id"):
        current_ride = get_ride_by_id(driver["current_ride_id"])
    queue = [r for r in get_all_rides() if r["status"] == "waiting"]
    return {
        "current_ride": current_ride,
        "queue": queue
    }

@app.post("/complete_ride/{ride_id}")
def complete_ride(ride_id: str):
    ride = get_ride_by_id(ride_id)
    if ride and ride.get("driver_id"):
        driver = get_driver_by_id(ride["driver_id"])
        if driver:
            # Set driver as available again
            update_driver_location(
                ride["driver_id"],
                float(driver.get("lat", 0)),
                float(driver.get("lon", 0)),
                available=True,
                current_ride_id=None
            )
    
    update_ride_status(ride_id, "completed")
    return {"status": "ride completed"}

@app.post("/accept_ride/{driver_id}/{ride_id}")
def accept_ride(driver_id: str, ride_id: str):
    """Driver accepts a ride from the queue"""
    driver = get_driver_by_id(driver_id)
    if not driver:
        return {"error": "Driver not found"}
    
    ride = get_ride_by_id(ride_id)
    if not ride or ride["status"] != "waiting":
        return {"error": "Ride not available"}
    
    # Assign ride to driver
    update_ride_status(ride_id, "in_car", driver_id)
    update_driver_location(
        driver_id,
        float(driver.get("lat", 0)),
        float(driver.get("lon", 0)),
        available=False,
        current_ride_id=ride_id
    )
    
    return {"status": "ride accepted"}

app.include_router(router)
