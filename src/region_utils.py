from typing import Dict, Tuple, Optional, List
from src.models import RegionBounds
import re

class RegionCalculator:
    """Utility class for calculating and managing geographical regions"""
    
    # Predefined regions with their bounds
    REGIONS = {
        'bay of bengal': RegionBounds(min_lat=8, max_lat=22, min_lon=80, max_lon=95, region_name='Bay of Bengal'),
        'arabian sea': RegionBounds(min_lat=8, max_lat=25, min_lon=50, max_lon=75, region_name='Arabian Sea'),
        'equatorial indian': RegionBounds(min_lat=-5, max_lat=5, min_lon=50, max_lon=100, region_name='Equatorial Indian'),
        'indian ocean': RegionBounds(min_lat=-40, max_lat=25, min_lon=20, max_lon=120, region_name='Indian Ocean'),
    }
    
    @classmethod
    def identify_region_from_text(cls, text: str) -> Optional[RegionBounds]:
        """
        Identify a region from text input
        """
        text_lower = text.lower()
        
        # Check for direct region matches
        for region_key, bounds in cls.REGIONS.items():
            if region_key in text_lower:
                return bounds
        
        # Check for coordinate patterns
        coords = cls.extract_coordinates_from_text(text)
        if coords:
            return cls.create_region_from_coordinates(coords['lat'], coords['lon'])
        
        return None
    
    @classmethod
    def extract_coordinates_from_text(cls, text: str) -> Optional[Dict[str, float]]:
        """
        Extract latitude and longitude coordinates from text
        """
        # Pattern for decimal coordinates
        coord_pattern = r'(-?\d+\.?\d*)[°]?\s*[,]?\s*(-?\d+\.?\d*)[°]?'
        matches = re.findall(coord_pattern, text)
        
        if matches:
            try:
                lat, lon = float(matches[0][0]), float(matches[0][1])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return {'lat': lat, 'lon': lon}
            except ValueError:
                pass
        
        return None
    
    @classmethod
    def create_region_from_coordinates(cls, lat: float, lon: float, buffer: float = 2.0) -> RegionBounds:
        """
        Create a region bounds around a specific coordinate with a buffer
        """
        return RegionBounds(
            min_lat=max(-90, lat - buffer),
            max_lat=min(90, lat + buffer),
            min_lon=max(-180, lon - buffer),
            max_lon=min(180, lon + buffer),
            region_name=f"Region around ({lat:.2f}, {lon:.2f})"
        )
    
    @classmethod
    def expand_region(cls, bounds: RegionBounds, factor: float = 1.2) -> RegionBounds:
        """
        Expand a region by a given factor
        """
        lat_center = (bounds.min_lat + bounds.max_lat) / 2
        lon_center = (bounds.min_lon + bounds.max_lon) / 2
        
        lat_range = (bounds.max_lat - bounds.min_lat) * factor / 2
        lon_range = (bounds.max_lon - bounds.min_lon) * factor / 2
        
        return RegionBounds(
            min_lat=max(-90, lat_center - lat_range),
            max_lat=min(90, lat_center + lat_range),
            min_lon=max(-180, lon_center - lon_range),
            max_lon=min(180, lon_center + lon_range),
            region_name=f"Expanded {bounds.region_name}" if bounds.region_name else "Expanded Region"
        )
    
    @classmethod
    def get_all_region_names(cls) -> List[str]:
        """
        Get list of all available region names
        """
        return [bounds.region_name for bounds in cls.REGIONS.values()]
    
    @classmethod
    def suggest_nearby_regions(cls, lat: float, lon: float, max_distance: float = 10.0) -> List[str]:
        """
        Suggest regions that are near the given coordinates
        """
        nearby_regions = []
        
        for region_name, bounds in cls.REGIONS.items():
            region_center_lat = (bounds.min_lat + bounds.max_lat) / 2
            region_center_lon = (bounds.min_lon + bounds.max_lon) / 2
            
            # Simple distance calculation (not perfect for all cases, but good enough)
            distance = ((lat - region_center_lat) ** 2 + (lon - region_center_lon) ** 2) ** 0.5
            
            if distance <= max_distance:
                nearby_regions.append(bounds.region_name)
        
        return nearby_regions

    @classmethod
    def classify_query_intent(cls, query: str) -> str:
        """
        Classify the intent of a user query
        """
        query_lower = query.lower()
        
        # Statistical queries
        if any(word in query_lower for word in ['average', 'avg', 'mean', 'median', 'statistics', 'stats', 'what is', 'how much']):
            return 'statistics'
        
        # Visualization queries
        if any(word in query_lower for word in ['plot', 'show', 'display', 'visualize', 'chart', 'graph', 'profile', 'trajectory', 'map']):
            return 'visualization'
        
        # Comparison queries
        if any(word in query_lower for word in ['compare', 'comparison', 'difference', 'vs', 'versus']):
            return 'comparison'
        
        # Search queries
        if any(word in query_lower for word in ['find', 'search', 'locate', 'nearest', 'closest']):
            return 'search'
        
        return 'general'
