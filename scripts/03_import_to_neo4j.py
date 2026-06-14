#!/usr/bin/env python3
"""
Import CSV data (dari Google Maps scraping) ke Neo4j.

Harus dijalankan SETELAH 02_process_data.py.

Usage:
    python scripts/03_import_to_neo4j.py
"""

import sys
import logging
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from src.database import Neo4jClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

IMPORT_DIR = Path(settings.neo4j_import_path)
BATCH_SIZE = 200


def batch_import(client: Neo4jClient, query: str, rows: list, label: str):
    total = len(rows)
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        client.run_query(query, {'rows': batch})
        logger.info(f"  {label}: {min(i + BATCH_SIZE, total)}/{total}")


def _bool_int(val) -> int:
    """Konversi nilai CSV ke integer 0/1 untuk boolean field."""
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        return int(bool(val))
    return 1 if str(val).strip().lower() in ('1', 'true', 'yes') else 0


def prepare_bool_cols(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Pastikan kolom boolean berisi integer 0/1."""
    for col in cols:
        if col in df.columns:
            df[col] = df[col].apply(_bool_int)
    return df


DEST_BOOL_COLS = [
    'has_toilet', 'has_restaurant', 'wheelchair_accessible',
    'good_for_kids', 'good_for_kids_birthday',
    'has_parking', 'has_free_parking',
    'requires_appointment', 'tickets_in_advance',
]

REST_BOOL_COLS = [
    'has_toilet', 'wheelchair_accessible', 'good_for_kids',
    'outdoor_seating', 'delivery_available', 'dine_in',
    'great_coffee', 'great_food', 'cash_only',
]


def import_destinations(client: Neo4jClient) -> int:
    path = IMPORT_DIR / 'destinations.csv'
    if not path.exists():
        logger.error(f"File tidak ditemukan: {path}")
        return 0

    df = pd.read_csv(path).fillna('')
    df = prepare_bool_cols(df, DEST_BOOL_COLS)
    rows = df.to_dict('records')

    dest_query = """
    UNWIND $rows AS row
    MERGE (d:Destination {destination_id: row.destination_id})
    SET d.name                   = row.name,
        d.category               = row.category,
        d.latitude               = toFloat(row.latitude),
        d.longitude              = toFloat(row.longitude),
        d.city                   = row.city,
        d.borough                = row.borough,
        d.street                 = row.street,
        d.postal_code            = row.postal_code,
        d.state                  = row.state,
        d.region                 = row.region,
        d.review_rating          = toFloat(coalesce(row.review_rating, 0)),
        d.review_count           = toInteger(coalesce(row.review_count, 0)),
        d.open_hours             = row.open_hours,
        d.open_hours_monday      = row.open_hours_monday,
        d.open_hours_tuesday     = row.open_hours_tuesday,
        d.open_hours_wednesday   = row.open_hours_wednesday,
        d.open_hours_thursday    = row.open_hours_thursday,
        d.open_hours_friday      = row.open_hours_friday,
        d.open_hours_saturday    = row.open_hours_saturday,
        d.open_hours_sunday      = row.open_hours_sunday,
        d.price_range            = row.price_range,
        d.has_toilet             = toBoolean(toInteger(row.has_toilet)),
        d.has_restaurant         = toBoolean(toInteger(row.has_restaurant)),
        d.wheelchair_accessible  = toBoolean(toInteger(row.wheelchair_accessible)),
        d.good_for_kids          = toBoolean(toInteger(row.good_for_kids)),
        d.good_for_kids_birthday = toBoolean(toInteger(row.good_for_kids_birthday)),
        d.has_parking            = toBoolean(toInteger(row.has_parking)),
        d.has_free_parking       = toBoolean(toInteger(row.has_free_parking)),
        d.requires_appointment   = toBoolean(toInteger(row.requires_appointment)),
        d.tickets_in_advance     = toBoolean(toInteger(row.tickets_in_advance)),
        d.google_maps_url        = row.google_maps_url,
        d.source                 = row.source,
        d.popularity_score       = toFloat(coalesce(row.popularity_score, 0))
    """

    city_query = """
    UNWIND $rows AS row
    MERGE (c:City {name: row.city})
    SET c.state = row.state, c.country = 'Indonesia', c.region = row.region
    WITH c, row
    MATCH (d:Destination {destination_id: row.destination_id})
    MERGE (d)-[:LOCATED_IN]->(c)
    """

    category_query = """
    UNWIND $rows AS row
    MERGE (cat:Category {name: row.category})
    WITH cat, row
    MATCH (d:Destination {destination_id: row.destination_id})
    MERGE (d)-[:HAS_CATEGORY]->(cat)
    """

    logger.info(f"Importing {len(rows)} destinations...")
    batch_import(client, dest_query, rows, "Destinations")
    batch_import(client, city_query, rows, "City links")
    batch_import(client, category_query, rows, "Category links")
    return len(rows)


def import_restaurants(client: Neo4jClient) -> int:
    path = IMPORT_DIR / 'restaurants.csv'
    if not path.exists():
        logger.error(f"File tidak ditemukan: {path}")
        return 0

    df = pd.read_csv(path).fillna('')
    df = prepare_bool_cols(df, REST_BOOL_COLS)
    rows = df.to_dict('records')

    rest_query = """
    UNWIND $rows AS row
    MERGE (r:Restaurant {restaurant_id: row.restaurant_id})
    SET r.name                = row.name,
        r.category            = row.category,
        r.latitude            = toFloat(row.latitude),
        r.longitude           = toFloat(row.longitude),
        r.city                = row.city,
        r.borough             = row.borough,
        r.region              = row.region,
        r.review_rating       = toFloat(coalesce(row.review_rating, 0)),
        r.review_count        = toInteger(coalesce(row.review_count, 0)),
        r.open_hours          = row.open_hours,
        r.open_hours_monday   = row.open_hours_monday,
        r.open_hours_tuesday  = row.open_hours_tuesday,
        r.open_hours_wednesday = row.open_hours_wednesday,
        r.open_hours_thursday = row.open_hours_thursday,
        r.open_hours_friday   = row.open_hours_friday,
        r.open_hours_saturday = row.open_hours_saturday,
        r.open_hours_sunday   = row.open_hours_sunday,
        r.price_range         = row.price_range,
        r.has_toilet          = toBoolean(toInteger(row.has_toilet)),
        r.wheelchair_accessible = toBoolean(toInteger(row.wheelchair_accessible)),
        r.good_for_kids       = toBoolean(toInteger(row.good_for_kids)),
        r.outdoor_seating     = toBoolean(toInteger(row.outdoor_seating)),
        r.delivery_available  = toBoolean(toInteger(row.delivery_available)),
        r.dine_in             = toBoolean(toInteger(row.dine_in)),
        r.great_coffee        = toBoolean(toInteger(row.great_coffee)),
        r.great_food          = toBoolean(toInteger(row.great_food)),
        r.cash_only           = toBoolean(toInteger(row.cash_only)),
        r.google_maps_url     = row.google_maps_url,
        r.source              = row.source,
        r.popularity_score    = toFloat(coalesce(row.popularity_score, 0))
    """

    city_query = """
    UNWIND $rows AS row
    MERGE (c:City {name: row.city})
    SET c.state = row.state, c.country = 'Indonesia', c.region = row.region
    WITH c, row
    MATCH (r:Restaurant {restaurant_id: row.restaurant_id})
    MERGE (r)-[:LOCATED_IN]->(c)
    """

    logger.info(f"Importing {len(rows)} restaurants/cafes...")
    batch_import(client, rest_query, rows, "Restaurants")
    batch_import(client, city_query, rows, "City links (restaurants)")
    return len(rows)


def import_connections(client: Neo4jClient) -> int:
    path = IMPORT_DIR / 'destination_connections.csv'
    if not path.exists():
        logger.error(f"File tidak ditemukan: {path}")
        return 0

    df = pd.read_csv(path).fillna('')
    rows = df.to_dict('records')

    query = """
    UNWIND $rows AS row
    MATCH (d1:Destination {destination_id: row.from_destination_id})
    MATCH (d2:Destination {destination_id: row.to_destination_id})
    MERGE (d1)-[r:CONNECTED_TO]->(d2)
    SET r.distance_km           = toFloat(row.distance_km),
        r.duration_minutes_car  = toInteger(row.duration_minutes_car),
        r.duration_minutes_bike = toInteger(row.duration_minutes_bike),
        r.transport_mode        = row.transport_mode
    """

    logger.info(f"Importing {len(rows)} connections...")
    batch_import(client, query, rows, "Connections")
    return len(rows)


def link_restaurants_to_destinations(client: Neo4jClient):
    """Link restoran ke destinasi terdekat (radius 3 km) via spatial query."""
    query = """
    MATCH (r:Restaurant)
    WHERE r.latitude IS NOT NULL AND r.longitude IS NOT NULL
    MATCH (d:Destination)
    WHERE d.latitude IS NOT NULL AND d.longitude IS NOT NULL
    WITH r, d,
         point.distance(
             point({latitude: r.latitude, longitude: r.longitude}),
             point({latitude: d.latitude, longitude: d.longitude})
         ) AS dist_m
    WHERE dist_m < 3000
    MERGE (r)-[rel:NEAR]->(d)
    SET rel.distance_km = round(dist_m / 10.0) / 100
    RETURN count(*) AS links_created
    """
    try:
        result = client.run_query(query)
        links = result[0]['links_created'] if result else 0
        logger.info(f"Restaurant-Destination links dibuat: {links}")
    except Exception as e:
        logger.error(f"Error linking restaurants: {str(e)}")


def main():
    logger.info("Connecting to Neo4j...")
    try:
        client = Neo4jClient()
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {str(e)}")
        return

    try:
        n_dest = import_destinations(client)
        n_rest = import_restaurants(client)
        n_conn = import_connections(client)

        if n_dest > 0 and n_rest > 0:
            logger.info("Linking restaurants ke destinations terdekat...")
            link_restaurants_to_destinations(client)

        logger.info("Creating indexes...")
        client.create_indexes()

        logger.info("=" * 50)
        logger.info("Import complete!")
        logger.info(f"  Destinations : {n_dest}")
        logger.info(f"  Restaurants  : {n_rest}")
        logger.info(f"  Connections  : {n_conn}")
        logger.info("=" * 50)

    finally:
        client.close()


if __name__ == "__main__":
    main()
