# db.py
from dotenv import load_dotenv
import os
import boto3
import datetime
from uuid import uuid4
from decimal import Decimal

load_dotenv()

# ----------------------------
# AWS Setup
# ----------------------------
dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION", "us-west-2"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

rides_table = dynamodb.Table(os.getenv("DYNAMO_RIDES_TABLE", "Rides"))
drivers_table = dynamodb.Table(os.getenv("DYNAMO_DRIVERS_TABLE", "Drivers"))

location_client = boto3.client(
    "location",
    region_name=os.getenv("AWS_REGION", "us-west-2"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

PLACE_INDEX = os.getenv("PLACE_INDEX_NAME", "CampusPlaceIndex")
ROUTE_CALCULATOR = os.getenv("ROUTE_CALCULATOR_NAME", "CampusRouteCalculator")

# ----------------------------
# Geocoding / Reverse Geocoding
# ----------------------------
def geocode_address(address_text):
    try:
        response = location_client.search_place_index_for_text(
            IndexName=PLACE_INDEX,
            Text=f"{address_text.strip()}, Seattle, WA",
            MaxResults=1
        )
        if response["Results"]:
            place = response["Results"][0]["Place"]
            lat, lon = place["Geometry"]["Point"][1], place["Geometry"]["Point"][0]
            label = place["Label"]
            return {"lat": lat, "lon": lon, "address": label}
    except Exception as e:
        print("Geocoding error:", e)
    return None

def reverse_geocode(lat, lon):
    try:
        response = location_client.search_place_index_for_position(
            IndexName=PLACE_INDEX,
            Position=[lon, lat]
        )
        if response["Results"]:
            return response["Results"][0]["Place"]["Label"]
    except Exception as e:
        print("Reverse geocoding error:", e)
    return None

# ----------------------------
# Ride Functions
# ----------------------------
def create_ride(name, uw_id, pickup, destination, notes=""):
    ride_id = uw_id  # Use UW NetID as ride_id
    ride_item = {
        "ride_id": ride_id,
        "name": name,
        "pickup": {
            "lat": Decimal(str(pickup["lat"])),
            "lon": Decimal(str(pickup["lon"])),
            "address": pickup["address"]
        },
        "destination": {
            "lat": Decimal(str(destination["lat"])),
            "lon": Decimal(str(destination["lon"])),
            "address": destination["address"]
        },
        "status": "waiting",
        "notes": notes,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    rides_table.put_item(Item=ride_item)
    return ride_item

def get_all_rides():
    response = rides_table.scan()
    return response.get("Items", [])

def update_ride_status(ride_id, status, driver_id=None):
    update_expr = "SET #s = :status"
    expr_names = {"#s": "status"}
    expr_values = {":status": status}
    if driver_id:
        update_expr += ", driver_id = :d"
        expr_values[":d"] = driver_id
    rides_table.update_item(
        Key={"ride_id": ride_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values
    )

def calculate_route_minutes_seconds(pickup, destination):
    try:
        print("Calculating route...")
        print("Pickup:", pickup)
        print("Destination:", destination)

        response = location_client.calculate_route(
            CalculatorName=ROUTE_CALCULATOR,
            DeparturePosition=[float(pickup["lon"]), float(pickup["lat"])],
            DestinationPosition=[float(destination["lon"]), float(destination["lat"])],
            TravelMode="Car",
            DistanceUnit="Kilometers",
            IncludeLegGeometry=False
        )
        print("🛰️ Full route response:", response)

        # Check for 'Legs' in response
        if "Legs" in response and response["Legs"]:
            leg = response["Legs"][0]
            eta_seconds = int(leg["DurationSeconds"])
            minutes = eta_seconds // 60
            seconds = eta_seconds % 60
            print(f"ETA: {minutes} min {seconds} sec")
            return minutes, seconds
        elif "Summary" in response:
            eta_seconds = int(response["Summary"]["DurationSeconds"])
            minutes = eta_seconds // 60
            seconds = eta_seconds % 60
            print(f"ETA: {minutes} min {seconds} sec")
            return minutes, seconds
        else:
            print("No route found in response structure.")
    except Exception as e:
        print("Route calculation error:", e)
        print("Using fallback estimate: 5 minutes")
        return 5, 0

    return 5, 0  # Fallback if route calculation fails

# ----------------------------
# Driver Functions
# ----------------------------
def update_driver_location(driver_id, lat, lon, available=True, current_ride_id=None):
    drivers_table.update_item(
        Key={"driver_id": driver_id},
        UpdateExpression="SET lat = :lat, lon = :lon, available = :avail, current_ride_id = :ride, last_updated = :ts",
        ExpressionAttributeValues={
            ":lat": Decimal(str(lat)),
            ":lon": Decimal(str(lon)),
            ":avail": available,
            ":ride": current_ride_id,
            ":ts": datetime.datetime.utcnow().isoformat()
        }
    )

def get_all_drivers():
    response = drivers_table.scan()
    return response.get("Items", [])

# ----------------------------
# Ride Assignment
# ----------------------------
def assign_next_ride():
    rides = [r for r in get_all_rides() if r["status"] == "waiting"]
    drivers = [d for d in get_all_drivers() if d.get("available", True)]
    
    for ride in rides:
        if drivers:
            driver = drivers.pop(0)
            update_ride_status(ride["ride_id"], "in_car", driver["driver_id"])
            update_driver_location(driver["driver_id"], driver["lat"], driver["lon"], available=False, current_ride_id=ride["ride_id"])

def get_ride_by_id(ride_id):
    """Fetch a specific ride from DynamoDB"""
    try:
        response = rides_table.get_item(Key={"ride_id": ride_id})
        return response.get("Item")
    except Exception as e:
        print(f"Error fetching ride {ride_id}: {e}")
        return None

def get_driver_by_id(driver_id):
    """Fetch a specific driver from DynamoDB"""
    try:
        response = drivers_table.get_item(Key={"driver_id": driver_id})
        return response.get("Item")
    except Exception as e:
        print(f"Error fetching driver {driver_id}: {e}")
        return None