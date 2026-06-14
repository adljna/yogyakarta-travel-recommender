"""Base class untuk data extractor."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Abstract base class untuk semua data extractors."""
    
    def __init__(self, name: str, source: str):
        """
        Initialize base extractor.
        
        Args:
            name: Nama extractor (e.g., 'wikidata', 'osm')
            source: Sumber data (e.g., 'Wikidata', 'OpenStreetMap')
        """
        self.name = name
        self.source = source
        self.data: Optional[pd.DataFrame] = None
        self.extracted_at = None
    
    @abstractmethod
    def extract(self, *args, **kwargs) -> pd.DataFrame:
        """
        Extract data dari source.
        
        Must be implemented by subclasses.
        """
        pass
    
    def validate(self) -> bool:
        """
        Validate extracted data.
        
        Returns:
            bool: True jika data valid
        """
        if self.data is None:
            logger.error(f"{self.name}: No data extracted")
            return False
        
        if len(self.data) == 0:
            logger.error(f"{self.name}: Empty dataframe")
            return False
        
        logger.info(f"{self.name}: Data validation passed. Rows: {len(self.data)}")
        return True
    
    def save(self, filepath: str) -> bool:
        """
        Save extracted data ke CSV.
        
        Args:
            filepath: Path untuk save file
            
        Returns:
            bool: True jika berhasil
        """
        try:
            self.data.to_csv(filepath, index=False, encoding='utf-8')
            logger.info(f"{self.name}: Data saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"{self.name}: Error saving data: {str(e)}")
            return False
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata tentang extraction.
        
        Returns:
            dict: Metadata (row count, columns, extracted_at, etc)
        """
        return {
            "extractor": self.name,
            "source": self.source,
            "rows": len(self.data) if self.data is not None else 0,
            "columns": list(self.data.columns) if self.data is not None else [],
            "extracted_at": datetime.now().isoformat(),
        }
