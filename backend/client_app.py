import streamlit as st
import requests
import time
import bedrock as br
from geopy.geocoders import Nominatim, Photon
import db

API_URL = "http://10.18.189.186:5001"
WS_URL = "ws://10.18.189.186:5001"

st.set_page_config(page_title="Campus Escort", layout="centered")
st.markdown("""
    <style>
    .stTextInput > div > div > input {
        font-size: 18px;
        padding: 10px;
    }
    .stTextArea textarea {
        font-size: 16px;
        padding: 10px;
    }
    </style>
""", unsafe_allow_html=True)
st.title("DriveHusky - Request a Ride")


if "ride_requested" not in st.session_state:
    st.session_state.ride_requested = False
    st.session_state.uw_id = ""
    st.session_state.destination = ""
    st.session_state.pickup = ""
    st.session_state.notes = ""
    st.session_state.rideID = ""
    st.session_state.status_data = {}

if not st.session_state.ride_requested:
    st.subheader("Enter Your Details")

    with st.form("ride_form"):
        name = st.text_input("Your Name")
        uw_id = st.text_input("UW NetID")
        # chat = st.text_input("Where would you like to be picked up and dropped off today?")
        pickup_text = st.text_input("Pickup Address")
        destination_text = st.text_input("Destination Address")
        notes = st.text_area("Notes (optional)")
        
        if "confirmed" not in st.session_state:
            st.session_state.confirmed = False
        
        if st.form_submit_button("Preview Ride"):
            st.session_state.confirmed = True    
    
    # name = st.text_input("Your Name")
    # uw_id = st.text_input("UW NetID")
    # chat = st.text_input("Where would you like to be picked up and dropped off today?")
    # # pickup = st.text_input("Pickup Address")
    # # destination = st.text_input("Destination Address")
    # notes = st.text_area("Notes (optional)")
    
    # if "confirmed" not in st.session_state:
    #     st.session_state.confirmed = False
    
    # if st.button("Preview Ride"):
    #     st.session_state.confirmed = True
    
    if st.session_state.confirmed:
        user_pickup = br.parse_ride_request(pickup_text)
        user_destination = br.parse_ride_request(destination_text)
        pickup = user_pickup["location"]
        destination = user_destination["location"]

        pickup_address = pickup
        
        destination_address = destination

        # user_pickup = br.parse_ride_request(pickup_text)["location"]
        # user_destination = br.parse_ride_request(destination_text)["location"]
        # pickup = user_pickup["location"]
        # destination = user_destination["location"]

        geolocator = Nominatim(user_agent="campus-pickup")
        viewbox = [(47.648546, -122.333540), (47.682512, -122.270640)]
        if user_destination is not None and user_pickup is not None:
            destination_address = str(geolocator.geocode(f"{destination}, Seattle, WA", exactly_one=True, viewbox=viewbox, bounded=True, timeout=10))
            pickup_address = geolocator.geocode(f"{pickup}, Seattle, WA", exactly_one=True, viewbox=viewbox, bounded=True, timeout=10)

            # st.write(str(pickup_address))
            # destination = db.geocode(user_destination)
            # pickup = db.geocode(user_pickup)


        st.markdown("### Confirm Your Ride Details:")
        st.write(f"**Name:** {name}")
        st.write(f"**UW NetID:** {uw_id}")
        st.write(f"**Pickup:** {str(pickup_address)}")
        st.write(f"**Destination:** {destination_address}")
        if notes:
            st.write(f"**Notes:** {notes}")
    
        if pickup == None or destination == None:
            st.error("Pickup or dropoff is invalid")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Request Ride"):
                    with st.spinner("Requesting ride..."):
                        res = requests.post(f"{API_URL}/request_ride", json={
                            "name": name,
                            "uw_id": uw_id,
                            "pickup_address": str(pickup_address),
                            "destination_address": destination_address,
                            "notes": notes
                        })
                        
                        if res.ok:
                            ride = res.json()
                            st.session_state.rideID = ride["ride_id"]
                            st.session_state.uw_id = uw_id
                            st.session_state.destination = destination
                            st.session_state.pickup = str(pickup)
                            st.session_state.notes = notes
                            st.session_state.ride_requested = True
                            st.session_state.confirmed = False
                            st.success("✅ Ride requested!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to request ride")
            
            with col2:
                if st.button("Cancel"):
                    st.session_state.confirmed = False
                    st.warning("Cancelled.")
                    st.session_state.ride_requested = False            
                    st.rerun()

else:
    # Ride tracking screen
    st.subheader("Tracking Your Ride")
    
    col_info, col_status = st.columns([2, 1])
    
    with col_info:
        st.write(f"**From:** {st.session_state.pickup}")
        st.write(f"**To:** {st.session_state.destination}")
        st.write(f"**Ride ID:** {st.session_state.rideID}")
    
    # Fetch current status
    res = requests.get(f"{API_URL}/client_status/{st.session_state.rideID}")
    
    if res.ok:
        status = res.json()
        
        if status.get("error"):
            st.error(f"{status['error']}")
        else:
            # Status indicator
            if status["status"] == "waiting":
                st.warning(f"Waiting for driver assignment")
                st.write(f"**Queue Position:** {status['queue_position']}")
                st.write(f"**Estimated Wait:** {status['eta']}")
                
                # Auto-refresh every 3 seconds
                placeholder = st.empty()
                with placeholder.container():
                    st.info("Refreshing in 5 seconds...")
                # Cancel ride button
                # if st.button("Cancel Ride Request"):
                #     st.session_state.ride_requested = False
                #     st.session_state.confirmed = False
                #     st.warning("Ride request cancelled")
                              
                #     time.sleep(1)
                #     st.rerun()                    
                time.sleep(5)
                st.rerun()
            
            elif status["status"] == "in_car":
                st.success("Driver on the way!")
                
                if status.get("driver_location"):
                    col_loc, col_eta = st.columns(2)
                    with col_loc:
                        st.metric("Driver Location", 
                                f"{status['driver_location']['lat']:.4f}, {status['driver_location']['lon']:.4f}")
                    with col_eta:
                        st.metric("ETA", status['eta'])
                
                st.write(f"**Driver ID:** {status.get('driver_id', 'N/A')}")
                
                # Auto-refresh every 2 seconds for live updates
                placeholder = st.empty()
                with placeholder.container():
                    st.info("Live tracking active... refreshing in 5 seconds")                      
                time.sleep(5)
                st.rerun()
            
            elif status["status"] == "completed":
                st.success("✅ Ride completed! Thanks for using Campus Escort.")
            else:
                st.info(f"Status: {status['status']}")
    else:
        st.error("Failed to fetch ride status")
    
