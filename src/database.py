import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List

from src.models import ArgoDataPoint, RegionBounds
from src.region_utils import RegionCalculator


class ArgoDatabase:
    """Database interface for ARGO data"""
    
    def __init__(self):
        self.engine = self._get_db_engine()
        self.region_calculator = RegionCalculator()
        self.table_name = "argo_measurements"  # Your view/table name
    
    @st.cache_resource
    def _get_db_engine(_self):
        """Initialize database connection with caching"""
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(dotenv_path=env_path)
        
        DB_USER = os.getenv("DB_USER")
        DB_PASS = os.getenv("DB_PASS") 
        DB_HOST = os.getenv("DB_HOST")
        DB_PORT = os.getenv("DB_PORT")
        DB_NAME = os.getenv("DB_NAME")
        
        if not all([DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME]):
            st.error("Database credentials are not set. Check your .env file.")
            st.stop()
        
        encoded_pass = quote_plus(DB_PASS)
        DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        
        return create_engine(DATABASE_URL)
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results as DataFrame"""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(query))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                return df
        except Exception as e:
            st.error(f"Database query error: {e}")
            return pd.DataFrame()
    
    def get_region_data(self, region: RegionBounds, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get ARGO data for a specific region."""
        query = f"""
        SELECT 
            latitude,
            longitude,
            temp,
            psal,
            pres,
            juld AS timestamp,
            CAST(platform_number AS TEXT) AS platform_number
        FROM {self.table_name}
        WHERE latitude BETWEEN {region.min_lat} AND {region.max_lat}
        AND longitude BETWEEN {region.min_lon} AND {region.max_lon}
        AND temp IS NOT NULL
        AND psal IS NOT NULL
        AND pres IS NOT NULL
        ORDER BY juld DESC
        LIMIT {limit};
        """
        df = self.execute_query(query)
        return df.to_dict('records') if not df.empty else []

    def get_float_trajectory(self, platform_number: str) -> List[Dict[str, Any]]:
        """Get trajectory data for a specific float."""
        query = f"""
        SELECT 
            latitude,
            longitude,
            juld AS timestamp,
            platform_number
        FROM {self.table_name}
        WHERE platform_number = '{platform_number}'
        ORDER BY juld ASC;
        """
        df = self.execute_query(query)
        return df.to_dict('records') if not df.empty else []

    def get_surface_temperature_timeseries(self, region: RegionBounds) -> List[Dict[str, Any]]:
        """Get surface temperature time series (pres <= 10) for a region."""
        query = f"""
        SELECT 
            temp,
            juld AS timestamp,
            pres,
            latitude,
            longitude,
            platform_number
        FROM {self.table_name}
        WHERE latitude BETWEEN {region.min_lat} AND {region.max_lat}
          AND longitude BETWEEN {region.min_lon} AND {region.max_lon}
          AND pres <= 10
          AND temp IS NOT NULL
        ORDER BY juld ASC;
        """
        df = self.execute_query(query)
        return df.to_dict('records') if not df.empty else []

    def search_floats_in_region(self, region: RegionBounds) -> List[str]:
        """Get list of platform_numbers in a region."""
        query = f"""
        SELECT DISTINCT platform_number
        FROM {self.table_name}
        WHERE latitude BETWEEN {region.min_lat} AND {region.max_lat}
          AND longitude BETWEEN {region.min_lon} AND {region.max_lon};
        """
        df = self.execute_query(query)
        return df['platform_number'].tolist() if not df.empty else []

    def get_regional_averages(self, region: RegionBounds) -> Dict[str, float]:
        """Calculate regional averages."""
        query = f"""
        SELECT 
            AVG(temp) AS avg_temp,
            AVG(psal) AS avg_psal,
            MIN(temp) AS min_temp,
            MAX(temp) AS max_temp,
            MIN(psal) AS min_psal,
            MAX(psal) AS max_psal,
            COUNT(*) AS data_points,
            COUNT(DISTINCT platform_number) AS unique_floats
        FROM {self.table_name}
        WHERE latitude BETWEEN {region.min_lat} AND {region.max_lat}
          AND longitude BETWEEN {region.min_lon} AND {region.max_lon}
          AND temp IS NOT NULL
          AND psal IS NOT NULL;
        """
        df = self.execute_query(query)
        return df.to_dict('records')[0] if not df.empty else {}

    def get_parameter_statistics(self, region: RegionBounds, parameter: str) -> Dict[str, Any]:
        """Get statistics for a specific parameter in a region."""
        param_mapping = {
            'temperature': 'temp',
            'salinity': 'psal',
            'pressure': 'pres',
        }
        col_name = param_mapping.get(parameter.lower(), parameter.lower())

        query = f"""
        SELECT 
            AVG({col_name}) AS avg_value,
            MIN({col_name}) AS min_value,
            MAX({col_name}) AS max_value,
            STDDEV({col_name}) AS std_value,
            COUNT({col_name}) AS data_points,
            COUNT(DISTINCT platform_number) AS unique_floats
        FROM {self.table_name}
        WHERE latitude BETWEEN {region.min_lat} AND {region.max_lat}
          AND longitude BETWEEN {region.min_lon} AND {region.max_lon}
          AND {col_name} IS NOT NULL;
        """
        df = self.execute_query(query)
        return df.to_dict('records')[0] if not df.empty else {}