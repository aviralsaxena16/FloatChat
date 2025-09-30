import streamlit as st
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from sqlalchemy import inspect

# Use st.cache_resource to initialize the agent once
@st.cache_resource
def create_agent(_db_engine):
    """
    Initializes the LangChain SQL Agent.
    """
    inspector = inspect(_db_engine)
    table = 'argo_measurements' if 'argo_measurements' in inspector.get_table_names() else 'argo_view'
    db = SQLDatabase(_db_engine, include_tables=[table], view_support=True)
    
    # Initialize your LLM. Make sure your API key is set in the environment.
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro", 
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0
    )

    system_help = f"""
    You will query table {table}. Use SELECT with aliases to normalize columns to:
    latitude, longitude, temp, psal, pres, timestamp, platform_number, cycle_number.
    Common real names to alias:
    - temperature->temp, salinity->psal, pressure->pres
    - lat/latitude -> latitude, lon/longitude -> longitude
    - float_id/platform_number -> platform_number
    Always apply provided map bounds when present. Return final answers only.
    """

    # Create the SQL Agent
    agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=False, system_message=system_help)
    
    return agent_executor

def query_agent(agent_executor, user_query):
    """
    Queries the agent and returns the response.
    """
    prompt = f"""
    Based on the user's question: "{user_query}", first, think about what you need to do.
    Then, generate and execute a SQL query on the 'argo_measurements' or 'argo_view' table.
    Finally, summarize the findings in a clear, natural language response.
    The table has columns that may vary, but common aliases are provided.
    If you are asked to show locations, respond with both the summary and a list of lat/lon coordinates.
    """
    try:
        response = agent_executor.invoke({"input": prompt})
        return response['output']
    except Exception as e:
        return f"An error occurred: {e}"
