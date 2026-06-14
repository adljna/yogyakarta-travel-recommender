"""Wikipedia enricher untuk menambah description dan metadata."""

import logging
import pandas as pd
from typing import Optional
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)


class WikipediaEnricher:
    """Enrich destination data dengan Wikipedia content."""
    
    def __init__(self):
        self.wikipedia_api = "https://en.wikipedia.org/w/api.php"
    
    def enrich(self, destinations: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich destinations dengan Wikipedia descriptions.
        
        Args:
            destinations: DataFrame dengan column 'name'
            
        Returns:
            pd.DataFrame: Enriched dengan column 'wikipedia_extract', 'wikipedia_url'
        """
        
        destinations = destinations.copy()
        destinations['wikipedia_extract'] = ''
        destinations['wikipedia_url'] = ''
        
        for idx, row in destinations.iterrows():
            try:
                name = row['name']
                logger.info(f"Enriching {name} dari Wikipedia...")
                
                # Search Wikipedia
                params = {
                    'action': 'query',
                    'format': 'json',
                    'titles': name,
                    'prop': 'extracts|info',
                    'inprop': 'url',
                    'explaintext': True,
                    'exsentences': 3,
                }
                
                response = requests.get(self.wikipedia_api, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                pages = data['query']['pages']
                
                for page_id, page_data in pages.items():
                    if 'extract' in page_data:
                        extract = page_data['extract'][:500]  # First 500 chars
                        url = page_data.get('contenturl', '')
                        
                        destinations.at[idx, 'wikipedia_extract'] = extract
                        destinations.at[idx, 'wikipedia_url'] = url
                        break
            
            except Exception as e:
                logger.warning(f"Error enriching {row.get('name', 'unknown')}: {str(e)}")
                continue
        
        return destinations
