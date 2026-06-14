#!/usr/bin/env python3
"""
End-to-end demo: user input -> extract constraints -> retrieve from graph -> generate itinerary.

Usage:
    python scripts/03_generate_itinerary_demo.py
"""

import sys
import logging
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from src.database import Neo4jClient
from src.rag import GraphRetriever, LLMClient, run_questionnaire

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    try:
        # Step 1: Kumpulkan preferensi via questionnaire
        constraints = run_questionnaire()
        logger.info(f"Constraints: {json.dumps(constraints, indent=2, ensure_ascii=False)}")
        
        # Step 2: Retrieve dari graph
        logger.info("\nSTEP 2: Retrieving context dari Neo4j...")
        neo4j_client = Neo4jClient()
        retriever = GraphRetriever(neo4j_client)
        graph_context = retriever.retrieve_context(constraints)
        
        logger.info(f"Retrieved {len(graph_context.get('destinations', []))} destinations")
        logger.info(f"Retrieved {len(graph_context.get('weather', []))} weather records")
        logger.info(f"Retrieved {len(graph_context.get('events', []))} events")
        
        # Step 3: Generate itinerary
        logger.info("\nSTEP 3: Generating itinerary via LLM...")
        llm_client = LLMClient()
        itinerary = llm_client.generate_itinerary(constraints, graph_context)
        
        logger.info("Itinerary generated successfully!")
        
        # Save to file
        output_file = Path("output_itinerary.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(itinerary)
        logger.info(f"Itinerary saved to: {output_file}")

        # Print ke console (handle karakter unicode yang tidak didukung Windows terminal)
        logger.info("\n" + "=" * 70)
        logger.info("GENERATED ITINERARY")
        logger.info("=" * 70)
        safe_output = itinerary.encode('ascii', errors='replace').decode('ascii')
        print(safe_output)
        
        neo4j_client.close()
    
    except Exception as e:
        logger.error(f"Error dalam itinerary generation: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
