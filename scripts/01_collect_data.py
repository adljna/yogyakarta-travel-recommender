import sys
import logging
import argparse
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from src.data_collection import (
    WikidataExtractor,
    WikipediaEnricher,
    OSMFetcher,
    GooglePlacesClient,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Data collection pipeline untuk itinerary recommendation system"
    )
    parser.add_argument(
        "--region",
        default="yogyakarta",
        help="Region untuk data collection (default: yogyakarta)"
    )
    parser.add_argument(
        "--skip-wikidata",
        action="store_true",
        help="Skip Wikidata extraction"
    )
    parser.add_argument(
        "--skip-osm",
        action="store_true",
        help="Skip OSM fetching"
    )
    parser.add_argument(
        "--skip-google",
        action="store_true",
        help="Skip Google Places enrichment"
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting data collection pipeline untuk region: {args.region}")
    
    # Create output directories
    raw_path = Path(settings.raw_data_path)
    raw_path.mkdir(parents=True, exist_ok=True)
    
    processed_path = Path(settings.processed_data_path)
    processed_path.mkdir(parents=True, exist_ok=True)
    
    # Phase 1: Wikidata Extraction
    if not args.skip_wikidata:
        logger.info("=" * 60)
        logger.info("PHASE 1: Extracting destinations dari Wikidata...")
        logger.info("=" * 60)
        
        try:
            extractor = WikidataExtractor()
            destinations = extractor.extract(
                region=args.region,
                limit=1000
            )
            
            if extractor.validate():
                output_file = raw_path / f"wikidata_{args.region}.csv"
                extractor.save(str(output_file))
                logger.info(f"Metadata: {extractor.get_metadata()}")
            
        except Exception as e:
            logger.error(f"Error dalam Wikidata extraction: {str(e)}")
            destinations = pd.DataFrame()
    else:
        logger.info("Skipping Wikidata extraction")
        destinations = pd.DataFrame()
    
    # Phase 2: Wikipedia Enrichment
    if not destinations.empty and not args.skip_wikidata:
        logger.info("=" * 60)
        logger.info("PHASE 2: Enriching data dari Wikipedia...")
        logger.info("=" * 60)
        
        try:
            enricher = WikipediaEnricher()
            enriched = enricher.enrich(destinations)
            
            output_file = raw_path / f"wikipedia_enrichment_{args.region}.csv"
            enriched.to_csv(output_file, index=False, encoding='utf-8')
            logger.info(f"Enrichment saved to {output_file}")
            
            destinations = enriched
        
        except Exception as e:
            logger.error(f"Error dalam Wikipedia enrichment: {str(e)}")
    
    # Phase 3: OSM POI Expansion
    if not args.skip_osm:
        logger.info("=" * 60)
        logger.info("PHASE 3: Fetching POIs dari OpenStreetMap...")
        logger.info("=" * 60)
        
        try:
            osm = OSMFetcher()
            pois = osm.fetch_tourism_pois(area_name=args.region.title())
            
            if not pois.empty:
                output_file = raw_path / f"osm_pois_{args.region}.csv"
                pois.to_csv(output_file, index=False, encoding='utf-8')
                logger.info(f"OSM POIs saved to {output_file}")
        
        except Exception as e:
            logger.error(f"Error dalam OSM fetch: {str(e)}")
    
    # Phase 4: Google Places Enrichment (if API key available)
    if not args.skip_google and settings.google_places_api_key:
        logger.info("=" * 60)
        logger.info("PHASE 4: Enriching ratings dari Google Places...")
        logger.info("=" * 60)
        
        try:
            google = GooglePlacesClient()
            logger.info("Google Places API client initialized")
            # In production, would search each destination by name
            logger.info("Note: Run search untuk setiap destination secara manual atau batch")
        
        except Exception as e:
            logger.error(f"Error dengan Google Places: {str(e)}")
    else:
        logger.warning("Google Places API key not configured, skipping Google enrichment")
    
    logger.info("=" * 60)
    logger.info("Data collection pipeline complete!")
    logger.info("=" * 60)
    logger.info(f"Raw data saved to: {raw_path}")
    logger.info("Next step: Run scripts/02_process_data.py untuk clean dan merge data")


if __name__ == "__main__":
    main()
