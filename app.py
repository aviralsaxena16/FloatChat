import streamlit as st
import pandas as pd
from src.db import get_db_engine
from src.agent import create_agent, query_agent

st.set_page_config(page_title="FloatChat", page_icon="🌊", layout="wide")

st.title("🌊 AquaQuery AI")
st.caption("Your Conversational Gateway to ARGO Ocean Data")

try:
    engine = get_db_engine()
    agent_executor = create_agent(engine)
except Exception as e:
    st.error(f"Failed to initialize. Check DB connection & API keys: {e}")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about ARGO floats in the Indian Ocean..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        assistant_response = query_agent(agent_executor, prompt)
        
        with st.chat_message("assistant"):
            st.markdown(assistant_response)
            # TODO: Add visualization logic here by parsing the agent's response
            # or the SQL it generated to fetch data and plot it.
            st.info("Visualizations would appear here.")

    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

with st.sidebar:
    st.header("About")
    st.markdown("This PoC for SIH 2025 uses an LLM to translate natural language into SQL queries against a real-time ARGO float database.")
    st.header("Tech Stack")
    st.markdown("- Streamlit\n- LangChain\n- OpenAI/Google Gemini\n- PostgreSQL/PostGIS")