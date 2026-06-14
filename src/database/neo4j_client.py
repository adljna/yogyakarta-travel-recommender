"""Neo4j database client wrapper."""

import logging
from typing import List, Dict, Any
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError

from config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Client untuk Neo4j database operations."""

    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None,
        database: str = None,
    ):
        self.uri = uri or settings.neo4j_uri
        self.username = username or settings.neo4j_username
        self.password = password or settings.neo4j_password
        self.database = database or settings.neo4j_database

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j: {self.uri}")
        except DriverError as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise

    def run_query(
        self,
        query: str,
        params: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        if params is None:
            params = {}
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Query execution error: {str(e)}")
            raise

    def create_indexes(self) -> bool:
        index_queries = [
            # Core lookup indexes
            "CREATE INDEX dest_id IF NOT EXISTS FOR (d:Destination) ON (d.destination_id)",
            "CREATE INDEX rest_id IF NOT EXISTS FOR (r:Restaurant) ON (r.restaurant_id)",
            "CREATE INDEX city_name IF NOT EXISTS FOR (c:City) ON (c.name)",
            "CREATE INDEX category_name IF NOT EXISTS FOR (cat:Category) ON (cat.name)",

            # Filtering indexes – heavily used dalam queries
            "CREATE INDEX dest_region IF NOT EXISTS FOR (d:Destination) ON (d.region)",
            "CREATE INDEX dest_rating IF NOT EXISTS FOR (d:Destination) ON (d.review_rating)",
            "CREATE INDEX dest_popularity IF NOT EXISTS FOR (d:Destination) ON (d.popularity_score)",
            "CREATE INDEX dest_kids IF NOT EXISTS FOR (d:Destination) ON (d.good_for_kids)",
            "CREATE INDEX dest_wheelchair IF NOT EXISTS FOR (d:Destination) ON (d.wheelchair_accessible)",

            "CREATE INDEX rest_region IF NOT EXISTS FOR (r:Restaurant) ON (r.region)",
            "CREATE INDEX rest_rating IF NOT EXISTS FOR (r:Restaurant) ON (r.review_rating)",
            "CREATE INDEX rest_popularity IF NOT EXISTS FOR (r:Restaurant) ON (r.popularity_score)",

            # Fulltext search
            """CREATE FULLTEXT INDEX dest_fulltext IF NOT EXISTS
               FOR (d:Destination) ON EACH [d.name, d.category, d.borough]""",
            """CREATE FULLTEXT INDEX rest_fulltext IF NOT EXISTS
               FOR (r:Restaurant) ON EACH [r.name, r.category, r.borough]""",
        ]

        try:
            with self.driver.session(database=self.database) as session:
                for query in index_queries:
                    session.run(query)
                    logger.info(f"Index: {query[:60]}...")
            return True
        except Exception as e:
            logger.error(f"Index creation error: {str(e)}")
            return False

    def close(self):
        try:
            self.driver.close()
            logger.info("Neo4j connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")
