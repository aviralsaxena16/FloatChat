import streamlit as st
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities.sql_database import SQLDatabase
# from langchain_openai import ChatOpenAI # Or from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import ChatGoogleGenerativeAI
import os
# Use st.cache_resource to initialize the agent once
@st.cache_resource
def create_agent(_db_engine):
    """
    Initializes the LangChain SQL Agent.
    """
    db = SQLDatabase(_db_engine, include_tables=['argo_measurements'])
    
    # Initialize your LLM. Make sure your API key is set in the environment.
    llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro", 
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0
)
    # Create the SQL Agent
    agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)
    
    return agent_executor

def query_agent(agent_executor, user_query):
    """
    Queries the agent and returns the response.
    """
    prompt = f"""
    Based on the user's question: "{user_query}", first, think about what you need to do.
    Then, generate and execute a SQL query on the 'argo_measurements' table.
    Finally, summarize the findings in a clear, natural language response.
    The table has the following columns: lat, lon, timestamp, temperature, salinity, pressure, float_id.
    If you are asked to show locations, respond with both the summary and a list of lat/lon coordinates.
    """
    try:
        response = agent_executor.invoke({"input": prompt})
        return response['output']
    except Exception as e:
        return f"An error occurred: {e}"