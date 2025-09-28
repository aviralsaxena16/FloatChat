import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from pathlib import Path

# --- LangChain Imports ---
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_groq import ChatGroq

# --- Map Imports ---
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- Page Configuration ---
st.set_page_config(
    page_title="FloatChat AI",
    page_icon="🌊",
    layout="wide"
)

# --- Initialize Session State for Shared Context ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "map_bounds" not in st.session_state:
    st.session_state.map_bounds = None

# --- Caching Database Connection ---
@st.cache_resource
def get_db_engine():
    """Creates and returns a SQLAlchemy engine for the PostgreSQL database."""
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")

    if not all([DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME]):
        st.error("Database credentials are not set. Please check your .env file.")
        st.stop()
    
    encoded_pass = quote_plus(DB_PASS)
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DATABASE_URL)
    return engine

# --- Initialize Agent ---
@st.cache_resource
def initialize_agent(_db_engine):
    """Initializes the LangChain SQL Agent."""
    db = SQLDatabase(_db_engine, include_tables=['argo_view'], view_support=True)
    
    llm = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2
)
    
    agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)
    return agent_executor

# --- Main Application ---
st.title("🌊 FloatChat AI: Conversational Ocean Data Explorer")
st.markdown("Ask questions in the chat or draw a rectangle on the map to query ARGO float data.")

try:
    engine = get_db_engine()
    agent_executor = initialize_agent(engine)
except Exception as e:
    st.error(f"Failed to initialize application. Please check connections and API keys.")
    st.error(f"Error details: {e}")
    st.stop()

# --- Layout: Map and Chat Side-by-Side ---
col1, col2 = st.columns([0.6, 0.4])

with col1:
    st.subheader("🗺️ Map-Based Query")
    
    m = folium.Map(location=[10, 80], zoom_start=4)
    Draw(export=False, filename='data.geojson', draw_options={'rectangle': {'shapeOptions': {'color': '#00BFFF'}}}).add_to(m)
    map_data = st_folium(m, height=500, width=700)

    if map_data and map_data.get("last_active_drawing") and map_data["last_active_drawing"]["geometry"]["type"] == "Polygon":
        coords = map_data["last_active_drawing"]["geometry"]["coordinates"][0]
        
        min_lon, max_lon = min(p[0] for p in coords), max(p[0] for p in coords)
        min_lat, max_lat = min(p[1] for p in coords), max(p[1] for p in coords)

        # --- CONTEXT SHARING: Save the bounds to session state ---
        st.session_state.map_bounds = {
            "min_lon": min_lon, "max_lon": max_lon,
            "min_lat": min_lat, "max_lat": max_lat
        }
        st.success(f"Map context set to bounding box: ({min_lat:.2f}, {min_lon:.2f}) to ({max_lat:.2f}, {max_lon:.2f})")

        query = text(f"""
            SELECT platform_number as float_id, latitude, longitude, temp_adjusted as temperature, psal_adjusted as salinity
            FROM public.argo_measurements
            WHERE geom && ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)
            LIMIT 500;
        """)
        
        with st.spinner("Querying database for map..."):
            try:
                with engine.connect() as connection:
                    result_df = pd.read_sql(query, connection)
                if not result_df.empty:
                    st.success(f"Found {len(result_df)} data points!")
                    st.dataframe(result_df)
                else:
                    st.warning("No data found in the selected area.")
            except Exception as e:
                st.error(f"An error occurred during map query: {e}")

with col2:
    st.subheader("💬 Chatbot Query")
    if st.session_state.map_bounds:
        b = st.session_state.map_bounds
        st.info(f"Using map context: ({b['min_lat']:.2f}, {b['min_lon']:.2f}) to ({b['max_lat']:.2f}, {b['max_lon']:.2f})")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is the average salinity here?"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Thinking..."):
            
            # --- CONTEXT SHARING: Check if map bounds exist and add them to the prompt ---
            context_prompt = ""
            # A simple check to see if the user is overriding the map context with a new location
            has_location = any(loc in prompt.lower() for loc in ["arabian sea", "bay of bengal", "equator", "indian ocean"])

            if st.session_state.map_bounds and not has_location:
                b = st.session_state.map_bounds
                context_prompt = f"The user has pre-selected a region on a map. You MUST constrain your SQL query to this bounding box: latitude BETWEEN {b['min_lat']} AND {b['max_lat']} AND longitude BETWEEN {b['min_lon']} AND {b['max_lon']}."
            
            full_prompt = f"""
            You are a helpful and expert oceanographic data analyst. Your goal is to answer the user's question by creating and executing a SQL query against the 'argo_view'.

            The view 'argo_view' has these columns: float_id, latitude, longitude, timestamp, cycle_number, direction, pressure, temperature, salinity, project_name, pi_name.
            
            Here is the user's question: "{prompt}"

            {context_prompt}

            Your process is as follows:
            1. Think about what the user is asking. If they mention a geographical name like 'Bay of Bengal', convert it to an approximate latitude/longitude bounding box in your SQL WHERE clause.
            2. Construct a valid PostgreSQL query to get the answer.
            3. Execute the query.
            4. **Crucially, you MUST analyze the result of the query and write a final, natural language answer.** Do not just output a tool call. Provide a complete sentence.
            """
            
            try:
                response = agent_executor.invoke({"input": full_prompt})
                assistant_response = response['output']
                
                st.chat_message("assistant").markdown(assistant_response)
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            except Exception as e:
                st.error(f"An error occurred with the AI agent: {e}")
