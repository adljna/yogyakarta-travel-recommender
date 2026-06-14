"""
Project configuration management menggunakan Pydantic Settings.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings untuk itinerary recommendation system."""
    
    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "itinerary"

    # API Keys
    google_places_api_key: str = ""
    openrouter_api_key: str = ""
    wikidata_sparql_endpoint: str = "https://query.wikidata.org/sparql"

    # Region Configuration
    region: str = "yogyakarta"

    # Paths
    raw_data_path: str = "data/raw"
    processed_data_path: str = "data/processed"
    neo4j_import_path: str = "data/neo4j_imports"

    # LLM Settings (via OpenRouter)
    llm_base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    llm_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    llm_max_tokens: int = 16000
    temperature: float = 0.7

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False

    # Data Collection Settings
    rate_limit_google_places: int = 100
    batch_size_wikidata: int = 1000
    google_places_retry_max: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def raw_data_path_obj(self) -> Path:
        return Path(self.raw_data_path)
    
    @property
    def processed_data_path_obj(self) -> Path:
        return Path(self.processed_data_path)
    
    @property
    def neo4j_import_path_obj(self) -> Path:
        return Path(self.neo4j_import_path)


# Load settings on import
settings = Settings()
