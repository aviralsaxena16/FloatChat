# 🌊 FloatChat AI

**An AI-powered conversational platform to explore and visualize complex ARGO oceanographic data using natural language and interactive maps.**

---

## 📌 Problem Statement
Oceanographic data, particularly from the ARGO float program, is vast, complex, and stored in formats like **NetCDF** that are inaccessible to non-technical users. Extracting meaningful insights requires domain knowledge and specialized tools, creating a gap between raw data and decision-makers.

---
![alt text](<assets/Screenshot 2025-09-29 015752.png>)

## 💡 Our Solution
FloatChat AI bridges this gap by providing a powerful yet intuitive **dual-interface system**.  

- Users can **visually query data** by drawing on a map.  
- Or, have a **deep, analytical conversation** with an AI agent that understands natural language.  

This democratizes access to ocean data, making it explorable for **scientists, policymakers, and students** alike.

---

## 🎥 Live Demo
*(A GIF showing a user drawing on the map and then asking the chatbot a question would be perfect here.)*

---

## ✨ Key Features
- **Conversational AI Chatbot**: Ask complex questions in plain English.  
  Powered by **Groq's LLaMA 3** and **LangChain**, the AI understands intent, writes its own SQL queries, and provides clear, natural-language answers.  

- **Interactive Map-Based Query**: Draw a rectangle on the world map to fetch and visualize data points within that region using **PostGIS**.  

- **Shared Context Awareness**: The chatbot remembers context. If you draw a region and ask *“What’s the average temperature here?”*, it intelligently answers based on the selected area.  

- **Dynamic Data Visualization**: Both map and chatbot queries generate instant, interactive charts and tables for quick analysis.  

- **Simplified Data Access**: A **SQL VIEW** simplifies raw data, ensuring accurate and reliable queries.  

---

## 🛠️ Tech Stack
**Frontend**:  
- Streamlit (interactive data app)  

**Backend & AI**:  
- Python  
- LangChain (SQL Agent framework)  
- Groq API (LLaMA 3 inference)  

**Database**:  
- PostgreSQL + PostGIS (via Supabase)  

**Data Processing**:  
- Pandas  

**Mapping**:  
- Folium + streamlit-folium  

---
