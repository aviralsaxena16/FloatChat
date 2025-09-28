import os
import glob
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv("../.env")
RAW_DATA_PATH = "../data/"  # Points to your folder with CSV files
TABLE_NAME = "argo_data" # Uploading to the main table

# --- DATABASE CONNECTION ---
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError("One or more database environment variables are not set. Check your .env file.")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def process_and_load_csv_data():
    """
    Finds all CSV files, processes them, and ingests them into the database.
    """
    csv_files = glob.glob(os.path.join(RAW_DATA_PATH, '*.csv'))
    
    if not csv_files:
        print(f"No CSV files found in {RAW_DATA_PATH}. Exiting.")
        return

    all_dataframes = []
    print(f"Found {len(csv_files)} CSV files to process...")

    for i, file_path in enumerate(csv_files):
        try:
            print(f"Processing file {i+1}/{len(csv_files)}: {os.path.basename(file_path)}")
            # Read the CSV file into a pandas DataFrame.
            df = pd.read_csv(file_path)
            all_dataframes.append(df)
        except Exception as e:
            print(f"  -> Error processing file {file_path}: {e}")

    if not all_dataframes:
        print("No data was successfully processed from CSVs. Exiting.")
        return

    print("Concatenating all dataframes...")
    final_df = pd.concat(all_dataframes, ignore_index=True)

    print(f"Uploading {len(final_df)} total records to PostgreSQL table '{TABLE_NAME}'...")
    # Use 'replace' to ensure a clean upload each time you run the script
    final_df.to_sql(TABLE_NAME, engine, if_exists='replace', index=False)
    
    print("--- CSV Ingestion Complete! ---")

if __name__ == "__main__":
    process_and_load_csv_data()