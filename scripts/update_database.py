import os
import glob
import pandas as pd
import xarray as xr
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv("../.env")
LATEST_DATA_PATH = "../data/raw_latest/"
TABLE_NAME = "argo_measurements"

# Identical DB connection setup as the initial script
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def update_database_with_latest_data():
    nc_files = glob.glob(os.path.join(LATEST_DATA_PATH, '*.nc'))
    if not nc_files:
        print("No new files to process.")
        return

    all_data = []
    print(f"Found {len(nc_files)} new files to process...")

    # Same processing loop as the initial script
    for file_path in nc_files:
        try:
            with xr.open_dataset(file_path) as ds:
                # Identical processing logic
                df = ds.to_dataframe().reset_index()
                required_cols = ['LATITUDE', 'LONGITUDE', 'TIME', 'TEMP_ADJUSTED', 'PSAL_ADJUSTED', 'PRES_ADJUSTED']
                if all(col in df.columns for col in required_cols):
                    df_subset = df[required_cols]
                    df_subset['float_id'] = ds.attrs.get('platform_number', os.path.basename(file_path).split('_')[0])
                    df_subset = df_subset.rename(columns={
                        'LATITUDE': 'lat', 'LONGITUDE': 'lon', 'TIME': 'timestamp',
                        'TEMP_ADJUSTED': 'temperature', 'PSAL_ADJUSTED': 'salinity', 'PRES_ADJUSTED': 'pressure'
                    })
                    df_subset.dropna(inplace=True)
                    all_data.append(df_subset)
        except Exception as e:
            print(f"  -> Error processing new file {file_path}: {e}")
    
    if not all_data:
        print("No new data was successfully processed.")
        return

    final_df = pd.concat(all_data, ignore_index=True)

    print(f"Appending {len(final_df)} new measurements to PostgreSQL...")
    # Key difference: Use 'append' to add new data without deleting old data
    final_df.to_sql(TABLE_NAME, engine, if_exists='append', index=False)
    
    # Update the geospatial column for the new rows only
    with engine.connect() as conn:
        conn.execute(f"UPDATE {TABLE_NAME} SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326) WHERE geom IS NULL;")
    print("--- Database Update Complete! ---")

    # Clean up the processed files
    for f in nc_files:
        os.remove(f)
    print("Cleaned up temporary download files.")

if __name__ == "__main__":
    update_database_with_latest_data()