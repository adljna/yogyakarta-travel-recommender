"""Cypher queries untuk Graph-RAG retrieval dari data Google Maps."""

import logging
from typing import Dict, List, Any, Optional
from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphQueries:
    """Cypher queries untuk itinerary generation berbasis data Google Maps."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    # Mapping interest user → kategori Google Maps
    # "Tourist attraction" dimasukkan di hampir semua kategori karena sangat generic
    INTEREST_TO_CATEGORIES = {
        'Culture': [
            'Tourist attraction', 'Historical landmark', 'Museum',
            'Cultural landmark', 'Historical place', 'Heritage preservation',
            'Art gallery', 'Art museum', 'Art center', 'Art studio',
            'Cultural center', 'Cultural association',
            'Heritage museum', 'Army museum', 'History museum',
            'Handicraft museum', 'Science museum',
            'Monument', 'Shrine',
            'Hindu temple', 'Buddhist temple', 'Mosque',
            'Craft store', 'Handicraft', 'Pottery store', 'Batik clothing store',
            'Traditional market', 'Market', 'Souvenir store',
            'Stage', 'Convention center',
        ],
        'Culinary': [
            'Coffee shop', 'Restaurant', 'Cafe', 'Noodle shop',
            'Indonesian restaurant', 'Javanese restaurant', 'Central Javanese restaurant',
            'East Javanese restaurant', 'Sundanese restaurant',
            'Satay restaurant', 'Soto restaurant', 'Soto ayam restaurant',
            'Diner', 'Family restaurant', 'Brunch restaurant',
            'Ikan bakar restaurant', 'Pecel lele restaurant',
            'Chicken restaurant', 'Seafood restaurant', 'Nasi restaurant',
            'Nasi goreng restaurant', 'Bakso restaurant',
            'Ramen restaurant', 'Fusion restaurant', 'European restaurant',
            'Barbecue restaurant', 'Breakfast restaurant',
            'Bakery', 'Pastry shop', 'Cake shop', 'Deli', 'Snack bar',
            'Ice cream shop', 'Dessert shop', 'Food court',
            'Hawker stall', 'Soup kitchen', 'Soup shop',
            'Coffee roastery', 'Coffee stand', 'Art cafe',
        ],
        'Nature': [
            'Tourist attraction', 'Park', 'City park', 'National reserve',
            'Nature preserve', 'Botanical garden', 'Garden', 'Community garden',
            'Hiking area', 'Mountain peak', 'National forest', 'Scenic spot',
            'Ecological park', 'Zoo', 'Campground',
        ],
        'Beach': [
            'Tourist attraction', 'Beach', 'Public beach',
            'Resort hotel', 'Resort',
        ],
        'Adventure': [
            'Tourist attraction', 'Amusement park', 'Theme park',
            'Raft trip outfitter', 'Rafting', 'Off roading area',
            'Hiking area', 'Mountain peak', 'Campground', 'Zoo',
            'Indoor playground', 'Recreation center', 'Playground',
            'Outdoor activity organiser',
        ],
        'Spiritual': [
            'Tourist attraction', 'Hindu temple', 'Buddhist temple',
            'Mosque', 'Shrine', 'Historical landmark',
            'Monument', 'Cultural landmark',
        ],
        'Shopping': [
            'Shopping mall', 'Market', 'Traditional market', 'Flea market',
            'Craft store', 'Souvenir store', 'Batik clothing store',
            'Clothing store', 'Boutique', 'Gift shop',
            'Pottery store', 'Handicraft',
        ],
    }

    def find_destinations_by_interest(
        self,
        region: str,
        interests: List[str],
        min_rating: float = 3.5,
        good_for_kids: bool = False,
        needs_wheelchair: bool = False,
        max_results: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Fetch destinations dari graph berdasarkan region, interest, dan filter preferensi.
        Sort: review_rating DESC, review_count DESC (destinasi paling populer & terbaik di atas).
        """
        # Kumpulkan semua kategori yang relevan dengan interests user
        expanded_categories = []
        for interest in interests:
            expanded_categories.extend(
                self.INTEREST_TO_CATEGORIES.get(interest, [interest])
            )
        # Hilangkan duplikat, pertahankan urutan
        seen = set()
        categories = [c for c in expanded_categories if not (c in seen or seen.add(c))]

        # Jika interests kosong → ambil semua tanpa filter kategori
        use_category_filter = bool(categories)

        query = """
        MATCH (d:Destination)
        WHERE d.region = $region
          AND d.review_rating >= $min_rating
          AND ($good_for_kids = false OR d.good_for_kids = true)
          AND ($needs_wheelchair = false OR d.wheelchair_accessible = true)
        """ + ("""
          AND EXISTS {
              MATCH (d)-[:HAS_CATEGORY]->(cat:Category)
              WHERE cat.name IN $categories
          }
        """ if use_category_filter else "") + """
        RETURN
          d.destination_id        AS id,
          d.name                  AS name,
          d.category              AS category,
          d.latitude              AS latitude,
          d.longitude             AS longitude,
          d.city                  AS city,
          d.borough               AS borough,
          d.review_rating         AS review_rating,
          d.review_count          AS review_count,
          d.open_hours            AS open_hours,
          d.open_hours_monday     AS open_hours_monday,
          d.open_hours_tuesday    AS open_hours_tuesday,
          d.open_hours_wednesday  AS open_hours_wednesday,
          d.open_hours_thursday   AS open_hours_thursday,
          d.open_hours_friday     AS open_hours_friday,
          d.open_hours_saturday   AS open_hours_saturday,
          d.open_hours_sunday     AS open_hours_sunday,
          d.price_range           AS price_range,
          d.has_toilet            AS has_toilet,
          d.has_restaurant        AS has_restaurant,
          d.wheelchair_accessible AS wheelchair_accessible,
          d.good_for_kids         AS good_for_kids,
          d.has_parking           AS has_parking,
          d.has_free_parking      AS has_free_parking,
          d.requires_appointment  AS requires_appointment,
          d.tickets_in_advance    AS tickets_in_advance,
          d.google_maps_url       AS google_maps_url,
          d.popularity_score      AS popularity_score
        ORDER BY d.review_rating DESC, d.review_count DESC
        LIMIT $max_results
        """

        params = {
            'region': region,
            'min_rating': min_rating,
            'good_for_kids': good_for_kids,
            'needs_wheelchair': needs_wheelchair,
            'categories': categories,
            'max_results': max_results,
        }

        return self.client.run_query(query, params)

    def find_nearby_restaurants(
        self,
        destination_id: str,
        min_rating: float = 3.5,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Cari restoran/cafe dalam radius 3 km dari sebuah destinasi."""
        query = """
        MATCH (d:Destination {destination_id: $destination_id})
        MATCH (r:Restaurant)-[rel:NEAR]->(d)
        WHERE r.review_rating >= $min_rating
        RETURN
          r.restaurant_id      AS restaurant_id,
          r.name               AS name,
          r.category           AS category,
          r.city               AS city,
          r.review_rating      AS review_rating,
          r.review_count       AS review_count,
          r.open_hours         AS open_hours,
          r.price_range        AS price_range,
          r.outdoor_seating    AS outdoor_seating,
          r.dine_in            AS dine_in,
          r.delivery_available AS delivery_available,
          r.great_coffee       AS great_coffee,
          r.great_food         AS great_food,
          r.google_maps_url    AS google_maps_url,
          rel.distance_km      AS distance_km
        ORDER BY r.review_rating DESC, r.review_count DESC
        LIMIT $max_results
        """
        return self.client.run_query(query, {
            'destination_id': destination_id,
            'min_rating': min_rating,
            'max_results': max_results,
        })

    def find_restaurants_in_region(
        self,
        region: str,
        min_rating: float = 3.5,
        max_results: int = 15,
    ) -> List[Dict[str, Any]]:
        """Cari restoran/cafe terbaik di region tanpa harus dekat destinasi tertentu."""
        query = """
        MATCH (r:Restaurant)
        WHERE r.region = $region
          AND r.review_rating >= $min_rating
        RETURN
          r.restaurant_id      AS restaurant_id,
          r.name               AS name,
          r.category           AS category,
          r.city               AS city,
          r.latitude           AS latitude,
          r.longitude          AS longitude,
          r.review_rating      AS review_rating,
          r.review_count       AS review_count,
          r.open_hours         AS open_hours,
          r.price_range        AS price_range,
          r.outdoor_seating    AS outdoor_seating,
          r.great_coffee       AS great_coffee,
          r.great_food         AS great_food,
          r.google_maps_url    AS google_maps_url,
          r.popularity_score   AS popularity_score
        ORDER BY r.review_rating DESC, r.review_count DESC
        LIMIT $max_results
        """
        return self.client.run_query(query, {
            'region': region,
            'min_rating': min_rating,
            'max_results': max_results,
        })

    def get_route_between_destinations(
        self,
        from_id: str,
        to_id: str,
    ) -> List[Dict[str, Any]]:
        """Dapatkan info jarak dan durasi antara dua destinasi."""
        query = """
        MATCH (d1:Destination {destination_id: $from_id})
        MATCH (d2:Destination {destination_id: $to_id})
        MATCH (d1)-[r:CONNECTED_TO]->(d2)
        RETURN
          r.distance_km           AS distance_km,
          r.duration_minutes_car  AS duration_minutes_car,
          r.duration_minutes_bike AS duration_minutes_bike,
          r.transport_mode        AS transport_mode
        """
        return self.client.run_query(query, {'from_id': from_id, 'to_id': to_id})

    def get_top_rated_destinations(
        self,
        region: str,
        min_review_count: int = 50,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Top-rated destinations dengan review count signifikan (menghindari tempat obscure)."""
        query = """
        MATCH (d:Destination)
        WHERE d.region = $region
          AND d.review_count >= $min_review_count
        RETURN
          d.destination_id AS id,
          d.name           AS name,
          d.category       AS category,
          d.review_rating  AS review_rating,
          d.review_count   AS review_count,
          d.open_hours     AS open_hours,
          d.price_range    AS price_range,
          d.good_for_kids  AS good_for_kids,
          d.has_parking    AS has_parking,
          d.popularity_score AS popularity_score
        ORDER BY d.popularity_score DESC
        LIMIT $limit
        """
        return self.client.run_query(query, {
            'region': region,
            'min_review_count': min_review_count,
            'limit': limit,
        })

    def full_graph_rag_retrieval(
        self,
        region: str,
        interests: List[str],
        start_date: str,
        end_date: str,
        min_rating: float = 3.5,
        avoid_preferences: Optional[List[str]] = None,
        good_for_kids: bool = False,
        needs_wheelchair: bool = False,
        include_culinary: bool = True,
    ) -> Dict[str, Any]:
        """
        Full Graph-RAG retrieval: destinations + restaurants terdekat + top picks.

        Returns dict dengan keys:
          - destinations: list dest dengan nearby_restaurants
          - top_picks: top rated dengan banyak review (social proof)
          - culinary_spots: restoran terbaik di region (jika include_culinary)
          - metadata: info retrieval
        """
        if avoid_preferences is None:
            avoid_preferences = []

        try:
            # Destinations berdasarkan interest
            destinations = self.find_destinations_by_interest(
                region=region,
                interests=interests,
                min_rating=min_rating,
                good_for_kids=good_for_kids,
                needs_wheelchair=needs_wheelchair,
            )

            # Enrich setiap destinasi dengan restoran terdekat
            for dest in destinations:
                dest['nearby_restaurants'] = self.find_nearby_restaurants(
                    destination_id=dest['id'],
                    min_rating=min_rating - 0.5,
                )

            # Top picks berdasarkan popularitas (untuk rekomendasi "must visit")
            top_picks = self.get_top_rated_destinations(region=region)

            # Kuliner terbaik di region (jika user interest kuliner atau include_culinary)
            culinary_spots = []
            if include_culinary or 'Culinary' in interests:
                culinary_spots = self.find_restaurants_in_region(
                    region=region,
                    min_rating=min_rating - 0.5,
                )

            context = {
                'destinations': destinations,
                'top_picks': top_picks,
                'culinary_spots': culinary_spots,
                'weather': [],   # placeholder – BMKG integration future
                'events': [],    # placeholder – event integration future
                'metadata': {
                    'region': region,
                    'interests': interests,
                    'date_range': f"{start_date} to {end_date}",
                    'min_rating': min_rating,
                    'good_for_kids': good_for_kids,
                    'needs_wheelchair': needs_wheelchair,
                    'data_source': 'Google Maps (scraped)',
                    'total_destinations_found': len(destinations),
                    'total_culinary_found': len(culinary_spots),
                }
            }

            logger.info(
                f"Graph RAG: {len(destinations)} dest, "
                f"{len(top_picks)} top picks, "
                f"{len(culinary_spots)} culinary"
            )
            return context

        except Exception as e:
            logger.error(f"Error dalam full_graph_rag_retrieval: {str(e)}")
            return {'destinations': [], 'top_picks': [], 'culinary_spots': [],
                    'weather': [], 'events': [], 'error': str(e)}
