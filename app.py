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
# This is the correct import for Google's models
from langchain_google_genai import ChatGoogleGenerativeAI

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
    # IMPORTANT: We point the agent to our clean 'argo_view'
    db = SQLDatabase(_db_engine, include_tables=['argo_view'], view_support=True)
    
    # --- FINAL FIX: Using the stable and universally available gemini-pro model ---
    llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro", 
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0
)
    # Using a compatible agent type
    agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)
    return agent_executor

# --- Main Application ---
st.title("🌊 FloatChat AI: Conversational Ocean Data Explorer")
st.markdown("Ask questions in the chat or draw a rectangle on the map to query ARGO float data.")

# --- Initialize Connections ---
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
    Draw(export=False).add_to(m)
    map_data = st_folium(m, height=500, width=700)

    if map_data and map_data.get("last_active_drawing"):
        drawing = map_data["last_active_drawing"]
        if drawing["geometry"]["type"] == "Polygon":
            coords = drawing["geometry"]["coordinates"][0]
            
            min_lon = min(p[0] for p in coords)
            max_lon = max(p[0] for p in coords)
            min_lat = min(p[1] for p in coords)
            max_lat = max(p[1] for p in coords)

            st.info(f"Searching within bounding box: ({min_lat:.2f}, {min_lon:.2f}) to ({max_lat:.2f}, {max_lon:.2f})")

            query = text(f"""
                SELECT platform_number, latitude, longitude, temp_adjusted, psal_adjusted, pres_adjusted
                FROM public.argo_measurements
                WHERE geom && ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)
                LIMIT 500;
            """)
            
            with st.spinner("Querying database..."):
                try:
                    with engine.connect() as connection:
                        result_df = pd.read_sql(query, connection)
                    
                    st.success(f"Found {len(result_df)} data points in the selected area!")
                    st.dataframe(result_df)
                    st.line_chart(result_df, x='psal_adjusted', y='temp_adjusted', color="#0083B8")

                except Exception as e:
                    st.error(f"An error occurred during map query: {e}")

with col2:
    st.subheader("💬 Chatbot Query")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Show salinity near the equator..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Thinking..."):
            full_prompt = f"""
            You are an expert oceanographic data analyst. Your goal is to answer the user's question by querying the 'argo_view'.
            The view has these columns: float_id, latitude, longitude, timestamp, cycle_number, direction, pressure, temperature, salinity, project_name, pi_name.
            User's question: "{prompt}"
            
            First, think about the SQL query you need to write.
            Then, execute the query.
            Finally, provide a clear, concise natural language answer based on the query results.
            If you are asked for profiles, you can suggest aggregating the data (e.g., finding the average temperature).
            """
            
            try:
                response = agent_executor.invoke({"input": full_prompt})
                assistant_response = response['output']
                
                st.chat_message("assistant").markdown(assistant_response)
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            except Exception as e:
                st.error(f"An error occurred with the AI agent: {e}")

