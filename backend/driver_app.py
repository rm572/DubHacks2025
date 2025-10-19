import streamlit as st
import requests
import time
import streamlit.components.v1 as components

API_URL = "http://10.18.189.186:5001"


def get_browser_location():
    """Get real-time GPS from mobile device"""
    
    geolocation_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                padding: 10px;
                margin: 0;
            }
            #status {
                padding: 12px;
                background: #e3f2fd;
                border-radius: 8px;
                margin: 10px 0;
                border-left: 4px solid #2196F3;
            }
            .success { background: #e8f5e9; border-left-color: #4CAF50; }
            .error { background: #ffebee; border-left-color: #f44336; }
            button {
                padding: 10px 20px;
                background: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
                margin-top: 10px;
            }
            button:active {
                background: #1976D2;
            }
            .coords {
                font-family: monospace;
                font-size: 14px;
                margin-top: 8px;
            }
        </style>
    </head>
    <body>
        <div id="status">Requesting location permission...</div>
        <button onclick="forceUpdate()">Update Location Now</button>
        
        <script>
        let watchId = null;
        let lastLat = null;
        let lastLon = null;
        
        function updateStreamlit(lat, lon, accuracy) {
            window.location.hash = `lat=${lat}&lon=${lon}&acc=${accuracy}`;
            
            window.parent.postMessage({
                type: 'geolocation',
                lat: lat,
                lon: lon,
                accuracy: accuracy
            }, '*');
            
            lastLat = lat;
            lastLon = lon;
        }
        
        function startTracking() {
            if (!navigator.geolocation) {
                document.getElementById('status').className = 'error';
                document.getElementById('status').innerHTML = 
                    'Geolocation not supported on this device';
                return;
            }
            
            const options = {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            };
            
            watchId = navigator.geolocation.watchPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    const accuracy = position.coords.accuracy;
                    
                    updateStreamlit(lat, lon, accuracy);
                    
                    document.getElementById('status').className = 'success';
                    document.getElementById('status').innerHTML = 
                        '✅ <strong>Live tracking active</strong>' +
                        '<div class="coords">Lat: ' + lat.toFixed(6) + '</div>' +
                        '<div class="coords">Lon: ' + lon.toFixed(6) + '</div>' +
                        '<div class="coords">Accuracy: ±' + accuracy.toFixed(0) + 'm</div>' +
                        '<div style="margin-top: 8px; font-size: 12px; color: #666;">' +
                        'Last update: ' + new Date().toLocaleTimeString() + '</div>';
                },
                function(error) {
                    let errorMsg = '';
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMsg = 'Location access denied. Please enable in browser settings.';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMsg = 'Location unavailable. Check GPS/internet connection.';
                            break;
                        case error.TIMEOUT:
                            errorMsg = 'Location request timed out. Retrying...';
                            break;
                    }
                    document.getElementById('status').className = 'error';
                    document.getElementById('status').innerHTML = errorMsg;
                },
                options
            );
        }
        
        function forceUpdate() {
            document.getElementById('status').innerHTML = 'Updating location...';
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    const accuracy = position.coords.accuracy;
                    
                    updateStreamlit(lat, lon, accuracy);
                    
                    document.getElementById('status').className = 'success';
                    document.getElementById('status').innerHTML = 
                        'Location updated manually!';
                },
                function(error) {
                    document.getElementById('status').className = 'error';
                    document.getElementById('status').innerHTML = 
                        'Failed to get location';
                },
                { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
            );
        }
        
        startTracking();
        
        setInterval(function() {
            if (lastLat !== null && lastLon !== null) {
                updateStreamlit(lastLat, lastLon, 0);
            }
        }, 2000);
        </script>
    </body>
    </html>
    """
    
    components.html(geolocation_html, height=200)
    
    # Default coordinates (UW Seattle campus)
    default_lat = 47.6553
    default_lon = -122.3035
    
    if 'driver_lat' not in st.session_state:
        st.session_state.driver_lat = default_lat
        st.session_state.driver_lon = default_lon
    
    st.caption("Current coordinates (auto-updating from GPS):")
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input(
            "Latitude", 
            value=st.session_state.driver_lat, 
            format="%.6f",
            key="lat_input"
        )
    with col2:
        lon = st.number_input(
            "Longitude", 
            value=st.session_state.driver_lon, 
            format="%.6f",
            key="lon_input"
        )
    
    st.session_state.driver_lat = lat
    st.session_state.driver_lon = lon
    
    return lat, lon

st.set_page_config(page_title="Driver Dashboard", layout="wide")
st.title("🚗 Driver Dashboard")

if "driver_id" not in st.session_state:
    st.session_state.driver_id = ""
    st.session_state.checked_in = False
    st.session_state.current_ride = None
    st.session_state.last_location_update = 0

# Sidebar for driver check-in
with st.sidebar:
    st.header("Driver Login")
    driver_id = st.text_input("Enter your Driver ID", key="driver_input")
    
    if st.button("Check In"):
        if driver_id:
            st.session_state.driver_id = driver_id
            st.session_state.checked_in = True
            st.success("✅ Checked in! Allow location access when prompted.")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Enter your Driver ID first")

if st.session_state.checked_in:
    driver_id = st.session_state.driver_id
    
    # Get current location from browser
    st.subheader("Your Location")
    lat, lon = get_browser_location()
    
    # Send location update to backend every 5 seconds
    current_time = time.time()
    if current_time - st.session_state.last_location_update > 5:
        try:
            # Get current ride ID if driver has one
            res_view = requests.get(f"{API_URL}/driver_view/{driver_id}")
            current_ride_id = None
            if res_view.ok:
                data = res_view.json()
                if data.get("current_ride"):
                    current_ride_id = data["current_ride"]["ride_id"]
            
            # Send location update
            res = requests.post(f"{API_URL}/update_driver_location", json={
                "driver_id": driver_id,
                "lat": lat,
                "lon": lon,
                "current_ride_id": current_ride_id
            })
            
            if res.ok:
                st.session_state.last_location_update = current_time
                
        except Exception as e:
            st.warning(f"Failed to update location: {e}")
    
    # Main dashboard
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Available Rides")
        if st.button("Refresh Queue"):
            st.rerun()
        
        res = requests.get(f"{API_URL}/driver_view/{driver_id}")
        if res.ok:
            data = res.json()
            
            # Current ride section
            if data["current_ride"]:
                st.success("Current Ride Assigned")
                ride = data["current_ride"]
                col_ride1, col_ride2 = st.columns(2)
                with col_ride1:
                    st.write(f"**Passenger:** {ride['name']}")
                    st.write(f"**From:** {ride['pickup']['address']}")
                with col_ride2:
                    st.write(f"**To:** {ride['destination']['address']}")
                    st.write(f"**Notes:** {ride.get('notes', 'N/A')}")
                
                st.info("📍 Your live location is being sent to the passenger automatically")
                
                if st.button("Complete Ride"):
                    res = requests.post(f"{API_URL}/complete_ride/{ride['ride_id']}")
                    if res.ok:
                        st.success("Ride completed!")
                        st.session_state.current_ride = None
                        time.sleep(1)
                        st.rerun()
            else:
                st.info("No active ride. Browse the queue below.")
            
            # Queue section
            st.subheader("⏳ Waiting Queue")
            if data["queue"]:
                for i, ride in enumerate(data["queue"], 1):
                    with st.container():
                        col_q1, col_q2, col_q3 = st.columns([3, 1, 1])
                        with col_q1:
                            st.write(f"**{i}. {ride['name']}**")
                            st.caption(f"{ride['pickup']['address']} → {ride['destination']['address']}")
                        with col_q2:
                            st.write(f"{ride.get('notes', '')}")
                        with col_q3:
                            if st.button("Accept", key=f"accept_{ride['ride_id']}"):
                                res = requests.post(
                                    f"{API_URL}/accept_ride/{driver_id}/{ride['ride_id']}"
                                )
                                if res.ok:
                                    st.success("Ride accepted!")
                                    time.sleep(1)
                                    st.rerun()
                        st.divider()
            else:
                st.write("No rides waiting")
    
    with col2:
        st.subheader("Stats")
        st.metric("Driver ID", driver_id)
        st.metric("Status", "On Duty")
        st.metric("Location Updates", "Live")
        
        if st.button("Check Out"):
            st.session_state.checked_in = False
            st.session_state.driver_id = ""
            st.info("Checked out!")
            time.sleep(1)
            st.rerun()
    
    # Auto-refresh every 3 seconds
    time.sleep(3)
    st.rerun()
    
else:
    st.info("Enter your Driver ID in the sidebar to get started")