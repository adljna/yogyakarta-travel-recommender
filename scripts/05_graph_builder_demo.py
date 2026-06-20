#!/usr/bin/env python3
"""
Demo: LLM Graph Builder (Tier 4)

Menunjukkan bagaimana LLM mengekstrak entitas & relasi dari teks tidak
terstruktur (artikel blog, ulasan wisata) dan menyimpannya ke Neo4j.

Usage:
    python scripts/06_graph_builder_demo.py
    python scripts/06_graph_builder_demo.py --file path/to/article.txt
    python scripts/06_graph_builder_demo.py --text "Coba teks ini..."
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import logging
from src.graph_builder import LLMGraphBuilder
from src.database import Neo4jClient

logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")

BANNER = """
╔══════════════════════════════════════════════════════╗
║   LLM Graph Builder Demo  (Tier 4)                  ║
║   Teks Bebas → Entitas & Relasi → Neo4j Graph        ║
╚══════════════════════════════════════════════════════╝
"""

# Contoh teks wisata yang akan diekstrak
SAMPLE_TEXTS = [
    {
        "source": "blog_wisata_jogja_1",
        "text": """
Itinerary 2 Hari di Yogyakarta: Dari Candi hingga Kuliner

Hari pertama kami mulai dengan mengunjungi Candi Prambanan yang megah,
terletak di Sleman, Yogyakarta. Kompleks candi Hindu terbesar di Indonesia ini
buka mulai jam 06:00 pagi hingga 17:00, dengan tiket masuk sekitar Rp 50.000
untuk wisatawan domestik. Setelah puas menikmati keindahan candi,
kami melanjutkan perjalanan ke Keraton Yogyakarta di pusat kota.
Keraton buka setiap hari kecuali Jumat, dari pukul 08:30 hingga 14:00.

Untuk makan siang, kami mencoba Warung Bu Ageng yang terkenal dengan
gudeg Yogyakarta-nya. Lokasinya dekat dengan Keraton dan selalu ramai.
Harganya terjangkau, sekitar Rp 25.000-50.000 per porsi.

Hari kedua kami mengunjungi Candi Borobudur yang terletak di Magelang,
sekitar 42 km dari Yogyakarta. Perjalanan memakan waktu sekitar 1 jam
dengan kendaraan pribadi. Tiket masuk Rp 50.000 untuk dewasa.
Di dekat Borobudur ada Rumah Makan Borobudur View yang menyajikan
pemandangan langsung ke candi, cocok untuk makan siang yang berkesan.
""",
    },
    {
        "source": "review_kuliner_jogja",
        "text": """
Kuliner Wajib Coba di Jogja

Yogyakarta bukan hanya kaya budaya, tapi juga surga kuliner.
Beberapa tempat makan yang wajib dikunjungi:

1. Angkringan Lik Man - Warung angkringan legendaris di dekat Stasiun Tugu.
   Buka dari sore hingga tengah malam. Harga sangat murah, cocok untuk backpacker.
   Terletak di Jl. Wongsodirjan, dekat Stasiun Tugu Yogyakarta.

2. Sate Klathak Pak Pong - Sate kambing bakar dengan bumbu sederhana tapi lezat.
   Lokasinya di Pasar Jejeran, Bantul. Buka siang hingga sore.
   Sangat dekat dengan area wisata Bantul.

3. Gudeg Yu Djum - Resto gudeg otentik yang sudah berdiri sejak 1951.
   Berlokasi di Wijilan, Yogyakarta, kawasan yang dikenal sebagai kampung gudeg.
   Buka setiap hari pukul 05:00-21:00. Harga Rp 30.000-80.000.

Area wisata Malioboro juga dekat dengan berbagai pilihan kuliner,
termasuk lesehan di sepanjang jalan yang menjual nasi goreng,
bakmi, dan seafood dengan harga terjangkau.
""",
    },
    {
        "source": "artikel_alam_jogja",
        "text": """
Wisata Alam Tersembunyi di Sekitar Yogyakarta

Bagi pecinta alam, Yogyakarta menyimpan banyak kejutan.
Pantai Parangtritis di selatan Yogyakarta (±28 km dari pusat kota)
adalah pantai paling ikonik, terkenal dengan ombak yang kuat dan
sunset yang memukau. Tiket masuk Rp 10.000.

Tidak jauh dari Parangtritis, terdapat Gumuk Pasir Parangkusumo,
padang pasir mini satu-satunya di Asia Tenggara. Cocok untuk sandboarding.
Kedua tempat ini saling berdekatan dan bisa dikunjungi dalam satu hari.

Untuk pendaki, Gunung Merapi menjadi daya tarik utama.
Basecamp pendakian ada di Kaliurang, Sleman. Dari Yogyakarta
jaraknya sekitar 25 km. Museum Gunung Merapi juga tersedia di
Kaliurang untuk yang ingin belajar tentang sejarah erupsi Merapi.
Museum buka 08:00-16:00, tiket Rp 5.000.
""",
    },
]


def display_extraction_result(result: dict):
    print(f"\n{'='*60}")
    print(f"SUMBER: {result['source']}")
    print(f"Panjang teks: {result['text_length']} karakter")
    print("="*60)

    extracted = result.get("extracted", {})
    entities = extracted.get("entities", {})

    # Tampilkan Destinasi
    destinations = entities.get("destinations", [])
    if destinations:
        print(f"\n[Destinasi yang diekstrak] ({len(destinations)} tempat)")
        for d in destinations:
            print(f"  • {d.get('name')} [{d.get('category', '-')}]")
            if d.get("description"):
                desc = d["description"][:80] + "..." if len(d["description"]) > 80 else d["description"]
                print(f"    → {desc}")
            if d.get("city"):
                print(f"    → Kota: {d['city']}")

    # Tampilkan Restoran
    restaurants = entities.get("restaurants", [])
    if restaurants:
        print(f"\n[Restoran/Kuliner yang diekstrak] ({len(restaurants)} tempat)")
        for r in restaurants:
            print(f"  • {r.get('name')} [{r.get('cuisine_type', '-')}]")
            if r.get("city"):
                print(f"    → Kota: {r['city']}, Harga: {r.get('price_level', '-')}")

    # Tampilkan Relasi
    relationships = extracted.get("relationships", [])
    if relationships:
        print(f"\n[Relasi yang diekstrak] ({len(relationships)} relasi)")
        for rel in relationships:
            print(f"  • {rel.get('from')} --[{rel.get('type')}]--> {rel.get('to')}")

    # Tampilkan yang tersimpan
    stored = result.get("stored", {})
    print(f"\n[Tersimpan ke Neo4j]")
    print(f"  Destinasi: {stored.get('destinations', 0)}")
    print(f"  Restoran:  {stored.get('restaurants', 0)}")
    print(f"  Kota:      {stored.get('cities', 0)}")
    print(f"  Relasi:    {stored.get('relationships', 0)}")
    if stored.get("errors", 0):
        print(f"  Error:     {stored['errors']}")

    print(f"\n[Ringkasan]")
    print(f"  {result.get('summary')}")


def verify_graph_contents(neo4j: Neo4jClient):
    """Verifikasi isi Neo4j setelah graph builder berjalan."""
    print(f"\n{'='*60}")
    print("VERIFIKASI GRAPH — Data yang ditambahkan LLM Graph Builder")
    print("="*60)

    queries = [
        ("Total node Destination", "MATCH (d:Destination) RETURN count(d) AS count"),
        ("Total node Restaurant", "MATCH (r:Restaurant) RETURN count(r) AS count"),
        ("Total node City", "MATCH (c:City) RETURN count(c) AS count"),
        ("Node dibuat oleh LLM Builder",
         "MATCH (n) WHERE n.created_by = 'llm_graph_builder' RETURN count(n) AS count"),
        ("Relasi RECOMMENDED_WITH",
         "MATCH ()-[r:RECOMMENDED_WITH]->() RETURN count(r) AS count"),
        ("Relasi NEAR",
         "MATCH ()-[r:NEAR]->() RETURN count(r) AS count"),
    ]

    for label, query in queries:
        try:
            result = neo4j.run_query(query)
            count = result[0]["count"] if result else 0
            print(f"  {label}: {count}")
        except Exception as e:
            print(f"  {label}: ERROR - {e}")

    # Tampilkan beberapa node yang baru dibuat
    try:
        new_nodes = neo4j.run_query(
            "MATCH (n) WHERE n.created_by = 'llm_graph_builder' "
            "RETURN labels(n)[0] AS type, n.name AS name, n.source AS source "
            "LIMIT 10"
        )
        if new_nodes:
            print(f"\n[Node baru dari LLM Graph Builder (maks 10)]")
            for node in new_nodes:
                print(f"  [{node['type']}] {node['name']} (sumber: {node['source']})")
    except Exception as e:
        print(f"  Gagal query node baru: {e}")


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(description="LLM Graph Builder Demo")
    parser.add_argument("--file", help="Path ke file teks yang akan diproses")
    parser.add_argument("--text", help="Teks langsung yang akan diproses")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip verifikasi isi graph setelah proses")
    args = parser.parse_args()

    try:
        neo4j = Neo4jClient()
        print("✓ Terhubung ke Neo4j\n")
    except Exception as e:
        print(f"✗ Gagal koneksi ke Neo4j: {e}")
        print("Pastikan Neo4j running di localhost:7687")
        return

    builder = LLMGraphBuilder(neo4j_client=neo4j)

    if args.file:
        # Proses dari file
        try:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
            print(f"Memproses file: {args.file}\n")
            result = builder.build_from_text(text, source=os.path.basename(args.file))
            display_extraction_result(result)
        except FileNotFoundError:
            print(f"File tidak ditemukan: {args.file}")
            return

    elif args.text:
        # Proses dari teks CLI
        print("Memproses teks dari argumen...\n")
        result = builder.build_from_text(args.text, source="cli_input")
        display_extraction_result(result)

    else:
        # Mode demo: proses semua sample text
        print(f"Memproses {len(SAMPLE_TEXTS)} contoh teks wisata...\n")
        print("(Untuk teks custom: --file artikel.txt atau --text 'teks Anda')\n")

        for sample in SAMPLE_TEXTS:
            print(f"\nMemproses: [{sample['source']}]...")
            result = builder.build_from_text(sample["text"], source=sample["source"])
            display_extraction_result(result)

    # Verifikasi isi graph
    if not args.no_verify:
        verify_graph_contents(neo4j)

    neo4j.close()
    print("\nSelesai.")


if __name__ == "__main__":
    main()
