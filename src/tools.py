import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any, Union, Optional, Tuple
import json
import base64
import re

from src.models import ArgoDataPoint, RegionBounds
from src.database import ArgoDatabase
from langchain.agents import tool

def create_download_link(fig, filename: str, file_format: str = "html") -> str:
    if file_format == "html":
        html_str = fig.to_html()
        b64 = base64.b64encode(html_str.encode()).decode()
        return f'<a href="data:text/html;base64,{b64}" download="{filename}.html">📥 Download {filename}</a>'
    elif file_format == "json":
        json_str = fig.to_json()
        b64 = base64.b64encode(json_str.encode()).decode()
        return f'<a href="data:application/json;base64,{b64}" download="{filename}.json">📥 Download {filename} Data</a>'
    return ""

def _validate_and_convert_data(data: Union[List[Dict[str, Any]], str]) -> List[ArgoDataPoint]:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            st.error("Invalid data format received")
            return []
    if not isinstance(data, list):
        st.error("Data must be a list of dictionaries")
        return []
    validated_data = []
    for item in data:
        try:
            validated_data.append(ArgoDataPoint(**item))
        except Exception as e:
            st.warning(f"Skipping invalid data point: {e}")
            continue
    return validated_data

def _plot_profiles_core(df: pd.DataFrame, region_info: str = "") -> str:
    df = df.dropna(subset=['temp', 'psal', 'pres'])
    if df.empty:
        st.warning("No valid temperature, salinity, and pressure data found.")
        return "No valid profile data available."

    # THE FIX IS HERE: Sort data by pressure to ensure correct line plotting
    df = df.sort_values(by='pres')

    st.subheader(f"📊 Depth Profiles {region_info}")

    col1, col2 = st.columns(2)

    with col1:
        temp_fig = px.line(
            df, x='temp', y='pres',
            title='Temperature vs. Depth',
            labels={'temp': 'Temperature (°C)', 'pres': 'Pressure (dbar)'}
        )
        temp_fig.update_yaxes(autorange="reversed", title_text="Depth (dbar)")
        temp_fig.update_layout(height=500)
        st.plotly_chart(temp_fig, use_container_width=True)
        st.markdown(create_download_link(temp_fig, "temperature_profile"), unsafe_allow_html=True)

    with col2:
        sal_fig = px.line(
            df, x='psal', y='pres',
            title='Salinity vs. Depth',
            labels={'psal': 'Salinity (PSU)', 'pres': 'Pressure (dbar)'}
        )
        sal_fig.update_yaxes(autorange="reversed", title_text="Depth (dbar)")
        sal_fig.update_layout(height=500)
        st.plotly_chart(sal_fig, use_container_width=True)
        st.markdown(create_download_link(sal_fig, "salinity_profile"), unsafe_allow_html=True)

    stats = {
        'Total Measurements': len(df),
        'Depth Range': f"{df['pres'].min():.1f} - {df['pres'].max():.1f} dbar",
        'Temperature Range': f"{df['temp'].min():.2f} - {df['temp'].max():.2f} °C",
        'Salinity Range': f"{df['psal'].min():.2f} - {df['psal'].max():.2f} PSU"
    }
    st.info(" | ".join([f"{k}: {v}" for k, v in stats.items()]))
    return (f"Successfully plotted depth profiles for {len(df)} data points. "
            f"Temperature range: {df['temp'].min():.2f} - {df['temp'].max():.2f} °C, "
            f"Salinity range: {df['psal'].min():.2f} - {df['psal'].max():.2f} PSU.")

def _plot_sst_core(df: pd.DataFrame, region_info: str = "") -> str:
    surface_data = df[(df['pres'] <= 10) & df['temp'].notna() & df['timestamp'].notna()]
    if surface_data.empty:
        st.warning("No valid surface temperature data found (pressure ≤ 10 dbar).")
        return "No valid SST data available."

    st.subheader(f"🌡️ Sea Surface Temperature Time-Series {region_info}")
    surface_data = surface_data.copy() # Avoid SettingWithCopyWarning
    surface_data['timestamp'] = pd.to_datetime(surface_data['timestamp'], errors='coerce')
    surface_data = surface_data.dropna(subset=['timestamp']).sort_values('timestamp')

    fig = px.line(
        surface_data, x='timestamp', y='temp',
        title='Sea Surface Temperature Over Time',
        labels={'timestamp': 'Date', 'temp': 'Temperature (°C)'},
        markers=True
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(create_download_link(fig, "sst_timeseries"), unsafe_allow_html=True)

    stats = {
        'Data Points': len(surface_data),
        'Temperature Range': f"{surface_data['temp'].min():.2f} - {surface_data['temp'].max():.2f} °C",
        'Average SST': f"{surface_data['temp'].mean():.2f} °C",
        'Time Period': f"{surface_data['timestamp'].min().strftime('%Y-%m-%d')} to {surface_data['timestamp'].max().strftime('%Y-%m-%d')}"
    }
    st.info(" | ".join([f"{k}: {v}" for k, v in stats.items()]))
    return f"Successfully plotted SST time-series for {len(surface_data)} surface measurements. Average SST: {surface_data['temp'].mean():.2f}°C."

@tool
def plot_profiles(data: Union[List[Dict[str, Any]], str], region_info: str = ""):
    """
    Plot temperature and salinity depth profiles side-by-side from ARGO data.
    """
    if not data:
        st.warning("No data provided for profile plots.")
        return "No data was provided to plot profiles."

    validated = _validate_and_convert_data(data)
    if not validated:
        return "No valid data points found for plotting profiles."

    df = pd.DataFrame([p.dict() for p in validated])
    return _plot_profiles_core(df, region_info)

@tool
def plot_sea_surface_temperature_timeseries(data: Union[List[Dict[str, Any]], str], region_info: str = ""):
    """
    Plot a time-series line chart of sea surface temperature from ARGO data.
    """
    if not data:
        st.warning("No data provided for SST plot.")
        return "No data was provided to plot SST time-series."

    validated = _validate_and_convert_data(data)
    if not validated:
        return "No valid data points found for SST plot."

    df = pd.DataFrame([p.dict() for p in validated])
    return _plot_sst_core(df, region_info)

# -----------------
# DB-backed tools
# -----------------

_REGION_MAP = {
    "arabian sea": RegionBounds(min_lat=8, max_lat=25, min_lon=50, max_lon=75, region_name="Arabian Sea"),
    "bay of bengal": RegionBounds(min_lat=8, max_lat=22, min_lon=80, max_lon=95, region_name="Bay of Bengal"),
    "equatorial indian": RegionBounds(min_lat=-5, max_lat=5, min_lon=50, max_lon=100, region_name="Equatorial Indian"),
    "indian ocean": RegionBounds(min_lat=-40, max_lat=25, min_lon=20, max_lon=120, region_name="Indian Ocean"),
}

_BOUNDS_RE = re.compile(
    r"latitude\s+BETWEEN\s+(-?\d+(?:\.\d+)?)\s+AND\s+(-?\d+(?:\.\d+)?)\s+AND\s+longitude\s+BETWEEN\s+(-?\d+(?:\.\d+)?)\s+AND\s+(-?\d+(?:\.\d+)?)",
    re.IGNORECASE
)

def _resolve_db() -> ArgoDatabase:
    # Prefer session db if available
    try:
        if "db" in st.session_state and isinstance(st.session_state.db, ArgoDatabase):
            return st.session_state.db
    except Exception:
        pass
    return ArgoDatabase()

def _parse_region_or_bounds(text_or_region: str) -> Tuple[RegionBounds, str]:
    """
    Accepts either a region name or a bounds string like:
    'USER SELECTED MAP REGION: latitude BETWEEN x AND y AND longitude BETWEEN a AND b...'
    Returns (RegionBounds, label).
    """
    s = (text_or_region or "").strip()
    if not s:
        # Default to Indian Ocean if unspecified
        rb = _REGION_MAP["indian ocean"]
        return rb, rb.region_name or "Indian Ocean"

    # Try map bounds first
    m = _BOUNDS_RE.search(s)
    if m:
        min_lat, max_lat, min_lon, max_lon = map(float, m.groups())
        rb = RegionBounds(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon, region_name="Selected Map Region")
        label = f"(Lat {min_lat:.2f}–{max_lat:.2f}, Lon {min_lon:.2f}–{max_lon:.2f})"
        return rb, label

    # Try named region
    key = s.lower()
    if key in _REGION_MAP:
        rb = _REGION_MAP[key]
        return rb, rb.region_name or s

    # If text contains a known region keyword
    for name, rb in _REGION_MAP.items():
        if name in key:
            return rb, rb.region_name or name

    # Fallback to Indian Ocean
    rb = _REGION_MAP["indian ocean"]
    return rb, rb.region_name or "Indian Ocean"

@tool
def plot_profiles_from_db(region_or_bounds: str = "", limit: int = 2000):
    """
    Query the main database for the specified region (by name or WHERE-bounds string) and render depth profiles.
    Pass either a known region name (e.g., 'Bay of Bengal') or the exact bounds line that includes:
    'latitude BETWEEN <min_lat> AND <max_lat> AND longitude BETWEEN <min_lon> AND <max_lon>'
    """
    db = _resolve_db()
    region, label = _parse_region_or_bounds(region_or_bounds)
    data = db.get_region_data(region, limit=int(limit))
    if not data:
        st.warning(f"No ARGO data found for {label}. Try a larger area or different region.")
        return f"No data for {label}."
    df = pd.DataFrame([ArgoDataPoint(**d).dict() for d in data])
    return _plot_profiles_core(df, f"({label})")

@tool
def plot_sst_from_db(region_or_bounds: str = "", limit: int = 5000):
    """
    Query the main database for the specified region (by name or WHERE-bounds string) and render SST time series (pres <= 10).
    Pass either a known region name (e.g., 'Bay of Bengal') or the exact bounds line that includes:
    'latitude BETWEEN <min_lat> AND <max_lat> AND longitude BETWEEN <min_lon> AND <max_lon>'
    """
    db = _resolve_db()
    region, label = _parse_region_or_bounds(region_or_bounds)
    data = db.get_surface_temperature_timeseries(region)
    if not data:
        st.warning(f"No surface temperature data found for {label}.")
        return f"No surface data for {label}."
    df = pd.DataFrame([ArgoDataPoint(**d).dict() for d in data])
    return _plot_sst_core(df, f"({label})")