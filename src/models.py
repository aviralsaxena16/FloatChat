from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from typing import List, Optional
from datetime import datetime


class ArgoDataPoint(BaseModel):
    """Pydantic model for individual ARGO data points"""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    temp: Optional[float] = Field(None, description="Temperature in Celsius")
    psal: Optional[float] = Field(None, description="Salinity in PSU")
    pres: Optional[float] = Field(None, ge=0, description="Pressure in dbar")
    timestamp: Optional[str] = Field(None, description="Timestamp of measurement")
    platform_number: Optional[str] = Field(None, description="Float identifier")
    cycle_number: Optional[int] = Field(None, description="Cycle number")

    # Convert int to string before validation
    @field_validator('platform_number', mode="before")
    def convert_platform_number(cls, v):
        if v is not None:
            return str(v)
        return v

    # Legacy field mappings for backward compatibility
    @property
    def temperature(self) -> Optional[float]:
        return self.temp

    @property
    def salinity(self) -> Optional[float]:
        return self.psal

    @property
    def pressure(self) -> Optional[float]:
        return self.pres

    @property
    def float_id(self) -> Optional[str]:
        return self.platform_number


class RegionBounds(BaseModel):
    """Pydantic model for geographical region bounds"""
    min_lat: float = Field(..., ge=-90, le=90)
    max_lat: float = Field(..., ge=-90, le=90)
    min_lon: float = Field(..., ge=-180, le=180)
    max_lon: float = Field(..., ge=-180, le=180)
    region_name: Optional[str] = Field(None, description="Name of the region")

    @field_validator('max_lat')
    def validate_lat_bounds(cls, v, info: ValidationInfo):
        min_lat = info.data.get('min_lat')
        if min_lat is not None and v <= min_lat:
            raise ValueError('max_lat must be greater than min_lat')
        return v

    @field_validator('max_lon')
    def validate_lon_bounds(cls, v, info: ValidationInfo):
        min_lon = info.data.get('min_lon')
        if min_lon is not None and v <= min_lon:
            raise ValueError('max_lon must be greater than min_lon')
        return v


class QueryResponse(BaseModel):
    """Pydantic model for query responses"""
    data: List[ArgoDataPoint]
    region: Optional[RegionBounds] = None
    summary: str
    data_count: int = 0

    @field_validator('data_count', mode="before")
    def validate_data_count(cls, v, info: ValidationInfo):
        data = info.data.get('data')
        if data is not None:
            return len(data)
        return v


class RegionStats(BaseModel):
    """Pydantic model for regional statistics"""
    region: RegionBounds
    avg_temp: Optional[float] = None
    avg_psal: Optional[float] = None
    max_temp: Optional[float] = None
    min_temp: Optional[float] = None
    max_psal: Optional[float] = None
    min_psal: Optional[float] = None
    data_points: int = 0
    unique_floats: int = 0


class QueryIntent(BaseModel):
    """Model for classifying user query intent"""
    intent_type: str = Field(..., description="Type of query: 'statistics', 'visualization', 'comparison', 'search'")
    region: Optional[str] = Field(None, description="Mentioned region")
    parameters: List[str] = Field(default_factory=list, description="Requested parameters like temperature, salinity")
    time_period: Optional[str] = Field(None, description="Time period mentioned")
    visualization_type: Optional[str] = Field(None, description="Type of plot requested")
    requires_plotting: bool = Field(False, description="Whether query requires visualization")
