from typing import Dict, List, Optional
from google.cloud import bigquery
import pandas as pd
import streamlit as st

# ==========================================
#       STRUCTURE & METADATA QUERIES
# ==========================================

@st.cache_data(ttl=600)
def list_datasets_and_tables(_client: bigquery.Client) -> Dict[str, List[str]]:
    """Scans the Google Cloud Project for all available BigQuery Datasets and Tables."""
    structure = {}
    try:
        datasets = list(_client.list_datasets())
        if not datasets:
            return {}

        for dataset in datasets:
            ds_id = dataset.dataset_id
            try:
                tables = list(_client.list_tables(ds_id))
                structure[ds_id] = [t.table_id for t in tables]
            except Exception as e:
                print(f"⚠️ Could not list tables for dataset {ds_id}: {e}")
                structure[ds_id] = []

        return structure
    except Exception as e:
        print(f"❌ Error listing datasets: {e}")
        return {}

@st.cache_data(ttl=600)
def get_experiment_names(_client: bigquery.Client, dataset_id: str, table_id: str) -> List[str]:
    """Fetches all unique experiment names from the table."""
    full_table_id = f"{_client.project}.{dataset_id}.{table_id}"
    
    query = f"""
    SELECT DISTINCT ExperimentData_Exp_name 
    FROM `{full_table_id}` 
    WHERE ExperimentData_Exp_name IS NOT NULL
    ORDER BY ExperimentData_Exp_name
    """
    try:
        query_job = _client.query(query)
        return [row[0] for row in query_job.result()]
    except Exception as e:
        print(f"❌ Error querying experiment names: {e}")
        return []

@st.cache_data(ttl=600)
def get_experiment_time_range(_client: bigquery.Client, dataset: str, table: str, exp_name: str) -> dict:
    """Gets the absolute start and end timestamps for a specific experiment."""
    full_table = f"`{_client.project}.{dataset}.{table}`"
    
    query = f"""
    SELECT MIN(TimeStamp) as start_time, MAX(TimeStamp) as end_time
    FROM {full_table}
    WHERE ExperimentData_Exp_name = @exp_name
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("exp_name", "STRING", exp_name)]
    )
    try:
        job = _client.query(query, job_config=job_config)
        row = next(job.result())
        if row.start_time is None: return {}
        return {"start": row.start_time, "end": row.end_time}
    except Exception as e:
        print(f"❌ Error fetching time range: {e}")
        return {}

# ==========================================
#          COORDINATE FETCHING
# ==========================================

@st.cache_data(ttl=3600)
def get_xyz_coordinates(_client: bigquery.Client, dataset: str, table: str, exp_name: str) -> pd.DataFrame:
    """
    Fetches the MOST RECENT valid coordinates for each sensor.
    Ignores rows where coordinates are (0,0,0) and duplicates.
    """
    full_table = f"`{_client.project}.{dataset}.{table}`"
    print(f"📍 Fetching latest sensor coordinates for '{exp_name}'...")

    query = f"""
    SELECT 
        SensorData_Name, 
        MetaData_Coordinates_x, 
        MetaData_Coordinates_y, 
        MetaData_Coordinates_z
    FROM {full_table}
    WHERE ExperimentData_Exp_name = @exp_name
      -- Filter out invalid 'ghost' logs
      AND NOT (MetaData_Coordinates_x = 0 AND MetaData_Coordinates_y = 0 AND MetaData_Coordinates_z = 0)
    
    -- Keep only the latest entry for each sensor
    QUALIFY ROW_NUMBER() OVER (PARTITION BY SensorData_Name ORDER BY TimeStamp DESC) = 1
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("exp_name", "STRING", exp_name)]
    )
    
    try:
        df = _client.query(query, job_config=job_config).to_dataframe()
        return df.set_index("SensorData_Name") if not df.empty else pd.DataFrame()
    except Exception as e:
        print(f"❌ Error fetching coordinates: {e}")
        return pd.DataFrame()

# ==========================================
#          DATA FETCHING (OPTIMIZED)
# ==========================================

@st.cache_data(ttl=600)
def get_data_for_range(_client: bigquery.Client, dataset: str, table: str, exp_name: str, start_date, end_date, metrics: List[str]) -> pd.DataFrame:
    """
    🚀 BULK FETCH: Retrieves data for a DATE RANGE (Start -> End).
    """
    full_table = f"`{_client.project}.{dataset}.{table}`"
    print(f"📥 Fetching data from {start_date} to {end_date}...")

    # Dynamic SQL Construction
    cols_to_fetch = ["TimeStamp", "SensorData_Name"] + metrics
    cols_string = ", ".join(cols_to_fetch)

    # UPDATED SQL: Uses 'BETWEEN' for the date range
    query = f"""
    SELECT {cols_string}
    FROM {full_table}
    WHERE ExperimentData_Exp_name = @exp_name
      AND DATE(TimeStamp) BETWEEN @start_date AND @end_date
    ORDER BY TimeStamp ASC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("exp_name", "STRING", exp_name),
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date)
        ]
    )
    
    try:
        df = _client.query(query, job_config=job_config).to_dataframe()
        return df
    except Exception as e:
        print(f"❌ Error fetching bulk data: {e}")
        return pd.DataFrame()

# ==========================================
#          LEGACY / UTILITY
# ==========================================

@st.cache_data(show_spinner=False)
def get_experiment_data(_client: bigquery.Client, dataset: str, table: str, exp_name: str, start_time, end_time, metric: str = None) -> pd.DataFrame:
    """
    Fetches data for a specific time range. 
    Useful if you need a specific slice instead of the whole day.
    """
    full_table = f"`{_client.project}.{dataset}.{table}`"
    
    # Map UI metric names to SQL columns
    column_map = {
        "battery": "SensorData_battery",
        "temp": "SensorData_temperature",
        "light": "SensorData_light",
        "RH": "SensorData_humidity" 
    }

    # If a specific metric is asked, ensure we fetch it, otherwise defaults to name/time
    extra_column = ""
    if metric and metric in column_map:
        extra_column = f", {column_map[metric]}"
    
    query = f"""
    SELECT TimeStamp, SensorData_Name{extra_column} 
    FROM {full_table}
    WHERE ExperimentData_Exp_name = @exp_name
      AND TimeStamp BETWEEN @start_ts AND @end_ts
    ORDER BY TimeStamp ASC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("exp_name", "STRING", exp_name),
            bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", start_time),
            bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", end_time),
        ]
    )
    
    try:
        df = _client.query(query, job_config=job_config).to_dataframe()
        return df
    except Exception as e:
        print(f"❌ Error fetching specific data slice: {e}")
        return pd.DataFrame()