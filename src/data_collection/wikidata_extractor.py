"""Wikidata SPARQL extractor untuk tourist destinations."""

import logging
import pandas as pd
from typing import Optional
import requests

from .base_extractor import BaseExtractor
from config import settings

logger = logging.getLogger(__name__)


class WikidataExtractor(BaseExtractor):
    """Extract tourist destinations dari Wikidata menggunakan SPARQL."""
    
    def __init__(self):
        super().__init__(name="wikidata", source="Wikidata")
        self.endpoint = settings.wikidata_sparql_endpoint
    
    # Bounding boxes per region — harus sinkron dengan OSMFetcher.REGION_BBOX
    REGION_BBOX = {
        'yogyakarta':  (-7.95, 110.20, -7.55, 110.55),
        'bali':        (-8.85, 114.43, -8.06, 115.71),
        'bandung':     (-7.10, 107.48, -6.79, 107.78),
        'jakarta':     (-6.37, 106.65, -6.08, 107.00),
        'surabaya':    (-7.40, 112.60, -7.15, 112.85),
        'lombok':      (-9.00, 115.95, -8.30, 116.70),
        'labuan_bajo': (-8.65, 119.80, -8.40, 120.05),
        'medan':       ( 3.40,  98.55,  3.75,  98.80),
    }

    def extract(
        self,
        region: str = "yogyakarta",
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Extract tourist destinations dari Wikidata SPARQL menggunakan bounding box.

        Args:
            region: Nama region (key di REGION_BBOX), default: 'yogyakarta'
            limit: Jumlah maksimal hasil

        Returns:
            pd.DataFrame: Destinations dengan columns: wikidata_id, name, category,
                         lat, lon, description, wikipedia_url, source
        """
        bbox = self.REGION_BBOX.get(region.lower())
        if bbox is None:
            logger.error(f"Region '{region}' tidak ditemukan di REGION_BBOX.")
            self.data = pd.DataFrame()
            return self.data

        south, west, north, east = bbox

        # wikibase:box lebih reliable daripada P131+ traversal
        query = f"""
        SELECT DISTINCT
            ?item ?itemLabel
            ?coord
            ?desc
            ?category ?categoryLabel
            ?article
        WHERE {{
            SERVICE wikibase:box {{
                ?item wdt:P625 ?coord .
                bd:serviceParam wikibase:cornerWest "Point({west} {south})"^^geo:wktLiteral .
                bd:serviceParam wikibase:cornerEast "Point({east} {north})"^^geo:wktLiteral .
            }}

            # tourist attraction, museum, beach, mountain, national park,
            # island, palace, archaeological site, temple, park
            VALUES ?targetType {{
                wd:Q570116 wd:Q33506 wd:Q40080 wd:Q8502 wd:Q46169
                wd:Q23442 wd:Q16560 wd:Q839954 wd:Q44539 wd:Q22698
            }}
            ?item wdt:P31/wdt:P279* ?targetType .

            OPTIONAL {{ ?item wdt:P31 ?category . }}
            OPTIONAL {{ ?item schema:description ?desc FILTER(LANG(?desc) = "id") }}
            OPTIONAL {{
                ?article schema:about ?item .
                ?article schema:inLanguage "en" .
                ?article schema:isPartOf <https://en.wikipedia.org/> .
            }}

            SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "id,en" .
            }}
        }}
        LIMIT {limit}
        """
        
        try:
            logger.info(f"Querying Wikidata for region '{region}' (bbox: {bbox})...")

            response = requests.get(
                self.endpoint,
                params={
                    'query': query,
                    'format': 'json'
                },
                headers={
                    'User-Agent': 'ItineraryRecommendationSystem/0.1 (educational project)',
                    'Accept': 'application/sparql-results+json',
                },
                timeout=90
            )
            response.raise_for_status()
            
            results = response.json()['results']['bindings']
            
            # Parse results menjadi DataFrame
            data = []
            for result in results:
                # Extract coordinates
                coord_str = result.get('coord', {}).get('value', '')
                try:
                    lat, lon = self._parse_coordinates(coord_str)
                except:
                    lat, lon = None, None
                
                item = {
                    'wikidata_id': self._extract_id(result.get('item', {}).get('value', '')),
                    'name': result.get('itemLabel', {}).get('value', ''),
                    'category': result.get('categoryLabel', {}).get('value', ''),
                    'description': result.get('desc', {}).get('value', ''),
                    'latitude': lat,
                    'longitude': lon,
                    'location': result.get('locationLabel', {}).get('value', ''),
                    'wikipedia_url': result.get('article', {}).get('value', ''),
                    'source': 'wikidata'
                }
                
                if item['name']:  # Only include if name exists
                    data.append(item)
            
            self.data = pd.DataFrame(data)
            logger.info(f"Extracted {len(self.data)} destinations from Wikidata")
            
            return self.data
        
        except Exception as e:
            logger.error(f"Error extracting from Wikidata: {str(e)}")
            self.data = pd.DataFrame()
            return self.data
    
    @staticmethod
    def _parse_coordinates(coord_str: str) -> tuple:
        """Parse Wikidata coordinate format: Point(lat lon)"""
        # Format: "Point(110.20392 -7.60952)"
        coord_str = coord_str.replace('Point(', '').replace(')', '')
        lon, lat = map(float, coord_str.split())
        return lat, lon
    
    @staticmethod
    def _extract_id(url: str) -> str:
        """Extract Wikidata ID dari URL."""
        return url.split('/')[-1]
