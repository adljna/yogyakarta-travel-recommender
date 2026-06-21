# Yogyakarta Travel Recommender — Graph-RAG

Sistem rekomendasi itinerary wisata Yogyakarta berbasis Neo4j Graph Database dan LLM (via OpenRouter), dilengkapi Text-to-Cypher dan LLM Graph Builder.

## Fitur

- **Generate Itinerary** — input teks bebas, sistem ekstrak preferensi lalu buat itinerary dari data Neo4j
- **Text-to-Cypher** — tanya langsung tentang destinasi; LLM tulis Cypher, eksekusi ke Neo4j, jelaskan hasilnya
- **LLM Graph Builder** — paste teks artikel/blog/review; LLM ekstrak entitas & relasi lalu simpan ke Neo4j

## Arsitektur

```
User Input (Natural Language)
    │
    ├── Intent: itinerary ──► ConstraintExtractor (LLM)
    │                              ↓
    │                         GraphRetriever (Neo4j)
    │                              ↓
    │                         LLMClient (OpenRouter) ──► output_itinerary.md
    │
    ├── Intent: graph_query ──► TextToCypherConverter (LLM → Cypher → Neo4j)
    │                               ↓
    │                          Jawaban + penjelasan NL
    │
    └── Intent: add_data ──► LLMGraphBuilder (LLM ekstrak entitas → Neo4j)
                                 ↓
                            Ringkasan node & relasi yang tersimpan
```

## Tech Stack

- **Database**: Neo4j 5.x (Graph Database)
- **LLM**: OpenRouter API (model: `openai/gpt-4o-mini`)
- **Data Processing**: Python, Pandas
- **Language**: Python 3.10+

## Struktur Project

```
yogyakarta-travel-recommender/
├── config/
│   └── settings.py              # Pydantic settings loader dari .env
├── data/
│   ├── raw/                     # Data sumber asli (CSV)
│   │   ├── osm_pois_yogyakarta.csv
│   │   ├── wikidata_yogyakarta.csv
│   │   └── wikipedia_enrichment_yogyakarta.csv
│   ├── processed/               # CSV yang sudah dibersihkan
│   │   ├── destinations.csv
│   │   ├── restaurants.csv
│   │   └── destination_connections.csv
│   ├── neo4j_imports/           # Cypher import scripts & data
│   │   ├── 01_import_destinations.cypher
│   │   ├── 02_import_connections.cypher
│   │   └── *.csv
│   └── wisata_jogja_clean.csv   # Data sumber utama (Google Maps)
├── src/
│   ├── database/
│   │   ├── neo4j_client.py      # Koneksi Neo4j
│   │   └── queries.py           # Cypher queries statis
│   ├── rag/
│   │   ├── constraint_extractor.py   # Ekstrak preferensi user via LLM
│   │   ├── graph_retriever.py        # Query Neo4j untuk konteks
│   │   ├── llm_client.py             # Generate itinerary via OpenRouter
│   │   ├── questionnaire.py          # Klarifikasi info yang kurang
│   │   └── text_to_cypher.py         # NL → Cypher via LLM
│   └── graph_builder/
│       └── llm_graph_builder.py      # Teks → entitas → Neo4j
├── scripts/
│   ├── run.py                        # Entry point utama (conversational)
│   ├── 01_process_data.py            # Proses CSV mentah → processed/
│   ├── 02_import_to_neo4j.py        # Import CSV ke Neo4j
│   ├── 03_generate_itinerary_demo.py
│   ├── 04_text_to_cypher_demo.py    # Demo Text-to-Cypher
│   └── 05_graph_builder_demo.py     # Demo LLM Graph Builder
├── .env.example
├── requirements.txt
└── FLOW_TIER4.txt
```

## Setup

### Prerequisites

- Python 3.10+
- Neo4j (Desktop / Community / Aura) — database name: `itinerary`
- API Key: OpenRouter

### 1. Clone & virtual environment

```bash
git clone <repo>
cd yogyakarta-travel-recommender
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Konfigurasi environment

```bash
cp .env.example .env
```

Edit `.env` minimal dengan:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
OPENROUTER_API_KEY=your_openrouter_key
```

### 4. Import data ke Neo4j

```bash
python scripts/01_process_data.py     # proses CSV sumber
python scripts/02_import_to_neo4j.py  # import ke Neo4j
```

### 5. Jalankan

```bash
python scripts/run.py
```

## Cara Penggunaan

### Mode Conversational (default)

```bash
python scripts/run.py
```

Sistem deteksi intent otomatis — tidak perlu pilih menu:

```
Anda: Mau ke Yogyakarta 3 hari, suka kuliner dan budaya, budget medium
→ [Generate Itinerary]

Anda: Museum apa saja di Yogyakarta dengan rating di atas 4?
→ [Text-to-Cypher]

Anda: Tambah data: Pantai Parangtritis adalah pantai terkenal di Yogyakarta...
→ [LLM Graph Builder]
```

### Mode CLI Langsung

```bash
# Generate itinerary
python scripts/run.py "Buatkan itinerary 2 hari di Yogyakarta, suka alam, budget hemat"

# Tanya graph
python scripts/run.py --query "Restoran halal terdekat dari Prambanan?"

# Tambah data ke graph
python scripts/run.py --add "Kebun Buah Mangunan adalah wisata alam di Bantul..."
```

### Demo Scripts

```bash
python scripts/03_generate_itinerary_demo.py  # demo itinerary
python scripts/04_text_to_cypher_demo.py      # demo 5 pertanyaan Text-to-Cypher
python scripts/05_graph_builder_demo.py       # demo ekstrak artikel ke Neo4j
```

## Sumber Data

Data wisata Yogyakarta diperoleh dengan scraping Google Maps menggunakan [google-maps-scraper](https://github.com/gosom/google-maps-scraper), kemudian disimpan sebagai `data/wisata_jogja_clean.csv`.

Hasil scraping diproses oleh `scripts/01_process_data.py` menjadi tiga file di `data/processed/`:

| File | Isi |
|------|-----|
| `data/processed/destinations.csv` | Destinasi wisata Yogyakarta |
| `data/processed/restaurants.csv` | Restoran |
| `data/processed/destination_connections.csv` | Rute antar destinasi |

File processed inilah yang kemudian diimport ke Neo4j via `scripts/02_import_to_neo4j.py`.

## Troubleshooting

**Neo4j connection error**
```
Gagal konek ke Neo4j: ...
```
Pastikan Neo4j running dan kredensial di `.env` benar. Database harus bernama `itinerary`.

**API key error**
```
Error: OPENROUTER_API_KEY not found
```
Salin `.env.example` ke `.env` dan isi API key OpenRouter.

**0 destinasi ditemukan**
```
WARNING: 0 destinasi — jalankan scripts/02_import_to_neo4j.py terlebih dahulu.
```
Jalankan `scripts/02_import_to_neo4j.py` untuk mengisi database Neo4j.
