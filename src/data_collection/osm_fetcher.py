"""OpenStreetMap Overpass API fetcher untuk POIs."""

import logging
import pandas as pd
import requests
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class OSMFetcher:
    """Fetch POIs dari OpenStreetMap Overpass API."""
    
    def __init__(self):
        self.overpass_api = "https://overpass-api.de/api/interpreter"
    
    # Bounding boxes untuk region yang didukung (south, west, north, east)
    REGION_BBOX = {
        'yogyakarta': (-7.95, 110.20, -7.55, 110.55),
        'bali':       (-8.85, 114.43, -8.06, 115.71),
        'bandung':    (-7.10, 107.48, -6.79, 107.78),
        'jakarta':    (-6.37,  106.65, -6.08, 107.00),
        'surabaya':   (-7.40,  112.60, -7.15, 112.85),
        'lombok':     (-9.00, 115.95, -8.30, 116.70),
        'labuan_bajo':(-8.65, 119.80, -8.40, 120.05),
        'medan':      ( 3.40,   98.55,  3.75,  98.80),
    }

    def fetch_tourism_pois(
        self,
        area_name: str,
        tags: List[str] = None,
        bbox: tuple = None,
    ) -> pd.DataFrame:
        """
        Fetch tourism POIs dari area tertentu menggunakan bounding box.

        Args:
            area_name: Nama area (e.g., 'Yogyakarta') — dipakai untuk lookup bbox
            tags: OSM tags untuk filter
            bbox: (south, west, north, east) override; jika None, lookup dari REGION_BBOX

        Returns:
            pd.DataFrame: POIs dengan columns: osm_id, name, lat, lon, tags, type
        """

        if tags is None:
            tags = [
                'tourism=attraction',
                'tourism=museum',
                'tourism=viewpoint',
                'tourism=hotel',
                'tourism=restaurant',
                'amenity=restaurant',
                'amenity=cafe',
                'amenity=fast_food',
            ]

        if bbox is None:
            bbox = self.REGION_BBOX.get(area_name.lower())
        if bbox is None:
            logger.error(f"Tidak ada bounding box untuk '{area_name}'. Tambahkan ke REGION_BBOX.")
            return pd.DataFrame()

        south, west, north, east = bbox
        bbox_str = f"{south},{west},{north},{east}"

        # Build Overpass union query menggunakan bounding box (lebih reliable dari area name)
        node_lines = '\n  '.join(
            [f'node["{k}"="{v}"]({bbox_str});' for k, v in (t.split('=', 1) for t in tags)]
        )
        way_lines = '\n  '.join(
            [f'way["{k}"="{v}"]({bbox_str});' for k, v in (t.split('=', 1) for t in tags)]
        )

        query = f"""[out:json][timeout:90];
(
  {node_lines}
  {way_lines}
);
out body geom;
"""

        try:
            logger.info(f"Fetching OSM POIs untuk {area_name} (bbox: {bbox_str})...")

            response = requests.post(
                self.overpass_api,
                data={'data': query},
                headers={'User-Agent': 'ItineraryRecommendationSystem/0.1'},
                timeout=120,
            )
            response.raise_for_status()
            
            data = response.json()
            
            pois = []
            for element in data.get('elements', []):
                if element['type'] == 'node':
                    poi = self._parse_node(element)
                elif element['type'] == 'way':
                    poi = self._parse_way(element)
                else:
                    continue
                
                if poi:
                    pois.append(poi)
            
            df = pd.DataFrame(pois)
            logger.info(f"Fetched {len(df)} POIs dari OSM")
            return df
        
        except Exception as e:
            logger.error(f"Error fetching OSM data: {str(e)}")
            return pd.DataFrame()
    
    @staticmethod
    def _parse_node(element: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OSM node element."""
        tags = element.get('tags', {})
        return {
            'osm_id': f"node_{element['id']}",
            'name': tags.get('name', ''),
            'latitude': element.get('lat'),
            'longitude': element.get('lon'),
            'type': tags.get('tourism', tags.get('amenity', '')),
            'tags': json.dumps(tags),
            'source': 'osm'
        }
    
    @staticmethod
    def _parse_way(element: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OSM way element (calculate centroid)."""
        tags = element.get('tags', {})
        
        # Calculate centroid dari geometry
        if 'geometry' in element:
            lats = [coord['lat'] for coord in element['geometry']]
            lons = [coord['lon'] for coord in element['geometry']]
            lat = sum(lats) / len(lats)
            lon = sum(lons) / len(lons)
        else:
            return None
        
        return {
            'osm_id': f"way_{element['id']}",
            'name': tags.get('name', ''),
            'latitude': lat,
            'longitude': lon,
            'type': tags.get('tourism', tags.get('amenity', '')),
            'tags': json.dumps(tags),
            'source': 'osm'
        }
