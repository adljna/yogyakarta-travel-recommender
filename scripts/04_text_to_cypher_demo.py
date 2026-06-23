#!/usr/bin/env python3
"""
Menunjukkan bagaimana LLM mengubah pertanyaan natural language
menjadi Cypher query, mengeksekusinya ke Neo4j, dan menjelaskan hasilnya.

Usage:
    python scripts/05_text_to_cypher_demo.py
    python scripts/05_text_to_cypher_demo.py "Mana saja museum di Yogyakarta?"
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from src.rag.text_to_cypher import TextToCypherConverter
from src.database import Neo4jClient

logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")

BANNER = """
╔══════════════════════════════════════════════════╗
║   Text-to-Cypher Demo                  ║
║   Natural Language → Cypher → Neo4j → Jawaban   ║
╚══════════════════════════════════════════════════╝
"""

# Contoh pertanyaan demonstrasi
DEMO_QUESTIONS = [
    "Tampilkan destinasi wisata dengan rating di atas 4.5 di Yogyakarta",
    "Restoran apa saja yang dekat dengan destinasi wisata populer?",
    "Mana destinasi yang cocok untuk anak-anak di Yogyakarta?",
    "Berapa jarak antara Borobudur dan Prambanan?",
    "Tampilkan 10 tempat wisata paling populer berdasarkan jumlah ulasan",
]


def run_single_query(question: str, converter: TextToCypherConverter):
    print(f"\n{'='*60}")
    print(f"PERTANYAAN: {question}")
    print("="*60)

    result = converter.convert_and_execute(question)

    print(f"\n[Cypher yang di-generate LLM]")
    print("-" * 40)
    print(result["cypher"])

    if result["error"]:
        print(f"\n[ERROR] {result['error']}")
    else:
        print(f"\n[Hasil] {len(result['results'])} baris data")
        if result["results"]:
            # Tampilkan maksimal 5 hasil
            for i, row in enumerate(result["results"][:5], 1):
                print(f"  {i}. {json.dumps(row, ensure_ascii=False)}")
            if len(result["results"]) > 5:
                print(f"  ... dan {len(result['results']) - 5} baris lainnya")

    print(f"\n[Penjelasan dari LLM]")
    print("-" * 40)
    print(result["explanation"])


def main():
    print(BANNER)

    try:
        neo4j = Neo4jClient()
        print("✓ Terhubung ke Neo4j\n")
    except Exception as e:
        print(f"✗ Gagal koneksi ke Neo4j: {e}")
        print("Pastikan Neo4j running di localhost:7687")
        return

    converter = TextToCypherConverter(neo4j_client=neo4j)

    if len(sys.argv) > 1:
        # Mode: pertanyaan dari argumen CLI
        question = " ".join(sys.argv[1:])
        run_single_query(question, converter)
    else:
        # Mode: demo dengan pertanyaan bawaan
        print("Menjalankan demo dengan beberapa pertanyaan contoh...\n")
        print("(Atau jalankan dengan argumen: python 05_text_to_cypher_demo.py 'pertanyaan Anda')\n")

        for question in DEMO_QUESTIONS:
            run_single_query(question, converter)

        # Mode interaktif setelah demo
        print(f"\n{'='*60}")
        print("SESI INTERAKTIF — Ketik pertanyaan Anda (atau 'keluar' untuk berhenti)")
        print("="*60)
        while True:
            try:
                user_input = input("\nPertanyaan: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if user_input.lower() in ("keluar", "exit", "quit", "q"):
                break
            if not user_input:
                continue
            run_single_query(user_input, converter)

    neo4j.close()
    print("\nSelesai.")


if __name__ == "__main__":
    main()
