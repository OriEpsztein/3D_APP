import streamlit as st
import os
import BQ_handler
import GRAPH
import SPACES
from google.oauth2 import service_account
from google.cloud import bigquery

# --- 1. Page Setup ---
st.set_page_config(page_title="3D Sensor Digital Twin", layout="wide")
st.title("🧪 3D Experiment Player (Unrestricted)")

# --- 2. Connection ---
@st.cache_resource
def connect_to_gcp():
    env_path = os.path.join("auth", ".env")
    if os.path.exists(env_path):
        from auth import get_bq_client
        return get_bq_client(env_path)
    elif "gcp_service_account" in st.secrets:
        try:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return bigquery.Client(credentials=creds, project=key_dict["project_id"])
        except Exception as e:
            st.error(f"❌ Cloud Connection Error: {e}")
            return None
    else:
        st.error("❌ No credentials found.")
        return None

client = connect_to_gcp()
if not client: st.stop()

# --- Initialize Session States ---
if 'day_data' not in st.session_state: st.session_state.day_data = None
if 'loaded_range' not in st.session_state: st.session_state.loaded_range = None
if 'generated_frames' not in st.session_state: st.session_state.generated_frames = {} 
if 'playback_times' not in st.session_state: st.session_state.playback_times = []

# ==========================================
# SIDEBAR (Data Loading)
# ==========================================
st.sidebar.header("1. Data Source")
selected_space_name = st.sidebar.selectbox("Select Space Model", options=list(SPACES.ROOM_DB.keys()))
current_space_config = SPACES.ROOM_DB[selected_space_name]

st.sidebar.divider()

# Load Structure
structure = BQ_handler.list_datasets_and_tables(client)
if not structure: st.stop()

selected_dataset = st.sidebar.selectbox("Dataset", options=list(structure.keys()), index=None)
if not selected_dataset: st.stop()

selected_table = st.sidebar.selectbox("Table", options=structure[selected_dataset], index=None)
if not selected_table: st.stop()

exp_list = BQ_handler.get_experiment_names(client, selected_dataset, selected_table)
selected_exp = st.sidebar.selectbox("Experiment", options=exp_list, index=None)

# Fetch Data Button
if selected_exp:
    times = BQ_handler.get_experiment_time_range(client, selected_dataset, selected_table, selected_exp)
    if times:
        st.sidebar.write(f"📅 Available: {times['start'].date()} - {times['end'].date()}")
        date_range = st.sidebar.date_input("Select Days", value=[], min_value=times['start'].date(), max_value=times['end'].date())
        
        col_map = {
            "Temperature": "SensorData_temperature",
            "Humidity": "SensorData_humidity",
            "Light": "SensorData_light",
            "Battery": "SensorData_battery"
        }
        selected_params = st.sidebar.multiselect("Parameters", options=list(col_map.keys()), default=["Temperature"])
        
        if st.sidebar.button("📥 Load Dataset", type="primary"):
             if len(date_range) > 0 and selected_params:
                start_d = date_range[0]
                end_d = date_range[-1]
                db_cols = [col_map[k] for k in selected_params]
                
                with st.spinner("Fetching data from BigQuery..."):
                    data = BQ_handler.get_data_for_range(client, selected_dataset, selected_table, selected_exp, start_d, end_d, db_cols)
                    st.session_state.day_data = data
                    st.session_state.loaded_range = f"{start_d} to {end_d}"
                    st.session_state.loaded_params = selected_params
                    # Clear old cache when new data loads
                    st.session_state.generated_frames = {}
                    st.session_state.playback_times = []

# ==========================================
# MAIN PAGE
# ==========================================
day_df = st.session_state.day_data

if day_df is None or day_df.empty:
    st.info("👈 Use the sidebar to load your experiment data first.")
    st.stop()

loaded_map = {k:v for k,v in col_map.items() if k in st.session_state.loaded_params}

st.markdown(f"### 🎞️ Frame Generator ({st.session_state.loaded_range})")

# --- CONTROL PANEL ---
with st.expander("⚙️ Animation Settings", expanded=True):
    
    # 1. RANGE SLIDER (Select Start and End)
    all_times = sorted(day_df['TimeStamp'].unique())
    
    if len(all_times) > 1:
        start_ts, end_ts = st.select_slider(
            "1. Select Time Range to Animate",
            options=all_times,
            value=(all_times[0], all_times[-1]),
            format_func=lambda x: x.strftime("%H:%M:%S")
        )
    else:
        st.warning("Not enough data for a range.")
        st.stop()

    # 2. VISUAL SETTINGS
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_choice = st.radio("Metric", options=list(loaded_map.keys()), horizontal=True)
    with c2:
        opacity = st.slider("Opacity", 0.0, 1.0, 0.2, 0.05)
    with c3:
        voxel_size = st.select_slider("Voxel Size", options=[0.05, 0.08, 0.10, 0.20], value=0.10)

    # 3. GENERATE BUTTON
    if st.button("🚀 Generate ALL Frames", type="primary", use_container_width=True):
        
        # Filter Data to Range
        mask = (day_df['TimeStamp'] >= start_ts) & (day_df['TimeStamp'] <= end_ts)
        sliced_df = day_df.loc[mask]
        
        # --- NO LIMITS: Get ALL timestamps ---
        unique_times_in_range = sorted(sliced_df['TimeStamp'].unique())
        count = len(unique_times_in_range)
        st.toast(f"Starting generation of {count} frames...", icon="⏳")
        
        # PRE-CALCULATION LOOP
        coords = BQ_handler.get_xyz_coordinates(client, selected_dataset, selected_table, selected_exp)
        metric_col = loaded_map[metric_choice]
        
        temp_frames = {}
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ts in enumerate(unique_times_in_range):
            # Update bar
            progress = (i + 1) / count
            progress_bar.progress(progress)
            status_text.text(f"Rendering frame {i+1}/{count} ({ts.strftime('%H:%M:%S')})")
            
            # Generate Figure
            snapshot = sliced_df[sliced_df['TimeStamp'] == ts]
            fig = GRAPH.plot_3d_room(
                snapshot, coords, metric_col, 
                opacity=opacity, voxel_size=voxel_size, 
                space_def=current_space_config, timestamp=ts
            )
            temp_frames[ts] = fig
            
        # Save to Session State
        st.session_state.generated_frames = temp_frames
        st.session_state.playback_times = unique_times_in_range
        st.rerun() # Refresh page to show the player

# ==========================================
# PLAYER INTERFACE (Appears after Generation)
# ==========================================
st.divider()

if st.session_state.generated_frames:
    st.write(f"### 🎬 Playback ({len(st.session_state.playback_times)} Frames)")
    
    # THE "INSTANT" SLIDER
    selected_frame_time = st.select_slider(
        "Scrub to view frame:",
        options=st.session_state.playback_times,
        format_func=lambda x: x.strftime("%H:%M:%S")
    )
    
    # Display the pre-generated figure instantly
    fig_to_show = st.session_state.generated_frames[selected_frame_time]
    st.plotly_chart(fig_to_show, use_container_width=True)

else:
    st.info("👆 Select a range and click 'Generate' to build the animation.")
