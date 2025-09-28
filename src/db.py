import os
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Use st.cache_resource to prevent re-creating the connection on every rerun
@st.cache_resource
def get_db_engine():
    """
    Creates and returns a SQLAlchemy engine for the PostgreSQL database.
    """
    load_dotenv()
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    
    if not all([DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME]):
        raise ValueError("One or more database environment variables are not set.")
        
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DATABASE_URL)
    return engine

# Placeholder for ChromaDB logic
def get_vector_store():
    # TODO: Initialize and return your ChromaDB client/collection here.
    pass