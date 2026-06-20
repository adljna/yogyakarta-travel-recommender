#!/usr/bin/env python3
"""
Process data dari wisata_jogja_clean.csv (hasil Google Maps scraping)
menjadi format siap import Neo4j.

Menghasilkan di data/neo4j_imports/:
  - destinations.csv   (tempat wisata)
  - restaurants.csv    (restoran, cafe, coffee shop)
  - destination_connections.csv (jarak antar destinasi)

Usage:
    python scripts/02_process_data.py
"""

import sys
import logging
import json
import math
import re
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SOURCE_CSV = Path("data/wisata_jogja_clean.csv")
IMPORT_PATH = Path(settings.neo4j_import_path)

# Kata kunci substring untuk menandakan tempat makan/minum
RESTAURANT_KEYWORDS = (
    'restaurant', 'cafe', 'coffee', 'bakery', 'bar', 'grill', 'kitchen',
    'deli', 'buffet', 'bistro', 'eatery', 'food court', 'snack bar',
    'dessert', 'ice cream', 'cake shop', 'pastry shop', 'soup shop',
    'soup kitchen', 'hawker', 'warung', 'karaoke bar', 'art cafe',
    'coffee roastery', 'coffee stand', 'noodle', 'diner',
)

# Kategori non-wisata — exact match (agar tidak menimpa sub-kategori seperti 'Batik clothing store')
EXCLUDE_EXACT_CATEGORIES = {
    'car rental agency', 'coworking space', 'corporate office',
    'transportation service', 'motorcycle rental agency',
    'bus stop', 'bus ticket agency', 'government office',
    'train station', 'bus station', 'bus company',
    'virtual office rental', 'design agency', 'media company',
    'association / organization', 'preschool', 'education center',
    'catering food and drink supplier', 'food producer',
    'food and beverage exporter', 'food manufacturing supply',
    'event technology service', 'e-commerce service',
    'make-up artist', 'embroidery service', 'alternative fuel station',
    'state government office', 'clothing store', 'store',
    'office', 'office space rental agency', 'social worker',
    'recording studio', 'building', 'cell phone store',
    'cell phone accessory store', 'home goods store',
    'home improvement store', 'school supply store',
    'supermarket', 'hypermarket', 'grocery store',
    'wholesale market', 'anganwadi center',
}


def is_restaurant_category(category: str) -> bool:
    cat_lower = category.lower()
    return any(kw in cat_lower for kw in RESTAURANT_KEYWORDS)


def is_excluded_category(category: str) -> bool:
    return category.lower().strip() in EXCLUDE_EXACT_CATEGORIES


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def parse_address(addr_str: str) -> dict:
    try:
        addr = json.loads(addr_str) if addr_str and addr_str.strip() not in ('', '{}') else {}
    except (json.JSONDecodeError, TypeError):
        addr = {}
    return {
        'city': (addr.get('city') or '').strip() or 'Yogyakarta',
        'borough': (addr.get('borough') or '').strip(),
        'street': (addr.get('street') or '').strip(),
        'postal_code': (addr.get('postal_code') or '').strip(),
        'state': (addr.get('state') or '').strip() or 'Special Region of Yogyakarta',
    }


def parse_open_hours(hours_str: str) -> tuple[str, dict]:
    """
    Return: (formatted_string, per_day_dict)
    per_day_dict keys: Monday, Tuesday, ..., Sunday
    """
    try:
        hours = json.loads(hours_str) if hours_str and hours_str.strip() not in ('', '{}') else {}
    except (json.JSONDecodeError, TypeError):
        hours = {}

    if not hours:
        return '', {}

    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_abbr = {'Monday': 'Sen', 'Tuesday': 'Sel', 'Wednesday': 'Rab',
                'Thursday': 'Kam', 'Friday': 'Jum', 'Saturday': 'Sab', 'Sunday': 'Min'}

    per_day = {}
    for day in day_order:
        if day in hours:
            times = hours[day]
            per_day[day] = ', '.join(times) if isinstance(times, list) else str(times)

    if not per_day:
        return '', {}

    # Buat format ringkas
    unique_times = set(per_day.values())
    if len(unique_times) == 1:
        formatted = f"Setiap hari: {list(unique_times)[0]}"
    else:
        parts = [f"{day_abbr.get(d, d)}: {per_day[d]}" for d in day_order if d in per_day]
        formatted = ' | '.join(parts)

    return formatted, per_day


def parse_about(about_str: str) -> dict:
    """Parse JSON about field menjadi boolean amenity flags."""
    defaults = {
        'has_toilet': 0,
        'has_restaurant': 0,
        'wheelchair_accessible': 0,
        'good_for_kids': 0,
        'good_for_kids_birthday': 0,
        'has_parking': 0,
        'has_free_parking': 0,
        'requires_appointment': 0,
        'tickets_in_advance': 0,
        'outdoor_seating': 0,
        'delivery_available': 0,
        'dine_in': 0,
        'great_coffee': 0,
        'great_food': 0,
        'cash_only': 0,
    }

    try:
        about = json.loads(about_str) if about_str and about_str.strip() not in ('', '[]') else []
    except (json.JSONDecodeError, TypeError):
        about = []

    if not isinstance(about, list):
        return defaults

    for group in about:
        for opt in group.get('options', []):
            if not opt.get('enabled', False):
                continue
            name = opt.get('name', '').lower()

            if 'toilet' in name:
                defaults['has_toilet'] = 1
            if name == 'restaurant':
                defaults['has_restaurant'] = 1
            if 'wheelchair' in name:
                defaults['wheelchair_accessible'] = 1
            if name == 'good for kids':
                defaults['good_for_kids'] = 1
            if name == 'good for kids birthday':
                defaults['good_for_kids_birthday'] = 1
            if 'parking' in name:
                defaults['has_parking'] = 1
            if 'free' in name and 'parking' in name:
                defaults['has_free_parking'] = 1
            if name == 'appointment required':
                defaults['requires_appointment'] = 1
            if 'tickets in advance' in name:
                defaults['tickets_in_advance'] = 1
            if name == 'outdoor seating':
                defaults['outdoor_seating'] = 1
            if name == 'delivery':
                defaults['delivery_available'] = 1
            if name == 'dine-in':
                defaults['dine_in'] = 1
            if name == 'great coffee':
                defaults['great_coffee'] = 1
            if any(x in name for x in ('great food', 'great dessert', 'must try')):
                defaults['great_food'] = 1
            if name == 'cash only':
                defaults['cash_only'] = 1

    return defaults


def sanitize_id(data_id_str: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]', '_', str(data_id_str))
    return cleaned[:80]


def popularity_score(rating: float, review_count: int) -> float:
    """Score 0-1: kombinasi rating (60%) dan popularitas review (40%)."""
    if not rating:
        return 0.0
    log_count = math.log10(max(review_count, 1))
    score = (rating / 5.0) * 0.6 + min(log_count / 5.0, 1.0) * 0.4
    return round(score, 4)


def build_records(df: pd.DataFrame) -> tuple[list, list]:
    destinations = []
    restaurants = []

    for i, row in df.iterrows():
        category = str(row.get('category', '')).strip()

        # Skip kategori non-wisata
        if is_excluded_category(category):
            continue

        is_restaurant = is_restaurant_category(category)

        addr = parse_address(str(row.get('complete_address', '')))
        open_hours_str, open_hours_per_day = parse_open_hours(str(row.get('open_hours', '')))
        amenities = parse_about(str(row.get('about', '')))

        data_id = str(row.get('data_id', ''))
        name = str(row.get('title', '')).strip()

        rec_id = sanitize_id(data_id) if (data_id and data_id not in ('nan', '')) else f"gmap_{i:05d}"

        try:
            rating = float(row.get('review_rating') or 0)
        except (ValueError, TypeError):
            rating = 0.0

        try:
            review_count = int(float(row.get('review_count') or 0))
        except (ValueError, TypeError):
            review_count = 0

        price_range = str(row.get('price_range') or '').strip()
        city = addr['city']

        base = {
            'name': name,
            'category': category,
            'latitude': float(row.get('latitude') or 0),
            'longitude': float(row.get('longitude') or 0),
            'city': city,
            'borough': addr['borough'],
            'street': addr['street'],
            'postal_code': addr['postal_code'],
            'state': addr['state'],
            'region': 'Yogyakarta',
            'review_rating': rating,
            'review_count': review_count,
            'open_hours': open_hours_str,
            'open_hours_monday': open_hours_per_day.get('Monday', ''),
            'open_hours_tuesday': open_hours_per_day.get('Tuesday', ''),
            'open_hours_wednesday': open_hours_per_day.get('Wednesday', ''),
            'open_hours_thursday': open_hours_per_day.get('Thursday', ''),
            'open_hours_friday': open_hours_per_day.get('Friday', ''),
            'open_hours_saturday': open_hours_per_day.get('Saturday', ''),
            'open_hours_sunday': open_hours_per_day.get('Sunday', ''),
            'price_range': price_range,
            **amenities,
            'google_maps_url': str(row.get('link', '')),
            'source': 'google_maps',
            'popularity_score': popularity_score(rating, review_count),
        }

        if is_restaurant:
            base['restaurant_id'] = rec_id
            restaurants.append(base)
        else:
            base['destination_id'] = rec_id
            destinations.append(base)

    return destinations, restaurants


def build_connections(dest_records: list, max_distance_km: float = 30.0, max_per_dest: int = 8) -> list:
    rows = []
    valid = [r for r in dest_records if r['latitude'] and r['longitude']]

    for i, src in enumerate(valid):
        neighbors = []
        for j, tgt in enumerate(valid):
            if i == j:
                continue
            d = haversine_km(src['latitude'], src['longitude'], tgt['latitude'], tgt['longitude'])
            if d <= max_distance_km:
                neighbors.append((d, tgt['destination_id']))

        neighbors.sort(key=lambda x: x[0])
        for dist_km, tgt_id in neighbors[:max_per_dest]:
            rows.append({
                'from_destination_id': src['destination_id'],
                'to_destination_id': tgt_id,
                'distance_km': round(dist_km, 2),
                'duration_minutes_car': round(dist_km / 40 * 60),
                'duration_minutes_bike': round(dist_km / 15 * 60),
                'transport_mode': 'car',
            })
    return rows


def main():
    if not SOURCE_CSV.exists():
        logger.error(f"File tidak ditemukan: {SOURCE_CSV}")
        logger.error("Pastikan wisata_jogja_clean.csv ada di folder data/")
        return

    logger.info(f"Reading {SOURCE_CSV} ...")
    df = pd.read_csv(SOURCE_CSV, low_memory=False)
    df = df.fillna('')

    # Bersihkan data
    df = df[df['title'].astype(str).str.strip().ne('')]
    df = df[df['latitude'].astype(str).ne('') & df['longitude'].astype(str).ne('')]
    df = df.drop_duplicates(subset=['title'], keep='first')
    df = df.reset_index(drop=True)
    logger.info(f"Rows setelah cleaning: {len(df)}")

    IMPORT_PATH.mkdir(parents=True, exist_ok=True)

    dest_records, rest_records = build_records(df)
    logger.info(f"Destinations (wisata): {len(dest_records)}")
    logger.info(f"Restaurants/Cafes:     {len(rest_records)}")

    conn_records = build_connections(dest_records)
    logger.info(f"Connections:           {len(conn_records)}")

    dest_df = pd.DataFrame(dest_records)
    rest_df = pd.DataFrame(rest_records)
    conn_df = pd.DataFrame(conn_records)

    dest_out = IMPORT_PATH / 'destinations.csv'
    rest_out = IMPORT_PATH / 'restaurants.csv'
    conn_out = IMPORT_PATH / 'destination_connections.csv'

    dest_df.to_csv(dest_out, index=False, encoding='utf-8')
    rest_df.to_csv(rest_out, index=False, encoding='utf-8')
    conn_df.to_csv(conn_out, index=False, encoding='utf-8')

    logger.info(f"Saved → {dest_out}")
    logger.info(f"Saved → {rest_out}")
    logger.info(f"Saved → {conn_out}")
    logger.info("Done! Siap untuk 03_import_to_neo4j.py")


if __name__ == "__main__":
    main()
