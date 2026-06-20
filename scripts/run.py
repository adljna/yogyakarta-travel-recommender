#!/usr/bin/env python3
"""
Conversational Travel Recommender — Yogyakarta (Tier 4).

Tidak perlu pilih mode — cukup ketik apa yang kamu mau:
  • Ceritakan rencana perjalanan  → sistem buat itinerary otomatis
  • Tanya sesuatu tentang destinasi → langsung cari di graph (Text-to-Cypher)
  • "Tambah data: ..."             → ekstrak entitas ke Neo4j (Graph Builder)

Kalau ada info yang kurang (misal: durasi belum disebut), sistem akan tanya
satu pertanyaan lanjutan — tidak perlu isi form dari awal.

Usage:
    python scripts/run.py                          # conversational loop (default)
    python scripts/run.py "Buatkan itinerary ..."  # langsung generate itinerary
    python scripts/run.py --query "Mana museum?"   # langsung text-to-cypher
    python scripts/run.py --add "Teks wisata ..."  # langsung tambah data ke graph
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import logging
import json
from pathlib import Path

from config import settings
from src.database import Neo4jClient
from src.rag import ConstraintExtractor, GraphRetriever, LLMClient, ask_missing_fields
from src.rag.text_to_cypher import TextToCypherConverter
from src.graph_builder import LLMGraphBuilder

logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")

BANNER = """
╔══════════════════════════════════════════════════╗
║   Yogyakarta Travel Recommender  (Tier 4)       ║
║   Ceritakan rencana atau tanyakan apa saja!     ║
╚══════════════════════════════════════════════════╝
"""

# ── Intent detection ───────────────────────────────────────────────────────

_ITINERARY_KW = (
    "itinerary", "jadwal perjalanan", "rencana perjalanan", "rencanakan",
    "buat jadwal", "trip", "liburan", "hari di yogya", "mau ke yogya",
    "perjalanan ke", "wisata ke", "ajak ke",
)
_ADD_DATA_KW = (
    "tambah data", "masukkan data", "input data", "simpan data",
    "extract dari", "tambahkan info", "catat info",
)
# Sinyal spesifik bahwa user tanya tentang entitas di graph
_GRAPH_QUERY_KW = (
    "restoran", "restaurant", "tempat makan", "kuliner", "museum",
    "hotel", "destinasi apa", "tempat wisata apa", "rekomendasi restoran",
    "rekomendasi tempat makan", "rekomendasikan", "berikan rekomendasi",
    "berikan saya", "cocok untuk", "cocok buat", "yang buka", "rating",
)
_QUESTION_STARTERS = (
    "mana ", "apa ", "berapa ", "di mana", "dimana", "bagaimana ",
    "sebutkan", "tampilkan", "cari ", "ada ", "list ", "tunjukkan",
    "berikan", "rekomendasikan",
)


def detect_intent(text: str) -> str:
    """
    Deteksi intent dari natural language tanpa LLM call.
    Returns: 'itinerary' | 'graph_query' | 'add_data'
    """
    lower = text.lower().strip()

    if any(kw in lower for kw in _ADD_DATA_KW):
        return "add_data"

    # Graph query dicek duluan sebelum itinerary — lebih spesifik
    if any(kw in lower for kw in _GRAPH_QUERY_KW):
        return "graph_query"

    if text.strip().endswith("?") or any(lower.startswith(s) for s in _QUESTION_STARTERS):
        return "graph_query"

    if any(kw in lower for kw in _ITINERARY_KW):
        return "itinerary"

    # Default: itinerary
    return "itinerary"


def _get_neo4j() -> Neo4jClient:
    try:
        return Neo4jClient()
    except Exception as e:
        print(f"\nGagal konek ke Neo4j: {e}")
        print("Pastikan Neo4j running di localhost:7687 dan database 'itinerary' ada.")
        sys.exit(1)


# ──────────────────────────────────────────────
# Intent handlers
# ──────────────────────────────────────────────

def _handle_itinerary(user_input: str):
    """
    Generate itinerary dari natural language.
    Kalau ada info kritis yang kurang, tanya follow-up sebelum lanjut.
    """
    print("\n[1/3] Memahami preferensi Anda...")
    try:
        extractor = ConstraintExtractor()
        constraints = extractor.extract(user_input)
    except Exception as e:
        print(f"Gagal memahami preferensi: {e}")
        return

    # Progressive clarification — hanya tanya info yang benar-benar kurang
    missing = extractor.find_missing_required(constraints)
    if missing:
        print("\nAda satu info yang masih kurang:\n")
    constraints = ask_missing_fields(constraints, missing)

    print(f"\n  Tujuan  : {constraints.get('destination_area', 'Yogyakarta')}")
    print(f"  Durasi  : {constraints.get('duration_days')} hari")
    print(f"  Budget  : {constraints.get('budget_level', 'medium')}")
    print(f"  Minat   : {', '.join(constraints.get('interests', ['Culture', 'Culinary']))}")
    print(f"  Pace    : {constraints.get('pace', 'normal')}")

    neo4j = _get_neo4j()
    print("\n[2/3] Mencari destinasi dari Neo4j...")
    retriever = GraphRetriever(neo4j)
    context = retriever.retrieve_context(constraints)
    n_dest = len(context.get("destinations", []))
    print(f"      Ditemukan {n_dest} destinasi relevan di graph")
    neo4j.close()

    if n_dest == 0:
        print("      WARNING: 0 destinasi — jalankan scripts/03_import_to_neo4j.py terlebih dahulu.")

    print("\n[3/3] Membuat itinerary... (bisa 1-2 menit)\n")
    try:
        itinerary = LLMClient().generate_itinerary(constraints, context)
    except Exception as e:
        print(f"Gagal generate itinerary: {e}")
        return

    output_file = Path("output_itinerary.md")
    output_file.write_text(itinerary, encoding="utf-8")

    print("=" * 60)
    print(itinerary.encode("ascii", errors="replace").decode("ascii"))
    print("=" * 60)
    print(f"\nItinerary disimpan ke: {output_file.resolve()}")


def _handle_graph_query(question: str):
    """Jawab pertanyaan tentang destinasi langsung via Text-to-Cypher."""
    neo4j = _get_neo4j()
    converter = TextToCypherConverter(neo4j_client=neo4j)
    result = converter.convert_and_execute(question)

    print(f"\n[Cypher]\n{result['cypher']}")
    if result["error"]:
        print(f"[Error] {result['error']}")
    else:
        print(f"[Hasil] {len(result['results'])} data ditemukan")
        for row in result["results"][:5]:
            print(f"  {json.dumps(row, ensure_ascii=False)}")
    print(f"\n{result['explanation']}")

    neo4j.close()


def _handle_add_data(text: str):
    """Ekstrak entitas wisata dari teks dan simpan ke Neo4j."""
    neo4j = _get_neo4j()
    builder = LLMGraphBuilder(neo4j_client=neo4j)

    # Strip prefix kalau user menulis "tambah data: ..."
    for prefix in ("tambah data:", "tambahkan info:", "masukkan data:", "input data:", "catat info:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break

    print(f"\nMemproses teks ({len(text)} karakter)...")
    result = builder.build_from_text(text, source="manual_input")
    stored = result.get("stored", {})
    print(f"\nHasil:")
    print(f"  Destinasi : {stored.get('destinations', 0)}")
    print(f"  Restoran  : {stored.get('restaurants', 0)}")
    print(f"  Relasi    : {stored.get('relationships', 0)}")
    print(f"\n{result.get('summary', '')}")

    neo4j.close()


# ──────────────────────────────────────────────
# Conversational loop (default)
# ──────────────────────────────────────────────

def conversational_loop():
    """
    Loop percakapan utama.
    User tidak perlu pilih mode — sistem deteksi intent otomatis dari input.
    """
    print("\nHalo! Saya asisten wisata Yogyakarta Anda.")
    print("Ketik apa saja — rencana perjalanan, pertanyaan tentang tempat, dll.")
    print("(ketik 'keluar' untuk berhenti)\n")
    print("Contoh:")
    print("  • 'Mau ke Yogyakarta 3 hari, suka kuliner dan budaya, budget medium'")
    print("  • 'Museum apa saja di Yogyakarta dengan rating di atas 4?'")
    print("  • 'Restoran halal terdekat dari Prambanan?'\n")

    while True:
        try:
            user_input = input("Anda: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("keluar", "exit", "q", "quit"):
            break

        intent = detect_intent(user_input)

        if intent == "graph_query":
            _handle_graph_query(user_input)
        elif intent == "add_data":
            _handle_add_data(user_input)
        else:
            _handle_itinerary(user_input)

        print()


# ──────────────────────────────────────────────
# Standalone mode functions (untuk --query / --add flags dan demo scripts)
# ──────────────────────────────────────────────

def mode_text_to_cypher(question: str = None):
    """Dipakai oleh flag --query dan scripts/05_text_to_cypher_demo.py."""
    print("\n=== Tanya Graph (Text-to-Cypher) ===\n")
    neo4j = _get_neo4j()
    converter = TextToCypherConverter(neo4j_client=neo4j)

    def _ask(q: str):
        result = converter.convert_and_execute(q)
        print(f"\n[Cypher]\n{result['cypher']}")
        if result["error"]:
            print(f"[Error] {result['error']}")
        else:
            print(f"[Hasil] {len(result['results'])} baris")
            for row in result["results"][:5]:
                print(f"  {json.dumps(row, ensure_ascii=False)}")
        print(f"\n[Penjelasan]\n{result['explanation']}")

    if question:
        _ask(question)
    else:
        print("Pertanyaan ('keluar' untuk kembali):")
        while True:
            try:
                q = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("keluar", "exit", "q"):
                break
            if q:
                _ask(q)

    neo4j.close()


def mode_graph_builder(text: str = None):
    """Dipakai oleh flag --add dan scripts/06_graph_builder_demo.py."""
    print("\n=== Tambah Data ke Graph (LLM Graph Builder) ===\n")
    neo4j = _get_neo4j()
    builder = LLMGraphBuilder(neo4j_client=neo4j)

    def _process(t: str):
        print(f"Memproses ({len(t)} karakter)...")
        result = builder.build_from_text(t, source="manual_input")
        stored = result.get("stored", {})
        print(f"  Destinasi={stored.get('destinations', 0)}, "
              f"Restoran={stored.get('restaurants', 0)}, "
              f"Relasi={stored.get('relationships', 0)}")
        print(result.get("summary", ""))

    if text:
        _process(text)
    else:
        print("Masukkan teks (akhiri dengan baris kosong), atau 'keluar' untuk berhenti:")
        while True:
            lines = []
            try:
                while True:
                    line = input()
                    if line.lower() in ("keluar", "exit", "q"):
                        neo4j.close()
                        return
                    if line == "" and lines:
                        break
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                break
            if lines:
                _process("\n".join(lines))

    neo4j.close()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("request", nargs="?", help="Request itinerary (free-text)")
    parser.add_argument("--query", "-q", metavar="PERTANYAAN", help="Text-to-Cypher langsung")
    parser.add_argument("--add", "-a", metavar="TEKS", help="Tambah data ke graph langsung")
    args, _ = parser.parse_known_args()

    if args.query:
        mode_text_to_cypher(args.query)
    elif args.add:
        mode_graph_builder(args.add)
    elif args.request:
        _handle_itinerary(args.request)
    else:
        conversational_loop()

    print("\nTerima kasih!")


if __name__ == "__main__":
    main()
