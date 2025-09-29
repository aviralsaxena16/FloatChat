import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any
import json
from sqlalchemy.sql import text
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# LangChain imports
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit

# Local imports
from src.database import ArgoDatabase
from src.models import RegionBounds
# Import both core plotting tools and new DB-backed convenience tools
from src.tools import (
    plot_profiles,
    plot_sea_surface_temperature_timeseries,
    plot_profiles_from_db,
    plot_sst_from_db,
)

# Page config
st.set_page_config(
    page_title="FloatChat AI", 
    page_icon="🌊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stats-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1e3c72;
    }
    .region-info {
        background: #e1f5fe;
        padding: 0.5rem;
        border-radius: 5px;
        border: 1px solid #01579b;
    }
    .answer-box {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "map_bounds" not in st.session_state:
    st.session_state.map_bounds = None
if "selected_region" not in st.session_state:
    st.session_state.selected_region = None
if "db" not in st.session_state:
    st.session_state.db = ArgoDatabase()

@st.cache_resource
def initialize_agent(_db_engine, _table_name):
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
    db = SQLDatabase(_db_engine, include_tables=[_table_name], view_support=True)
    llm = ChatGroq(
        model="deepseek-r1-distill-llama-70b",
        temperature=0,
        max_retries=2,
    )
    sql_toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    # Prefer DB-backed plotting tools so the agent doesn't have to juggle raw data across tools
    custom_tools = [
        plot_profiles_from_db,
        plot_sst_from_db,
        # Also make pure plotting tools available if the agent already has data
        plot_profiles,
        plot_sea_surface_temperature_timeseries,
    ]
    tools = custom_tools + sql_toolkit.get_tools()

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
You are FloatChat AI, an oceanographic analyst for Indian Ocean regions.

DATABASE: {_table_name}
COLUMNS: latitude, longitude, temp, psal, pres, timestamp (from juld), platform_number

CRITICAL RULES:
- Output ONLY final answers and display plots directly in Streamlit. NEVER show SQL, tool calls, or internal thoughts.
- For plotting requests, prefer DB-backed tools:
  • For depth profiles: use tool "plot_profiles_from_db"
  • For SST time-series: use tool "plot_sst_from_db"
  Pass either a known region name (e.g., "Bay of Bengal") OR the exact WHERE-bounds string appended to the user prompt (see below).

MAP SELECTION:
If the user has a selected region on the map, their prompt includes:
"USER SELECTED MAP REGION: latitude BETWEEN <min_lat> AND <max_lat> AND longitude BETWEEN <min_lon> AND <max_lon>. Use these exact bounds in your WHERE clause."
When you see this, pass that exact line (bounds) to the DB-backed plotting tool.

REGION BOUNDS (by name):
- Arabian Sea: latitude BETWEEN 8 AND 25 AND longitude BETWEEN 50 AND 75
- Bay of Bengal: latitude BETWEEN 8 AND 22 AND longitude BETWEEN 80 AND 95
- Equatorial Indian: latitude BETWEEN -5 AND 5 AND longitude BETWEEN 50 AND 100
- Indian Ocean: latitude BETWEEN -40 AND 25 AND longitude BETWEEN 20 AND 120

STATISTICS:
- When asked for statistics only, respond with numbers and units (no SQL/tool details).

Keep responses short; plots will carry the detail.
"""),
        ("user", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=10,
        return_intermediate_steps=False
    )

# Header
st.markdown("""
<div class="main-header">
    <h1>🌊 FloatChat AI: Conversational Ocean Data Explorer</h1>
    <p>Explore ARGO oceanographic data through intelligent queries and visualizations</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.header("🎛️ Control Panel")
    
    # Region selector
    st.subheader("🗺️ Quick Regions")
    predefined_regions = [
        "Bay of Bengal", "Arabian Sea", "Indian Ocean", "Equatorial Indian"
    ]
    
    selected_region = st.selectbox(
        "Select a predefined region:",
        ["None"] + predefined_regions,
        help="Choose a region for quick analysis"
    )
    
    if selected_region != "None":
        if st.button(f"Analyze {selected_region}"):
            st.session_state.selected_region = selected_region
            query = f"What is the average temperature and salinity in {selected_region}? Also show me the profiles."
            st.session_state.messages.append({"role": "user", "content": query})
            st.rerun()
    
    # Statistics
    st.subheader("📊 Quick Stats")
    if st.button("Get Database Overview"):
        try:
            t = st.session_state.db.table_name
            query = f"SELECT COUNT(*) AS total_records, COUNT(DISTINCT platform_number) AS unique_floats FROM {t}"
            df = st.session_state.db.execute_query(query)
            if not df.empty:
                st.metric("Total Records", f"{df.iloc[0]['total_records']:,}")
                st.metric("Unique Floats", f"{df.iloc[0]['unique_floats']:,}")
        except Exception as e:
            st.error(f"Error fetching stats: {e}")
        
    # Help section
    st.subheader("💡 Example Queries")
    example_queries = [
        "What is the average salinity in Bay of Bengal?",
        "Show me temperature profiles for the Arabian Sea",
        "Plot trajectories of floats in the Indian Ocean",
        "Create a T-S diagram for Equatorial Indian region",
        "Plot sea surface temperature time series for Bay of Bengal"
    ]
    
    for query in example_queries:
        if st.button(query, key=f"example_{hash(query)}"):
            st.session_state.messages.append({"role": "user", "content": query})
            st.rerun()

# --- Main Layout ---
col1, col2 = st.columns([0.6, 0.4])

# --- Map Column ---
with col1:
    st.subheader("🗺️ Interactive Map Query")
    
    # Create folium map
    m = folium.Map(location=[15, 75], zoom_start=4)
    
    # Add drawing tools
    Draw(
        export=False,
        draw_options={
            'rectangle': {'shapeOptions': {'color': '#00BFFF'}},
            'polygon': {'shapeOptions': {'color': '#FF6B6B'}},
            'circle': False,
            'marker': False,
            'circlemarker': False,
            'polyline': False
        }
    ).add_to(m)
    
    # Display map
    map_data = st_folium(m, height=500, width=700)
    
    # Process map selection
    if map_data and map_data.get("last_active_drawing"):
        coords = map_data["last_active_drawing"]["geometry"]["coordinates"]
        
        if map_data["last_active_drawing"]["geometry"]["type"] == "Polygon":
            coords = coords[0]  # Extract coordinate array from polygon
        
        # Calculate bounds
        lons = [p[0] for p in coords]
        lats = [p[1] for p in coords]
        
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        
        # Update session state
        st.session_state.map_bounds = {
            "min_lon": min_lon, "max_lon": max_lon, 
            "min_lat": min_lat, "max_lat": max_lat
        }
        
        # Create region bounds
        region = RegionBounds(
            min_lat=min_lat, max_lat=max_lat,
            min_lon=min_lon, max_lon=max_lon,
            region_name="Selected Map Region"
        )
        
        with st.spinner("Analyzing selected region..."):
            data = st.session_state.db.get_region_data(region, limit=1000)
            if data and len(data) > 0:
                stats = st.session_state.db.get_regional_averages(region)
                st.success(f"Found {len(data)} data points in selected region")
                if stats and stats.get('data_points', 0) > 0:
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        if stats.get('avg_temp') is not None:
                            st.metric("Avg Temperature", f"{stats['avg_temp']:.2f}°C")
                    with col_b:
                        if stats.get('avg_psal') is not None:
                            st.metric("Avg Salinity", f"{stats['avg_psal']:.2f} PSU")
                    with col_c:
                        st.metric("Data Points", f"{stats.get('data_points', 0):,}")
            else:
                st.warning("No ARGO data found in the selected region. Try a larger area.")
    
    # Download map
    if st.button("📥 Download Map as HTML"):
        map_html = m._repr_html_()
        st.download_button(
            label="Download Map",
            data=map_html,
            file_name="argo_map.html",
            mime="text/html"
        )

# --- Chat Column ---
with col2:
    st.subheader("💬 Chat Interface")

    if st.session_state.map_bounds:
        b = st.session_state.map_bounds
        st.markdown(f"""
        <div class="region-info">
        <strong>🎯 Active Map Region:</strong><br>
        Lat: {b['min_lat']:.2f} to {b['max_lat']:.2f}<br>
        Lon: {b['min_lon']:.2f} to {b['max_lon']:.2f}
        </div>
        """, unsafe_allow_html=True)

        if st.button("Clear Map Selection"):
            st.session_state.map_bounds = None
            st.experimental_rerun()

    try:
        agent_executor = initialize_agent(
            st.session_state.db.engine,
            st.session_state.db.table_name
        )
    except Exception as e:
        st.error(f"Failed to initialize agent: {e}")
        st.stop()

    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                content = message["content"]
                if isinstance(content, pd.DataFrame):
                    st.dataframe(content, use_container_width=True)
                else:
                    st.markdown(content)

if prompt := st.chat_input("Ask about ARGO data..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("🤔 Analyzing oceanographic data..."):
            try:
                context_prompt = prompt
                region_keywords = ["bay of bengal", "arabian sea", "indian ocean", "equatorial indian"]
                has_specific_region = any(keyword in prompt.lower() for keyword in region_keywords)

                # Append map bounds in a format the agent is instructed to pass through to the DB-backed tools
                if st.session_state.map_bounds and not has_specific_region:
                    b = st.session_state.map_bounds
                    context_addition = (
                        f"\n\nUSER SELECTED MAP REGION: latitude BETWEEN {b['min_lat']} AND {b['max_lat']} "
                        f"AND longitude BETWEEN {b['min_lon']} AND {b['max_lon']}. "
                        f"Use these exact bounds in your WHERE clause."
                    )
                    context_prompt += context_addition

                response = agent_executor.invoke({"input": context_prompt})
                output = response.get('output', '')

                # Scrub any tool/thought artifacts
                import re
                output = re.sub(r'<tool_call>.*?</tool_call>', '', output, flags=re.DOTALL)
                output = re.sub(r'``````', '', output, flags=re.DOTALL)
                output = re.sub(r'Action:.*?(?=\n\n|\Z)', '', output, flags=re.DOTALL)
                output = re.sub(r'Thought:.*?(?=\n\n|\Z)', '', output, flags=re.DOTALL)
                output = re.sub(r'Observation:.*?(?=\n\n|\Z)', '', output, flags=re.DOTALL)
                output = re.sub(r'\n{3,}', '\n\n', output).strip()


                if output:
                    st.markdown(output)
                    st.session_state.messages.append({"role": "assistant", "content": output})
                else:
                    st.info("✅ Analysis complete. Check visualizations above.")
                    st.session_state.messages.append({"role": "assistant", "content": "Analysis complete."})


            except Exception as e:
                error_message = f"❌ Error: {str(e)}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})


# --- Footer ---
st.markdown("---")
st.markdown("""<div style='text-align: center; color: #666; font-size: 0.9em;'>🌊 FloatChat AI | Powered by ARGO Global Ocean Observing System | Built with Streamlit, LangChain & Plotly</div>""", unsafe_allow_html=True)