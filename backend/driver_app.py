import streamlit as st
import requests
import time

API_URL = "http://localhost:5001"

st.set_page_config(page_title="Driver Dashboard", layout="wide")
st.title("🚗 Driver Dashboard")

if "driver_id" not in st.session_state:
    st.session_state.driver_id = ""
    st.session_state.checked_in = False
    st.session_state.current_ride = None

# Sidebar for driver check-in
with st.sidebar:
    st.header("Driver Login")
    driver_id = st.text_input("Enter your Driver ID", key="driver_input")
    
    if st.button("Check In"):
        if driver_id:
            # Hardcoded coordinates for testing (UW campus)
            lat = 47.6550
            lon = -122.3050
            
            res = requests.post(f"{API_URL}/update_driver_location", json={
                "driver_id": driver_id,
                "lat": lat,
                "lon": lon
            })
            if res.ok:
                st.session_state.driver_id = driver_id
                st.session_state.checked_in = True
                st.success("✅ Checked in!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ Check-in failed: {res.text}")
        else:
            st.warning("Enter your Driver ID first")

if st.session_state.checked_in:
    driver_id = st.session_state.driver_id
    
    # Main dashboard
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Available Rides")
        if st.button("Refresh Queue"):
            pass
        
        res = requests.get(f"{API_URL}/driver_view/{driver_id}")
        if res.ok:
            data = res.json()
            
            # Current ride section
            if data["current_ride"]:
                st.success("🚕 Current Ride Assigned")
                ride = data["current_ride"]
                col_ride1, col_ride2 = st.columns(2)
                with col_ride1:
                    st.write(f"**Passenger:** {ride['name']}")
                    st.write(f"**From:** {ride['pickup']['address']}")
                with col_ride2:
                    st.write(f"**To:** {ride['destination']['address']}")
                    st.write(f"**Notes:** {ride.get('notes', 'N/A')}")
                
                if st.button("🏁 Complete Ride"):
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
                            st.write(f"📍 {ride.get('notes', '')}")
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
        st.subheader("📊 Stats")
        st.metric("Driver ID", driver_id)
        st.metric("Status", "On Duty" if st.session_state.checked_in else "Off Duty")
        
        if st.button("Check Out"):
            st.session_state.checked_in = False
            st.session_state.driver_id = ""
            st.info("Checked out!")
            time.sleep(1)
            st.rerun()
else:
    st.info("👈 Enter your Driver ID in the sidebar to get started")