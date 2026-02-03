import streamlit as st
import os
import BQ_handler
import GRAPH
import SPACES 
from auth.auth import get_bq_client

# --- 1. Page Setup ---
st.set_page_config(page_title="3D Sensor Digital Twin", layout="wide")
st.title("🧪 3D Experiment Snapshot")

# --- 2. Connection ---
@st.cache_resource
def connect_to_gcp():
    env_path = os.path.join("auth", ".env")
    try:
        return get_bq_client(env_path)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

client = connect_to_gcp()
if not client: st.stop()

# --- Initialize Session States ---
if 'day_data' not in st.session_state: st.session_state.day_data = None
if 'loaded_range' not in st.session_state: st.session_state.loaded_range = None
if 'current_fig' not in st.session_state: st.session_state.current_fig = None

# ==========================================
# SIDEBAR
# ==========================================

# --- 0. SPACE CONFIGURATION (New) ---
st.sidebar.header("0. Space Configuration")
# Defaults to the first option, or you can make this empty too if you prefer
selected_space_name = st.sidebar.selectbox("Select Space Model", options=list(SPACES.ROOM_DB.keys()))
current_space_config = SPACES.ROOM_DB[selected_space_name]

st.sidebar.divider()

# --- 1. SOURCE ---
st.sidebar.header("1. Source")
structure = BQ_handler.list_datasets_and_tables(client)
if not structure: st.stop()

selected_dataset = st.sidebar.selectbox("Dataset", options=list(structure.keys()), index=None, placeholder="Choose a dataset...")
if not selected_dataset: st.stop()

selected_table = st.sidebar.selectbox("Table", options=structure[selected_dataset], index=None, placeholder="Choose a table...")
if not selected_table: st.stop()

# --- 2. EXPERIMENT ---
st.sidebar.header("2. Experiment")
exp_list = BQ_handler.get_experiment_names(client, selected_dataset, selected_table)
selected_exp = st.sidebar.selectbox("Experiment", options=exp_list, index=None, placeholder="Choose an experiment...")
if not selected_exp: st.stop()

# --- 3. DATA FETCHING ---
st.sidebar.header("3. Data Fetching")
times = BQ_handler.get_experiment_time_range(client, selected_dataset, selected_table, selected_exp)

if times:
    date_range = st.sidebar.date_input("Select Date Range", value=[], min_value=times['start'].date(), max_value=times['end'].date())
    
    start_d, end_d = None, None
    if len(date_range) == 2:
        start_d, end_d = date_range
    elif len(date_range) == 1:
        start_d = end_d = date_range[0]

    col_map = {
        "Temperature": "SensorData_temperature",
        "Humidity": "SensorData_humidity",
        "Light": "SensorData_light",
        "Battery": "SensorData_battery"
    }
    
    # Starts Empty
    selected_params = st.sidebar.multiselect("Select Parameters", options=list(col_map.keys()), default=[])
    db_cols = [col_map[k] for k in selected_params]
    
    st.sidebar.markdown("---")
    is_ready = (start_d is not None) and (len(selected_params) > 0)
    
    if st.sidebar.button("📥 Fetch Data", type="primary", disabled=not is_ready):
        with st.spinner(f"Loading data from {start_d} to {end_d}..."):
            data = BQ_handler.get_data_for_range(client, selected_dataset, selected_table, selected_exp, start_d, end_d, db_cols)
            st.session_state.day_data = data
            st.session_state.loaded_range = f"{start_d} - {end_d}"
            st.session_state.loaded_params = selected_params

# ==========================================
# MAIN PAGE
# ==========================================
day_df = st.session_state.day_data

if day_df is None or day_df.empty:
    st.info("👈 Please complete the selection in the sidebar to begin.")
    st.stop()

loaded_map = {k:v for k,v in col_map.items() if k in st.session_state.loaded_params}
if not loaded_map: st.error("No valid parameters loaded."); st.stop()

st.divider()

# --- 🚀 FORM WRAPPER (Visuals & Timeline) ---
with st.form("controls_form"):
    
    # 1. Timeline Slider
    available_times = day_df['TimeStamp'].unique()
    st.caption(f"📅 Loaded Range: **{st.session_state.loaded_range}** | {len(available_times)} snapshots")
    
    selected_ts = st.select_slider(
        "⏱️ Scrub Timeline", 
        options=available_times, 
        format_func=lambda x: x.strftime("%Y-%m-%d %H:%M:%S")
    )

    st.write("### ⚙️ Visual Settings")
    c1, c2, c3 = st.columns([2, 2, 2])

    with c1:
        metric_choice = st.radio("Visualize Metric:", options=list(loaded_map.keys()), horizontal=True)
    
    with c2:
        opacity = st.slider("Heatmap Opacity", 0.0, 1.0, 0.85, 0.05)

    with c3:
        voxel_size = st.select_slider(
            "Voxel Resolution (Size)", 
            options=[0.05, 0.08, 0.10, 0.15, 0.20], 
            value=0.10,
            format_func=lambda x: f"{x}m ({'High' if x<0.1 else 'Low'} Res)"
        )

    st.write("##") 
    # Triggers the re-run
    update_plot = st.form_submit_button("🔄 Update Plot", type="primary", use_container_width=True)

# --- RENDER LOGIC ---
plot_container = st.empty()

if update_plot:
    coords = BQ_handler.get_xyz_coordinates(client, selected_dataset, selected_table, selected_exp)
    snapshot_df = day_df[day_df['TimeStamp'] == selected_ts]
    metric_col = loaded_map[metric_choice]

    if not coords.empty and not snapshot_df.empty:
        # Pass ALL new parameters: Opacity, Voxel Size, and SPACE CONFIG
        fig = GRAPH.plot_3d_room(
            snapshot_df, 
            coords, 
            metric_col, 
            opacity=opacity, 
            voxel_size=voxel_size, 
            space_def=current_space_config,  # <--- From SPACES.py
            timestamp=selected_ts
        )
        st.session_state.current_fig = fig  
    else:
        st.error("Data missing for this moment.")

if st.session_state.current_fig is not None:
    plot_container.plotly_chart(st.session_state.current_fig, use_container_width=True)
else:
    plot_container.info("Select settings above and click 'Update Plot'.")