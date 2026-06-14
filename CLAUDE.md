# Sistem Rekomendasi Itinerary Wisata Indonesia - Graph-RAG

AI-powered travel itinerary recommendation system untuk Indonesia menggunakan Neo4j Graph Database, Graph-RAG architecture, dan Claude LLM.

## 🎯 Overview

Sistem ini menghasilkan itinerary wisata yang dipersonalisasi berdasarkan:
- Preferensi user (budget, interests, pace, duration)
- Data dari multiple sources (Wikidata, OpenStreetMap, Google Places, BMKG)
- Graph-based retrieval dari Neo4j
- Natural language explanation dari Claude

## 🏗️ Arsitektur

```
User Input (Natural Language)
    ↓
NLP Extraction Layer (Claude - extract constraints)
    ↓
Graph-RAG Retrieval (Neo4j - fetch relevant data)
    ↓
Itinerary Optimization Layer
    ↓
LLM Generation (Claude - generate readable itinerary)
    ↓
Output (Markdown itinerary dengan alternatives)
```

## 📦 Tech Stack

- **Database**: Neo4j (Graph Database)
- **Data Processing**: Python, Pandas, GeoPandas
- **APIs**: 
  - Wikidata SPARQL
  - OpenStreetMap Overpass
  - Google Places API
  - BMKG Weather API
  - Anthropic Claude API
- **Web Framework**: FastAPI (untuk API endpoint)

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Neo4j (Community/Enterprise atau Neo4j Aura)
- API Keys:
  - Google Places API
  - Anthropic Claude API

### Setup

1. **Clone dan setup virtual environment**
```bash
git clone <repo>
cd itinerary-recommendation-system
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env dengan API keys dan Neo4j connection
```

4. **Start Neo4j**
```bash
# Via Docker
docker run --publish=7474:7474 --publish=7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Atau gunakan Neo4j Desktop / Neo4j Aura
```

5. **Data Collection (Optional - use provided sample data)**
```bash
python scripts/01_collect_data.py --region yogyakarta
```

6. **Import data ke Neo4j**
```bash
python scripts/02_import_to_neo4j.py
```

7. **Generate sample itinerary**
```bash
python scripts/03_generate_itinerary_demo.py
```

## 📂 Project Structure

```
itinerary-recommendation-system/
├── config/                          # Configuration files
│   ├── settings.py
│   └── __init__.py
├── data/
│   ├── raw/                        # Raw data dari APIs
│   │   ├── wikidata/
│   │   ├── osm/
│   │   └── google_places/
│   ├── processed/                  # Cleaned final CSVs
│   │   ├── destinations.csv
│   │   ├── restaurants.csv
│   │   └── ...
│   └── neo4j_imports/              # Cypher import scripts
├── src/
│   ├── data_collection/            # Data extraction modules
│   ├── database/                   # Neo4j client & queries
│   ├── rag/                        # RAG pipeline
│   ├── optimization/               # Itinerary optimization
│   ├── generation/                 # Output generation
│   └── api/                        # FastAPI endpoints
├── scripts/
│   ├── 01_collect_data.py
│   ├── 02_import_to_neo4j.py
│   └── 03_generate_itinerary_demo.py
├── notebooks/
│   └── 01_eda_destinations.ipynb   # Exploratory notebooks
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
│   └── docker-compose.yml
└── README.md
```

## 🔄 Data Pipeline

### Phase 1: Data Collection
- Wikidata SPARQL untuk destinations awal
- OpenStreetMap Overpass untuk POIs
- Google Places untuk ratings & metadata
- BMKG API untuk weather

### Phase 2: Data Processing
- Deduplication (fuzzy matching)
- Coordinate validation
- Format normalization
- Data quality scoring

### Phase 3: Neo4j Graph
- Load CSVs via Cypher
- Create nodes & relationships
- Index optimization

### Phase 4: RAG Pipeline
- Constraint extraction (Claude)
- Graph retrieval (Neo4j Cypher)
- Itinerary generation (Claude)

## 🎓 Usage Examples

### Example 1: 3-day Cultural Journey

```bash
python scripts/03_generate_itinerary_demo.py
```

Input:
```
Buatkan itinerary 3 hari di Yogyakarta untuk budget medium, 
suka budaya dan kuliner, pace santai.
```

Output:
```markdown
# Itinerary Yogyakarta, 3 Hari

## Summary
- Duration: 3 hari
- Total Budget: Rp 2,000,000
- Pace: Slow (2-3 destinasi/hari)
- Group: Individual

## Day 1: 15 Juli 2024
### Weather: Partly Cloudy, 31°C

| Time | Activity | Duration | Cost | Notes |
|------|----------|----------|------|-------|
| 08:00 | Visit Borobudur Temple | 120 min | Rp 50-100k | Rating: 4.7/5, Open 06:00-17:00 |
| 10:30 | Travel to site | 45 min | - | 42.5 km via car |
| ... | ... | ... | ... | ... |
```

### Example 2: API Usage (Future)

```python
import requests

response = requests.post("http://localhost:8000/generate-itinerary", json={
    "user_message": "3 hari di Bali, budget medium, suka pantai"
})

print(response.json())
```

## 🔍 Key Features

✅ **Graph-Based Retrieval**: Menggunakan Neo4j untuk relation traversal
✅ **Multi-source Data**: Wikidata, OSM, Google Places, BMKG terintegrasi
✅ **Constraint Validation**: Respect user preferences (budget, pace, interests)
✅ **No Hallucination**: LLM hanya generate dari graph context
✅ **Source Attribution**: Setiap data point ada source-nya
✅ **Alternative Suggestions**: Multiple itineraries dengan berbagai pace

## ⚠️ Important Notes

### Data Accuracy
- Data dari berbagai sources mungkin ada perbedaan
- Selalu verify sebelum kunjungan
- Rating disimpan dengan source info (Google vs Tripadvisor)

### API Rate Limits
- Google Places: ~100 req/min
- Wikidata SPARQL: Bisa handle batch queries
- Claude API: Respek rate limits di .env

### Geographic Scope (MVP)
- MVP fokus pada **Yogyakarta region** saja
- Expansion ke regions lain di Phase 2

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Coverage report
pytest --cov=src tests/
```

## 📊 Sample Data

Project includes sample CSV files untuk testing:
- `data/processed/destinations.csv` - 5 Yogyakarta attractions
- `data/processed/restaurants.csv` - 5 restaurants
- `data/processed/destination_connections.csv` - Routes

Untuk production data, jalankan:
```bash
python scripts/01_collect_data.py --region yogyakarta
```

## 🐛 Troubleshooting

### Neo4j Connection Error
```
Error: Failed to connect to Neo4j
```
**Solution**: Pastikan Neo4j running dan credentials di .env benar
```bash
docker ps  # Check if container running
# Or check Neo4j Aura connection string
```

### API Key Not Found
```
Error: ANTHROPIC_API_KEY not found
```
**Solution**: Copy .env.example ke .env dan fill API keys
```bash
cp .env.example .env
# Edit .env dengan actual API keys
```

### CSV Import Error
```
FileNotFoundError: data/processed/destinations.csv
```
**Solution**: Run data collection script atau gunakan sample data yang provided

## 📚 Documentation

- `docs/ARCHITECTURE.md` - Detailed system architecture
- `docs/DATA_SOURCES.md` - Data source documentation
- `docs/SETUP.md` - Detailed setup guide
- `docs/API_DOCUMENTATION.md` - API endpoint documentation

## 🗺️ Roadmap

**Phase 1 (MVP - Week 4)**
- [x] Data collection pipeline
- [x] Neo4j graph setup
- [x] RAG constraint extraction
- [x] Itinerary generation

**Phase 2 (Q3 2024)**
- [ ] Multi-region support (Bali, Bandung, Surabaya)
- [ ] Advanced TSP optimization
- [ ] Booking integration (Agoda, Tiket.com)
- [ ] User authentication & history

**Phase 3 (Q4 2024)**
- [ ] Mobile app
- [ ] Real-time itinerary adjustment
- [ ] Social features (share, collaborate)
- [ ] Personalized ML recommendations

## 👥 Contributing

Contributions welcome! Areas:
- [ ] More regions dataset
- [ ] Better optimization algorithms
- [ ] Test coverage improvement
- [ ] Documentation enhancement

## 📝 License

MIT License - Silakan gunakan untuk educational & research purposes

## 📧 Contact

Untuk questions atau suggestions:
- Open GitHub Issue
- Email: [your-email]

---

**Last Updated**: 2024-06-10
**MVP Status**: Ready for testing
**Stable Release**: v0.1.0
