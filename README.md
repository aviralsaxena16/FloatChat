# 🌊 FloatChat AI

**An AI-powered conversational platform to explore and visualize complex ARGO oceanographic data using natural language, embeddings, and interactive maps.**

---

## 📌 Problem Statement
Oceanographic data, particularly from the ARGO float program, is **vast, complex, and stored in formats like NetCDF** that are inaccessible to non-technical users. Extracting meaningful insights requires domain knowledge and specialized tools, creating a gap between raw data and decision-makers.

---
### 1️⃣ User marking a region on the map and asking a query
<img width="70%" alt="Map-based query" src="https://github.com/user-attachments/assets/d10c5d43-539a-4561-b8bf-8704e20b3c37" />

<br><br>
### 2️⃣ Conversational AI answering general queries
<img width="70%" alt="General queries" src="https://github.com/user-attachments/assets/33845436-7eb3-447d-9be1-7b5b353a6cee" />


<br><br>
### 3️⃣ Plotting temperature and salinity profiles for the selected region
<img width="70%" alt="Profile plotting" src="https://github.com/user-attachments/assets/5012ed5d-cfd0-4da1-94cc-269d8004ab49" />

---

## 💡 Our Solution
FloatChat AI bridges this gap with a **dual-interface system**:  

- Users can **draw on a map to query data visually**.  
- Or, **chat with an AI agent** that understands natural language and oceanography.  

This democratizes access to ocean data, making it explorable for **scientists, policymakers, educators, and students** alike.

---

## ✨ Key Features

- **Conversational AI Chatbot**  
  - Ask complex queries in plain English.  
  - Uses **LangChain + Groq LLaMA 3** to translate questions into SQL/vector searches.  
  - Returns clear answers, charts, or tables.  

- **Vector Search with ChromaDB**  
  - User queries are embedded and matched against **ChromaDB**.  
  - Enables **semantic search** beyond exact SQL queries.  

- **Interactive Map-Based Query**  
  - Select a region on the world map.  
  - Fetch and analyze ARGO profiles (temperature, salinity, etc.) for that region.  

- **Profile Plotting**  
  - Generate **Temperature vs Depth** and **Salinity vs Depth** graphs.  
  - Works for both **map-selected regions** and **manually defined regions**.  

- **Automated Data Pipeline**  
  - A **scheduler** runs regularly to:  
    - Fetch latest ARGO `.nc` (NetCDF) data.  
    - Convert it to **CSV**.  
    - Upload into **PostgreSQL** and **ChromaDB**.  
  - Ensures **real-time ocean data availability**.  

- **Shared Context Awareness**  
  - If you select a region and ask: *“What’s the average salinity here?”*, the bot answers with context.  

---

## 🛠️ Tech Stack

**Frontend**  
- Streamlit (interactive app)  

**Backend & AI**  
- Python  
- LangChain (SQL Agent + Vector Search)  
- Groq API (LLaMA 3 inference)  

**Databases**  
- PostgreSQL + PostGIS (structured data + spatial queries)  
- ChromaDB (embeddings for semantic/vector search)  

**Data Pipeline**  
- NetCDF → CSV conversion (xarray / netCDF4)  
- Scheduler for automatic ingestion  

**Visualization & Mapping**  
- Pandas & Matplotlib (profiles & charts)  
- Folium + streamlit-folium (map interface)  

---

## 🚀 Future Scope
- Add **multi-float trajectory analysis**  
- Support **climate trend detection** (time-series analysis)  
- Enable **collaborative dashboards** for teams  

---

## 🤝 Contributors
Team September– making ocean data accessible for everyone 🌍🌊  

---
