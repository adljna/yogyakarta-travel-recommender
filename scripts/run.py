#!/usr/bin/env python3
"""
Interactive itinerary generator.

Usage:
    python scripts/run.py
    python scripts/run.py "Buatkan itinerary 2 hari di Yogyakarta..."
"""

import sys
import os
# Pastikan project root ada di sys.path sebelum import apapun
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import json
from pathlib import Path

from config import settings
from src.database import Neo4jClient
from src.rag import ConstraintExtractor, GraphRetriever, LLMClient, run_questionnaire

logging.basicConfig(
    level=logging.WARNING,  # suppress noise, hanya tampilkan WARNING ke atas
    format='%(levelname)s - %(message)s'
)

BANNER = """
╔══════════════════════════════════════════════╗
║   Itinerary Recommendation System           ║
║   Powered by Neo4j + OpenRouter             ║
╚══════════════════════════════════════════════╝
"""

CONTOH = (
    "Contoh: Buatkan itinerary 2 hari di Yogyakarta, "
    "budget hemat (Rp 500rb/hari), suka alam dan kuliner, "
    "perjalanan 20-21 Juli 2024."
)



def main():
    print(BANNER)

    if len(sys.argv) > 1:
        # Mode free-text: python run.py "3 hari di Bali..."
        user_request = " ".join(sys.argv[1:])
        print(f"Mode: free-text\nRequest: {user_request}\n")
        print("[1/3] Mengekstrak preferensi via LLM...")
        extractor = ConstraintExtractor()
        try:
            constraints = extractor.extract(user_request)
        except Exception as e:
            print(f"\nGagal ekstrak constraints: {e}")
            return
        _continue(constraints)
    else:
        # Mode default: guided questionnaire
        constraints = run_questionnaire()
        _continue(constraints)


def _continue(constraints: dict):
    """Lanjutkan pipeline setelah constraints terkumpul."""
    print("\n[2/3] Mengambil data destinasi dari Neo4j...")
    try:
        neo4j = Neo4jClient()
    except Exception as e:
        print(f"\nGagal konek ke Neo4j: {e}")
        print("Pastikan Neo4j running di localhost:7687 dan database 'itinerary' ada.")
        return

    retriever = GraphRetriever(neo4j)
    context = retriever.retrieve_context(constraints)
    n_dest = len(context.get('destinations', []))
    print(f"      Ditemukan {n_dest} destinasi relevan di graph")
    neo4j.close()

    if n_dest == 0:
        print("      WARNING: 0 destinasi — pastikan data sudah diimport via 03_import_to_neo4j.py")

    print("\n[3/3] Membuat itinerary... (bisa 1-2 menit)\n")
    llm = LLMClient()
    try:
        itinerary = llm.generate_itinerary(constraints, context)
    except Exception as e:
        print(f"\nGagal generate itinerary: {e}")
        return

    output_file = Path("output_itinerary.md")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(itinerary)

    print("=" * 60)
    safe = itinerary.encode('ascii', errors='replace').decode('ascii')
    print(safe)
    print("=" * 60)
    print(f"\nItinerary disimpan ke: {output_file.resolve()}")


if __name__ == "__main__":
    main()
