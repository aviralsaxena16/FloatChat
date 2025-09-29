import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from langchain.agents import tool
from typing import List, Dict, Any, Union
import base64
import json
from io import BytesIO
import zipfile
from datetime import datetime

from src.models import ArgoDataPoint, QueryResponse, RegionBounds, RegionStats
from src.region_utils import RegionCalculator

def create_download_link(fig, filename: str, file_format: str = "html") -> str:
    """Create a download link for plotly figures"""
    if file_format == "html":
        html_str = fig.to_html()
        b64 = base64.b64encode(html_str.encode()).decode()
        return f'<a href="data:text/html;base64,{b64}" download="{filename}.html">📥 Download {filename}</a>'
    elif file_format == "json":
        json_str = fig.to_json()
        b64 = base64.b64encode(json_str.encode()).decode()
        return f'<a href="data:application/json;base64,{b64}" download="{filename}.json">📥 Download {filename} Data</a>'

def validate_and_convert_data(data: Union[List[Dict[str, Any]], str]) -> List[ArgoDataPoint]:
    """Validate and convert data to ArgoDataPoint objects"""
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

@tool
def calculate_statistics(data: Union[List[Dict[str, Any]], str], parameter: str = "temperature", region_info: str = ""):
    """
    Calculate statistical measures for oceanographic parameters.
    Input: List of dictionaries or JSON string with oceanographic data.
    Parameter: 'temperature', 'salinity', or 'pressure'
    """
    if not data:
        return f"No data provided for {parameter} statistics."
    
    validated_data = validate_and_convert_data(data)
    if not validated_data:
        return f"No valid data points found for {parameter} statistics."
    
    df = pd.DataFrame([point.dict() for point in validated_data])
    
    # Map parameter names to actual column names
    param_mapping = {
        'temperature': 'temp',
        'salinity': 'psal', 
        'pressure': 'pres'
    }
    
    col_name = param_mapping.get(parameter.lower(), parameter.lower())
    
    if col_name not in df.columns:
        return f"Parameter '{parameter}' not found in data."
    
    # Filter out null values
    valid_data = df[df[col_name].notna()][col_name]
    
    if valid_data.empty:
        return f"No valid {parameter} data found."
    
    # Calculate statistics
    stats = {
        'count': len(valid_data),
        'mean': valid_data.mean(),
        'median': valid_data.median(),
        'std': valid_data.std(),
        'min': valid_data.min(),
        'max': valid_data.max(),
        'q25': valid_data.quantile(0.25),
        'q75': valid_data.quantile(0.75)
    }
    
    # Format units
    units = {
        'temperature': '°C',
        'salinity': 'PSU',
        'pressure': 'dbar'
    }
    unit = units.get(parameter.lower(), '')
    
    # Create response
    response = f"**{parameter.title()} Statistics {region_info}**\n\n"
    response += f"• **Average**: {stats['mean']:.2f} {unit}\n"
    response += f"• **Median**: {stats['median']:.2f} {unit}\n"
    response += f"• **Range**: {stats['min']:.2f} - {stats['max']:.2f} {unit}\n"
    response += f"• **Standard Deviation**: {stats['std']:.2f} {unit}\n"
    response += f"• **Data Points**: {stats['count']:,}\n"
    
    return response
@tool
def plot_profiles(data: Union[List[Dict[str, Any]], str], region_info: str = ""):
    """
    Plot temperature and salinity depth profiles side-by-side.
    Input: List of dictionaries or JSON string with 'temp', 'psal', and 'pres' data.
    """
    if not data:
        st.warning("No data provided for profile plots.")
        return "No data was provided to plot profiles."
    
    # Validate data
    validated_data = validate_and_convert_data(data)
    if not validated_data:
        return "No valid data points found for plotting profiles."
    
    df = pd.DataFrame([point.dict() for point in validated_data])
    
    # Filter out invalid measurements
    df = df.dropna(subset=['temp', 'psal', 'pres'])
    
    if df.empty:
        st.warning("No valid temperature, salinity, and pressure data found.")
        return "No valid profile data available."
    
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
        
        # Download link
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
        
        # Download link
        st.markdown(create_download_link(sal_fig, "salinity_profile"), unsafe_allow_html=True)
    
    # Statistics
    stats = {
        'Total Measurements': len(df),
        'Depth Range': f"{df['pres'].min():.1f} - {df['pres'].max():.1f} dbar",
        'Temperature Range': f"{df['temp'].min():.2f} - {df['temp'].max():.2f} °C",
        'Salinity Range': f"{df['psal'].min():.2f} - {df['psal'].max():.2f} PSU"
    }
    
    st.info(" | ".join([f"{k}: {v}" for k, v in stats.items()]))
    
    return f"Successfully plotted depth profiles for {len(df)} data points. Temperature range: {df['temp'].min():.2f} - {df['temp'].max():.2f} °C, Salinity range: {df['psal'].min():.2f} - {df['psal'].max():.2f} PSU."

@tool
def plot_ts_diagram(data: Union[List[Dict[str, Any]], str], region_info: str = ""):
    """
    Create a Temperature-Salinity (T-S) diagram.
    Input: List of dictionaries or JSON string with 'temp', 'psal', and 'pres' data.
    """
    if not data:
        st.warning("No data provided for T-S diagram.")
        return "No data was provided to create T-S diagram."
    
    validated_data = validate_and_convert_data(data)
    if not validated_data:
        return "No valid data points found for T-S diagram."
    
    df = pd.DataFrame([point.dict() for point in validated_data])
    df = df.dropna(subset=['temp', 'psal'])
    
    if df.empty:
        st.warning("No valid temperature and salinity data found.")
        return "No valid T-S data available."
    
    st.subheader(f"🌊 Temperature-Salinity Diagram {region_info}")
    
    # Create T-S diagram
    ts_fig = px.scatter(
        df, x='psal', y='temp',
        title='Temperature-Salinity (T-S) Diagram',
        labels={'psal': 'Salinity (PSU)', 'temp': 'Temperature (°C)'},
        color='pres' if 'pres' in df.columns else None,
        color_continuous_scale='Viridis_r',
        hover_data=['pres'] if 'pres' in df.columns else None
    )
    
    ts_fig.update_layout(height=600)
    st.plotly_chart(ts_fig, use_container_width=True)
    
    # Download link
    st.markdown(create_download_link(ts_fig, "ts_diagram"), unsafe_allow_html=True)
    
    return f"Successfully created T-S diagram for {len(df)} data points."

@tool
def plot_float_trajectory(data: Union[List[Dict[str, Any]], str], region_info: str = ""):
    """
    Plot the trajectory (path) of floats on a map.
    Input: List of dictionaries or JSON string with 'latitude', 'longitude', 'timestamp', and 'platform_number' data.
    """
    if not data:
        st.warning("No data provided for trajectory plot.")
        return "No data was provided to plot trajectory."
    
    validated_data = validate_and_convert_data(data)
    if not validated_data:
        return "No valid data points found for trajectory plot."
    
    df = pd.DataFrame([point.dict() for point in validated_data])
    df = df.dropna(subset=['latitude', 'longitude'])
    
    if df.empty:
        st.warning("No valid latitude and longitude data found.")
        return "No valid trajectory data available."
    
    st.subheader(f"🗺️ Float Trajectory {region_info}")
    
    # Sort by timestamp if available
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.sort_values(['platform_number', 'timestamp']).reset_index(drop=True)
    
    # Create trajectory map
    map_center = [df['latitude'].mean(), df['longitude'].mean()]
    m = folium.Map(location=map_center, zoom_start=5)
    
    # Group by platform_number if available
    if 'platform_number' in df.columns:
        colors = ['blue', 'red', 'green', 'purple', 'orange', 'darkred', 'lightred', 
                 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen']
        
        for i, platform_number in enumerate(df['platform_number'].unique()):
            float_data = df[df['platform_number'] == platform_number]
            color = colors[i % len(colors)]
            
            if len(float_data) > 1:
                points = list(zip(float_data['latitude'], float_data['longitude']))
                folium.PolyLine(points, color=color, weight=2.5, opacity=0.8, 
                               popup=f"Float {platform_number}").add_to(m)
                
                # Add start and end markers
                folium.Marker(points[0], popup=f"Float {platform_number} - Start", 
                             icon=folium.Icon(color='green', icon='play')).add_to(m)
                folium.Marker(points[-1], popup=f"Float {platform_number} - End", 
                             icon=folium.Icon(color='red', icon='stop')).add_to(m)
            else:
                folium.Marker([float_data.iloc[0]['latitude'], float_data.iloc[0]['longitude']], 
                             popup=f"Float {platform_number}", 
                             icon=folium.Icon(color=color)).add_to(m)
    else:
        # Single trajectory
        points = list(zip(df['latitude'], df['longitude']))
        if len(points) > 1:
            folium.PolyLine(points, color="blue", weight=3, opacity=1).add_to(m)
            folium.Marker(points[0], popup="Start", icon=folium.Icon(color='green')).add_to(m)
            folium.Marker(points[-1], popup="End", icon=folium.Icon(color='red')).add_to(m)
    
    st_folium(m, height=500, width=700)
    
    # Add trajectory statistics
    unique_floats = df['platform_number'].nunique() if 'platform_number' in df.columns else 1
    total_points = len(df)
    
    stats_info = f"📊 **Trajectory Statistics**: {unique_floats} float(s), {total_points} positions"
    if 'timestamp' in df.columns and df['timestamp'].notna().sum() > 0:
        date_range = f"from {df['timestamp'].min().strftime('%Y-%m-%d')} to {df['timestamp'].max().strftime('%Y-%m-%d')}"
        stats_info += f", {date_range}"
    
    st.info(stats_info)
    
    return f"Successfully plotted trajectory for {unique_floats} float(s) with {total_points} positions."

@tool
def plot_sea_surface_temperature_timeseries(data: Union[List[Dict[str, Any]], str], region_info: str = ""):
    """
    Plot a time-series of sea surface temperature (SST).
    Input: List of dictionaries or JSON string with 'temp', 'timestamp', and 'pres' data.
    """
    if not data:
        st.warning("No data provided for SST plot.")
        return "No data was provided to plot SST time-series."
    
    validated_data = validate_and_convert_data(data)
    if not validated_data:
        return "No valid data points found for SST plot."
    
    df = pd.DataFrame([point.dict() for point in validated_data])
    
    # Filter for surface data (pressure < 10 dbar) and valid temperature/timestamp
    surface_data = df[(df['pres'] <= 10) & df['temp'].notna() & df['timestamp'].notna()]
    
    if surface_data.empty:
        st.warning("No valid surface temperature data found (pressure ≤ 10 dbar).")
        return "No valid SST data available."
    
    st.subheader(f"🌡️ Sea Surface Temperature Time-Series {region_info}")
    
    # Convert timestamp and sort
    surface_data['timestamp'] = pd.to_datetime(surface_data['timestamp'], errors='coerce')
    surface_data = surface_data.dropna(subset=['timestamp']).sort_values('timestamp')
    
    if surface_data.empty:
        st.warning("No valid timestamp data found.")
        return "No valid timestamp data available."
    
    # Create SST time-series plot
    fig = px.line(
        surface_data, x='timestamp', y='temp',
        title='Sea Surface Temperature Over Time',
        labels={'timestamp': 'Date', 'temp': 'Temperature (°C)'},
        markers=True
    )
    
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Download link
    st.markdown(create_download_link(fig, "sst_timeseries"), unsafe_allow_html=True)
    
    # Statistics
    stats = {
        'Data Points': len(surface_data),
        'Temperature Range': f"{surface_data['temp'].min():.2f} - {surface_data['temp'].max():.2f} °C",
        'Average SST': f"{surface_data['temp'].mean():.2f} °C",
        'Time Period': f"{surface_data['timestamp'].min().strftime('%Y-%m-%d')} to {surface_data['timestamp'].max().strftime('%Y-%m-%d')}"
    }
    
    st.info(" | ".join([f"{k}: {v}" for k, v in stats.items()]))
    
    return f"Successfully plotted SST time-series for {len(surface_data)} surface measurements. Average SST: {surface_data['temp'].mean():.2f}°C."

@tool
def calculate_regional_statistics(data: Union[List[Dict[str, Any]], str], region_bounds: str = ""):
    """
    Calculate comprehensive statistics for a region.
    Input: List of dictionaries or JSON string with oceanographic data.
    """
    if not data:
        st.warning("No data provided for regional statistics.")
        return "No data was provided for regional statistics."
    
    validated_data = validate_and_convert_data(data)
    if not validated_data:
        return "No valid data points found for regional statistics."
    
    df = pd.DataFrame([point.dict() for point in validated_data])
    
    st.subheader(f"📈 Regional Statistics {region_bounds}")
    
    # Temperature statistics
    temp_stats = df['temp'].describe() if 'temp' in df.columns else None
    sal_stats = df['psal'].describe() if 'psal' in df.columns else None
    
    col1, col2 = st.columns(2)
    
    with col1:
        if temp_stats is not None:
            st.write("**Temperature Statistics (°C)**")
            st.write(f"• Mean: {temp_stats['mean']:.2f}")
            st.write(f"• Min: {temp_stats['min']:.2f}")
            st.write(f"• Max: {temp_stats['max']:.2f}")
            st.write(f"• Std Dev: {temp_stats['std']:.2f}")
    
    with col2:
        if sal_stats is not None:
            st.write("**Salinity Statistics (PSU)**")
            st.write(f"• Mean: {sal_stats['mean']:.2f}")
            st.write(f"• Min: {sal_stats['min']:.2f}")
            st.write(f"• Max: {sal_stats['max']:.2f}")
            st.write(f"• Std Dev: {sal_stats['std']:.2f}")
    
    # Data coverage
    unique_floats = df['platform_number'].nunique() if 'platform_number' in df.columns else 'N/A'
    unique_positions = df[['latitude', 'longitude']].drop_duplicates().shape[0]
    
    st.write("**Data Coverage**")
    st.write(f"• Total measurements: {len(df)}")
    st.write(f"• Unique floats: {unique_floats}")
    st.write(f"• Unique positions: {unique_positions}")
    
    summary = f"Regional analysis complete. Found {len(df)} measurements"
    if temp_stats is not None:
        summary += f" with average temperature {temp_stats['mean']:.2f}°C"
    if sal_stats is not None:
        summary += f" and average salinity {sal_stats['mean']:.2f} PSU"
    
    return summary
