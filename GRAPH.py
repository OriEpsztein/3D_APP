import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.spatial.distance import cdist

# ==========================================
#           INTERPOLATION ENGINE
# ==========================================

def generate_grid_points(dims, cube_size):
    """Generates a 3D grid based on the PASSED dimensions."""
    if cube_size <= 0: cube_size = 0.1
    
    xs = np.arange(cube_size/2, dims['x'], cube_size)
    ys = np.arange(cube_size/2, dims['y'], cube_size)
    zs = np.arange(cube_size/2, dims['z'], cube_size)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing='ij')
    return np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])

def calculate_interpolation_weights(grid_points, sensor_coords, power=2):
    dists = cdist(grid_points, sensor_coords)
    dists[dists < 1e-6] = 1e-6
    weights = 1.0 / np.power(dists, power)
    return weights / np.sum(weights, axis=1)[:, None]

# ==========================================
#           3D MESH GENERATION
# ==========================================

def create_voxel_mesh(grid_df, metric_name, cmin, cmax, opacity_val, cube_size):
    if grid_df.empty: return None
    hs = (cube_size * 0.85) / 2.0 
    
    all_x, all_y, all_z, all_intensity = [], [], [], []
    all_i, all_j, all_k = [], [], []
    base_i = np.array([7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2])
    base_j = np.array([3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3])
    base_k = np.array([0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6])
    
    offset = 0
    for _, row in grid_df.iterrows():
        cx, cy, cz, val = row['x'], row['y'], row['z'], row['value']
        all_x.extend([cx-hs, cx+hs, cx+hs, cx-hs, cx-hs, cx+hs, cx+hs, cx-hs])
        all_y.extend([cy-hs, cy-hs, cy+hs, cy+hs, cy-hs, cy-hs, cy+hs, cy+hs])
        all_z.extend([cz-hs, cz-hs, cz-hs, cz-hs, cz+hs, cz+hs, cz+hs, cz+hs])
        all_intensity.extend([val] * 8)
        all_i.extend(base_i + offset); all_j.extend(base_j + offset); all_k.extend(base_k + offset)
        offset += 8

    return go.Mesh3d(
        x=all_x, y=all_y, z=all_z, i=all_i, j=all_j, k=all_k, 
        intensity=all_intensity, colorscale='bluered', cmin=cmin, cmax=cmax, 
        opacity=opacity_val, name='Heatmap', hoverinfo='skip'
    )

def get_metal_frame_geometries(dims, config):
    """Builds structure based on PASSED dims and config."""
    geos = []
    dx, dy, dz = dims['x'], dims['y'], dims['z']
    pt, bt = config['pillar_thickness'], config['bar_thickness']
    
    # Pillars
    corners = [(0,0), (dx-pt, 0), (0, dy-pt), (dx-pt, dy-pt)]
    for cx, cy in corners:
        geos.append({
            'x': [cx, cx+pt, cx+pt, cx, cx, cx+pt, cx+pt, cx],
            'y': [cy, cy, cy+pt, cy+pt, cy, cy, cy+pt, cy+pt],
            'z': [0, 0, 0, 0, dz, dz, dz, dz],
            'color': 'darkgrey'
        })
    # Bars
    for fz in config['levels']:
        geos.append({'x': [0, dx, dx, 0]*2, 'y': [0, 0, pt, pt]*2, 'z': [fz, fz, fz, fz, fz+bt, fz+bt, fz+bt, fz+bt], 'color': 'silver'})
        geos.append({'x': [0, dx, dx, 0]*2, 'y': [dy-pt, dy-pt, dy, dy]*2, 'z': [fz, fz, fz, fz, fz+bt, fz+bt, fz+bt, fz+bt], 'color': 'silver'})
        geos.append({'x': [0, 0, pt, pt]*2, 'y': [0, dy, dy, 0]*2, 'z': [fz, fz, fz, fz, fz+bt, fz+bt, fz+bt, fz+bt], 'color': 'silver'})
        geos.append({'x': [dx-pt, dx-pt, dx, dx]*2, 'y': [0, dy, dy, 0]*2, 'z': [fz, fz, fz, fz, fz+bt, fz+bt, fz+bt, fz+bt], 'color': 'silver'})
    return geos

# ==========================================
#           MAIN PLOTTING FUNCTION
# ==========================================

def plot_3d_room(snapshot_df, coords_df, metric_col, opacity, voxel_size, space_def, timestamp=None):
    """
    Now accepts 'space_def' which contains 'dims' and 'config' from SPACES.py
    """
    merged = snapshot_df.merge(coords_df, left_on='SensorData_Name', right_index=True)
    if merged.empty: return go.Figure()

    # Extract geometry data
    ROOM_DIMS = space_def['dims']
    FRAME_CFG = space_def['config']

    l_min, l_max = merged[metric_col].min(), merged[metric_col].max()
    if l_min == l_max: l_min -= 0.1; l_max += 0.1

    # Generate Grid using DYNAMIC Dims
    grid_pts = generate_grid_points(ROOM_DIMS, voxel_size)
    
    sensor_xyz = merged[['MetaData_Coordinates_x', 'MetaData_Coordinates_y', 'MetaData_Coordinates_z']].values
    sensor_vals = merged[metric_col].values
    
    weights = calculate_interpolation_weights(grid_pts, sensor_xyz)
    interp_vals = np.dot(weights, sensor_vals)
    
    grid_df = pd.DataFrame(grid_pts, columns=['x', 'y', 'z'])
    grid_df['value'] = interp_vals
    
    fig = go.Figure()
    
    # 1. Heatmap
    voxel_trace = create_voxel_mesh(grid_df, metric_col, l_min, l_max, opacity, voxel_size)
    if voxel_trace: fig.add_trace(voxel_trace)
    
    # 2. Frame (Pass the specific config)
    for s in get_metal_frame_geometries(ROOM_DIMS, FRAME_CFG):
        fig.add_trace(go.Mesh3d(
            x=s['x'], y=s['y'], z=s['z'], 
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], 
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], 
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6], 
            color=s['color'], opacity=0.7, 
            showlegend=False, hoverinfo='skip'
        ))
    
    # 3. Sensors
    fig.add_trace(go.Scatter3d(
        x=merged['MetaData_Coordinates_x'], 
        y=merged['MetaData_Coordinates_y'], 
        z=merged['MetaData_Coordinates_z'], 
        mode='markers', 
        marker=dict(size=8, color='black', symbol='diamond', line=dict(width=2, color='white')), 
        text=merged['SensorData_Name'], 
        customdata=merged[metric_col],
        hovertemplate='<b>%{text}</b><br>Reading: %{customdata:.2f}<extra></extra>'
    ))
    
    # Title
    time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else "Snapshot"
    title_text = f"<b>{time_str}</b><br>Min: {l_min:.2f} | Max: {l_max:.2f}"

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Width', range=[0, ROOM_DIMS['x']]),
            yaxis=dict(title='Depth', range=[0, ROOM_DIMS['y']]),
            zaxis=dict(title='Height', range=[0, ROOM_DIMS['z']]),
            aspectmode='manual',
            aspectratio=dict(x=ROOM_DIMS['x'], y=ROOM_DIMS['y'], z=ROOM_DIMS['z'])
        ), 
        title=dict(text=title_text, x=0.5, font=dict(size=20)),
        margin=dict(t=60, b=0, l=0, r=0)
    )
    return fig