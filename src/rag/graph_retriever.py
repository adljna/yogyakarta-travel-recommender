"""Graph retrieval untuk fetch context dari Neo4j."""

import logging
from typing import Dict, Any

from src.database import Neo4jClient, GraphQueries

logger = logging.getLogger(__name__)


class GraphRetriever:
    """Retrieve context dari Neo4j graph untuk itinerary generation."""

    def __init__(self, neo4j_client: Neo4jClient):
        self.client = neo4j_client
        self.queries = GraphQueries(neo4j_client)

    def retrieve_context(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve semua data relevan dari graph untuk generate itinerary.

        Args:
            constraints: User constraints dari questionnaire

        Returns:
            dict: Graph context dengan destinations, culinary, top_picks, dll
        """
        try:
            region = constraints.get('destination_area', 'Yogyakarta')
            interests = constraints.get('interests', [])
            start_date = constraints['travel_dates']['start_date']
            end_date = constraints['travel_dates']['end_date']
            min_rating = constraints.get('min_rating', 3.5)
            avoid = constraints.get('avoid_preferences', [])
            good_for_kids = constraints.get('good_for_kids', False)
            needs_wheelchair = constraints.get('needs_wheelchair', False)
            include_culinary = (
                'Culinary' in interests
                or constraints.get('include_culinary', True)
            )

            logger.info(f"Retrieving graph context untuk {region}...")

            context = self.queries.full_graph_rag_retrieval(
                region=region,
                interests=interests,
                start_date=start_date,
                end_date=end_date,
                min_rating=min_rating,
                avoid_preferences=avoid,
                good_for_kids=good_for_kids,
                needs_wheelchair=needs_wheelchair,
                include_culinary=include_culinary,
            )

            context['constraints'] = constraints

            total_dest = len(context.get('destinations', []))
            total_cul = len(context.get('culinary_spots', []))
            logger.info(f"Context: {total_dest} destinations, {total_cul} culinary spots")

            return context

        except Exception as e:
            logger.error(f"Error retrieving graph context: {str(e)}")
            return {
                'destinations': [],
                'top_picks': [],
                'culinary_spots': [],
                'weather': [],
                'events': [],
                'error': str(e),
            }
