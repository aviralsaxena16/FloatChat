import os
import json
import tempfile
import requests
import xarray as xr
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import warnings
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import zipfile

warnings.filterwarnings("ignore")

BASE_URL = "https://www.ncei.noaa.gov/data/oceans/argo/gadr/data/indian/"
OUTPUT_DIR = "argo_csvs"
STATE_FILE = "processed_files.json"
ZIP_NAME = "argo_csvs_sql_ready.zip"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define column types for cleaning
COLUMN_TYPES = {
    "pres": float, "pres_qc": str, "pres_adjusted": float, "pres_adjusted_qc": str,
    "temp": float, "temp_qc": str, "temp_adjusted": float, "temp_adjusted_qc": str,
    "psal": float, "psal_qc": str, "psal_adjusted": float, "psal_adjusted_qc": str,
    "data_type": str, "format_version": str, "handbook_version": str,
    "reference_date_time": "datetime", "date_creation": "datetime", "date_update": "datetime",
    "platform_number": str, "project_name": str, "pi_name": str, "station_parameters": str,
    "cycle_number": int, "direction": str, "data_centre": str, "dc_reference": str,
    "data_state_indicator": str, "data_mode": str, "platform_type": str, "float_serial_no": str,
    "firmware_version": str, "wmo_inst_type": str, "juld": float, "juld_qc": str,
    "juld_location": float, "latitude": float, "longitude": float, "position_qc": str,
    "positioning_system": str, "profile_pres_qc": str, "profile_temp_qc": str, "profile_psal_qc": str,
    "vertical_sampling_scheme": str, "config_mission_number": str, "pres_adjusted_error": float,
    "temp_adjusted_error": float, "psal_adjusted_error": float, "parameter": str,
    "scientific_calib_equation": str, "scientific_calib_coefficient": str,
    "scientific_calib_comment": str, "scientific_calib_date": "datetime",
    "history_institution": str, "history_step": str, "history_software": str,
    "history_software_release": str, "history_reference": str, "history_date": "datetime",
    "history_action": str, "history_parameter": str, "history_start_pres": float,
    "history_stop_pres": float, "history_previous_value": str, "history_qctest": str, "crs": str
}

# STATE MANAGEMENT
def load_processed_files():
    
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"processed": [], "last_run": None}

def save_processed_files(state):
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# WEB SCRAPING 
def get_subfolders(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True)]
    return [l for l in links if l != url and not l.endswith("../")]

def get_nc_files(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True)]
    return [l for l in links if l.endswith(".nc")]

# DATA PROCESSING
def convert_value(val, target_type):
    """Convert a single value to the target type"""
    if isinstance(val, bytes):
        val = val.decode("utf-8", errors="ignore")
    if isinstance(val, str) and val.startswith("b'") and val.endswith("'"):
        val = val[2:-1]

    if pd.isna(val) or val == "":
        return pd.NA

    try:
        if target_type == float:
            return float(val)
        elif target_type == int:
            return int(float(val))
        elif target_type == "datetime":
            return pd.to_datetime(val, errors="coerce")
        else:
            return str(val)
    except:
        return pd.NA

def clean_dataframe(df):
    #Clean dataframe according to schema
    for col, typ in COLUMN_TYPES.items():
        if col in df.columns:
            df[col] = df[col].apply(lambda x: convert_value(x, typ))
    
    # Convert datetime columns to ISO strings
    for col, typ in COLUMN_TYPES.items():
        if typ == "datetime" and col in df.columns:
            df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else "")
    
    return df

def process_nc_file(url, csv_name):
    #Download, convert, and clean a single .nc file
    try:
        local_file = tempfile.NamedTemporaryFile(delete=False)
        r = requests.get(url, timeout=30)
        local_file.write(r.content)
        local_file.close()

        ds = xr.open_dataset(local_file.name)
        df = ds.to_dataframe().reset_index()
        
        # Clean according to schema
        df = clean_dataframe(df)
        
        df.to_csv(csv_name, index=False, encoding="utf-8")
        print(f"Converted {url} → {csv_name}")
        os.remove(local_file.name)
        return True
    except Exception as e:
        print(f"Failed {url}: {e}")
        return False

# FETCH LOGIC 
def fetch_new_data():
    #Fetch only NEW files that haven't been processed before
    print(f"\n{'='*60}")
    print(f"Starting weekly data fetch: {datetime.now()}")
    print(f"{'='*60}\n")
    
    state = load_processed_files()
    processed_set = set(state["processed"])
    newly_processed = []
    
    subfolders = get_subfolders(BASE_URL)
    
    for folder in subfolders:
        sub_subfolders = get_subfolders(folder)
        for sub in sub_subfolders:
            nc_files = get_nc_files(sub)
            for nc_url in nc_files:
                #Skip if already processed
                if nc_url in processed_set:
                    continue
                
                csv_name = os.path.join(OUTPUT_DIR, os.path.basename(nc_url).replace(".nc", ".csv"))
                success = process_nc_file(nc_url, csv_name)
                
                if success:
                    newly_processed.append(nc_url)
                    processed_set.add(nc_url)
    
    # Update state
    state["processed"] = list(processed_set)
    state["last_run"] = datetime.now().isoformat()
    save_processed_files(state)
    
    print(f"\n{'='*60}")
    print(f"Fetch complete! New files processed: {len(newly_processed)}")
    print(f"Total files tracked: {len(processed_set)}")
    print(f"{'='*60}\n")
    
    # Create zip if new files were added
    if newly_processed:
        create_zip()
    
    return len(newly_processed)

def create_zip():
    #Zip all CSV files
    print("Creating ZIP archive...")
    with zipfile.ZipFile(ZIP_NAME, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith(".csv"):
                zipf.write(os.path.join(OUTPUT_DIR, f), arcname=f)
    print(f"Created '{ZIP_NAME}'")

#SCHEDULER 
def run_scheduler():
    #weekly - Run the scheduler (weekly on Mondays at 2 AM)
    scheduler = BlockingScheduler()
    
    # Schedule weekly: every Monday at 2:00 AM
    scheduler.add_job(fetch_new_data, 'cron', day_of_week='mon', hour=2, minute=0)
    
    print("Scheduler started!")
    print("Will run every Monday at 2:00 AM")
    print("Press Ctrl+C to stop\n")
    
    # Run immediately on first start
    print("Running initial fetch...")
    fetch_new_data()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n Scheduler stopped!")

#MANUAL TRIGGERS
def manual_fetch():
    # Manually trigger a fetch (for testing)
    fetch_new_data()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        # Run once manually
        manual_fetch()
    else:
        # Start scheduler
        run_scheduler()
