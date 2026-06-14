"""Google Places API client untuk ratings dan metadata."""

import logging
import pandas as pd
import time
from typing import Optional, Dict, Any
import requests

from config import settings

logger = logging.getLogger(__name__)


class GooglePlacesClient:
    """Client untuk Google Places API."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.google_places_api_key
        self.base_url = "https://maps.googleapis.com/maps/api/place"
        self.retry_max = settings.google_places_retry_max
    
    def search_nearby(
        self,
        latitude: float,
        longitude: float,
        radius: int = 1000,
        types: list = None
    ) -> pd.DataFrame:
        """
        Search places nearby coordinates.
        
        Args:
            latitude: Latitude
            longitude: Longitude
            radius: Search radius dalam meters
            types: Filter by place types (e.g., ['museum', 'restaurant'])
            
        Returns:
            pd.DataFrame: Places dengan columns: place_id, name, rating, review_count, lat, lon
        """
        
        places = []
        next_page_token = None
        
        while True:
            try:
                params = {
                    'key': self.api_key,
                    'location': f"{latitude},{longitude}",
                    'radius': radius,
                }
                
                if types:
                    params['type'] = '|'.join(types)
                
                if next_page_token:
                    params['pagetoken'] = next_page_token
                
                response = requests.get(
                    f"{self.base_url}/nearbysearch/json",
                    params=params,
                    timeout=10
                )
                response.raise_for_status()
                
                data = response.json()
                
                for result in data.get('results', []):
                    place = {
                        'google_place_id': result['place_id'],
                        'name': result.get('name', ''),
                        'rating': result.get('rating'),
                        'review_count': result.get('user_ratings_total', 0),
                        'latitude': result['geometry']['location']['lat'],
                        'longitude': result['geometry']['location']['lng'],
                        'types': ','.join(result.get('types', [])),
                        'source': 'google_places'
                    }
                    places.append(place)
                
                # Check untuk next page
                next_page_token = data.get('next_page_token')
                if not next_page_token:
                    break
                
                # Rate limiting
                time.sleep(2)
            
            except Exception as e:
                logger.error(f"Error searching Google Places: {str(e)}")
                break
        
        return pd.DataFrame(places)
    
    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information untuk place.
        
        Args:
            place_id: Google Place ID
            
        Returns:
            dict: Place details (name, rating, hours, photos, etc)
        """
        
        try:
            params = {
                'key': self.api_key,
                'place_id': place_id,
                'fields': (
                    'name,rating,user_ratings_total,formatted_address,'
                    'opening_hours,photos,website,phone_number,url'
                )
            }
            
            response = requests.get(
                f"{self.base_url}/details/json",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get('result')
        
        except Exception as e:
            logger.error(f"Error getting place details: {str(e)}")
            return None
