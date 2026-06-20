"""
LLM Graph Builder: Menggunakan LLM untuk mengekstrak entitas dan relasi
dari teks tidak terstruktur (artikel blog, ulasan, deskripsi Wikipedia),
lalu menyimpannya langsung ke Neo4j.

Komponen wajib Tier 4: LLM for Graph Builder.
"""

import json
import logging
import re
import uuid
import requests
from typing import Optional

from config import settings
from src.database.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

# Schema ekstraksi yang dikirim ke LLM sebagai panduan
EXTRACTION_PROMPT_TEMPLATE = """Anda adalah expert knowledge graph builder untuk data wisata Indonesia.

Ekstrak entitas dan relasi dari teks berikut, lalu kembalikan sebagai JSON.

FORMAT JSON YANG DIHARAPKAN:
{
  "entities": {
    "destinations": [
      {
        "name": "Nama Tempat",
        "category": "temple/museum/park/beach/market/restaurant/cafe/landmark/nature",
        "description": "deskripsi singkat",
        "city": "nama kota",
        "region": "Yogyakarta",
        "opening_hours": "jam buka jika disebutkan",
        "ticket_price": "harga tiket jika disebutkan",
        "rating": null
      }
    ],
    "restaurants": [
      {
        "name": "Nama Restoran",
        "cuisine_type": "jenis masakan",
        "description": "deskripsi singkat",
        "city": "nama kota",
        "price_level": "budget/medium/premium",
        "halal_status": "halal/not_halal/unknown",
        "rating": null
      }
    ],
    "cities": [
      {
        "name": "nama kota",
        "province": "nama provinsi"
      }
    ]
  },
  "relationships": [
    {
      "from": "Nama Entitas Asal",
      "type": "NEAR|IS_IN|HAS_CATEGORY|RECOMMENDED_WITH|CLOSE_TO",
      "to": "Nama Entitas Tujuan",
      "properties": {}
    }
  ]
}

ATURAN:
- Hanya ekstrak entitas yang EKSPLISIT disebutkan dalam teks
- Jika field tidak disebutkan, gunakan null (bukan string kosong)
- Untuk "type" relasi gunakan: NEAR (berdekatan), IS_IN (berada di kota),
  HAS_CATEGORY (jenis tempat), RECOMMENDED_WITH (disarankan dikunjungi bersama),
  CLOSE_TO (dekat dengan)
- Kembalikan HANYA JSON valid, tanpa penjelasan tambahan

TEKS YANG AKAN DIEKSTRAK:
"""


class LLMGraphBuilder:
    """
    Membangun knowledge graph dari teks bebas menggunakan LLM.

    Alur kerja:
    1. Terima teks (artikel blog, review, deskripsi Wikipedia, dll.)
    2. Kirim ke LLM untuk ekstrak entitas (Destination, Restaurant, City)
       dan relasi (NEAR, IS_IN, HAS_CATEGORY, RECOMMENDED_WITH)
    3. Simpan hasil ke Neo4j menggunakan MERGE (tidak duplikat)
    4. Kembalikan ringkasan apa yang tersimpan
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        self.neo4j = neo4j_client or Neo4jClient()
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model
        self.base_url = settings.llm_base_url

    def build_from_text(self, text: str, source: str = "manual_input") -> dict:
        """
        Pipeline utama: teks → ekstrak → simpan ke Neo4j.

        Args:
            text: Teks bebas berisi informasi tempat wisata
            source: Label sumber data (untuk audit trail)

        Returns:
            dict dengan keys: source, extracted, stored, summary
        """
        logger.info(f"LLM Graph Builder: processing text ({len(text)} chars) from '{source}'")

        # Step 1: Ekstrak entitas & relasi via LLM
        extracted = self._extract_entities_and_relations(text)
        logger.info(
            f"Extracted: {len(extracted.get('entities', {}).get('destinations', []))} destinations, "
            f"{len(extracted.get('entities', {}).get('restaurants', []))} restaurants, "
            f"{len(extracted.get('relationships', []))} relationships"
        )

        # Step 2: Simpan ke Neo4j
        stored_counts = self._store_to_neo4j(extracted, source)

        # Step 3: Buat ringkasan natural language
        summary = self._generate_summary(extracted, stored_counts, source)

        return {
            "source": source,
            "text_length": len(text),
            "extracted": extracted,
            "stored": stored_counts,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Step 1: Ekstraksi via LLM
    # ------------------------------------------------------------------

    def _extract_entities_and_relations(self, text: str) -> dict:
        prompt = EXTRACTION_PROMPT_TEMPLATE + text
        response = self._call_llm(
            system_prompt="Anda adalah expert knowledge graph builder. Kembalikan hanya JSON valid.",
            user_message=prompt,
            temperature=0.1,
            max_tokens=3000,
        )
        return self._parse_json_safe(response)

    # ------------------------------------------------------------------
    # Step 2: Simpan ke Neo4j
    # ------------------------------------------------------------------

    def _store_to_neo4j(self, extracted: dict, source: str) -> dict:
        counts = {
            "destinations": 0,
            "restaurants": 0,
            "cities": 0,
            "relationships": 0,
            "errors": 0,
        }

        entities = extracted.get("entities", {})

        # --- Simpan City ---
        for city in entities.get("cities", []):
            if not city.get("name"):
                continue
            try:
                self.neo4j.run_query(
                    """
                    MERGE (c:City {name: $name})
                    ON CREATE SET c.province = $province, c.created_by = 'llm_graph_builder'
                    ON MATCH SET c.province = COALESCE(c.province, $province)
                    """,
                    {"name": city["name"], "province": city.get("province", "")},
                )
                counts["cities"] += 1
            except Exception as e:
                logger.warning(f"Gagal simpan city '{city.get('name')}': {e}")
                counts["errors"] += 1

        # --- Simpan Destination ---
        for dest in entities.get("destinations", []):
            if not dest.get("name"):
                continue
            try:
                dest_id = f"llm_{uuid.uuid4().hex[:8]}"
                self.neo4j.run_query(
                    """
                    MERGE (d:Destination {name: $name})
                    ON CREATE SET
                        d.destination_id   = $dest_id,
                        d.category         = $category,
                        d.description      = $description,
                        d.city             = $city,
                        d.region           = $region,
                        d.opening_hours    = $opening_hours,
                        d.source           = $source,
                        d.data_quality_score = 0.5,
                        d.created_by       = 'llm_graph_builder'
                    ON MATCH SET
                        d.description = COALESCE(d.description, $description),
                        d.source      = $source
                    """,
                    {
                        "name": dest["name"],
                        "dest_id": dest_id,
                        "category": dest.get("category", "tourist_attraction"),
                        "description": dest.get("description"),
                        "city": dest.get("city"),
                        "region": dest.get("region", "Yogyakarta"),
                        "opening_hours": dest.get("opening_hours"),
                        "source": source,
                    },
                )

                # Auto-link ke City jika ada
                if dest.get("city"):
                    self.neo4j.run_query(
                        """
                        MATCH (d:Destination {name: $name})
                        MERGE (c:City {name: $city})
                        MERGE (d)-[:IS_IN]->(c)
                        """,
                        {"name": dest["name"], "city": dest["city"]},
                    )

                # Auto-link ke Category
                if dest.get("category"):
                    self.neo4j.run_query(
                        """
                        MATCH (d:Destination {name: $name})
                        MERGE (cat:Category {name: $category})
                        MERGE (d)-[:HAS_CATEGORY]->(cat)
                        """,
                        {"name": dest["name"], "category": dest["category"]},
                    )

                counts["destinations"] += 1

            except Exception as e:
                logger.warning(f"Gagal simpan destination '{dest.get('name')}': {e}")
                counts["errors"] += 1

        # --- Simpan Restaurant ---
        for rest in entities.get("restaurants", []):
            if not rest.get("name"):
                continue
            try:
                rest_id = f"llm_{uuid.uuid4().hex[:8]}"
                self.neo4j.run_query(
                    """
                    MERGE (r:Restaurant {name: $name})
                    ON CREATE SET
                        r.restaurant_id  = $rest_id,
                        r.cuisine_type   = $cuisine_type,
                        r.description    = $description,
                        r.city           = $city,
                        r.price_level    = $price_level,
                        r.halal_status   = $halal_status,
                        r.source         = $source,
                        r.created_by     = 'llm_graph_builder'
                    ON MATCH SET
                        r.source = $source
                    """,
                    {
                        "name": rest["name"],
                        "rest_id": rest_id,
                        "cuisine_type": rest.get("cuisine_type"),
                        "description": rest.get("description"),
                        "city": rest.get("city"),
                        "price_level": rest.get("price_level"),
                        "halal_status": rest.get("halal_status", "unknown"),
                        "source": source,
                    },
                )

                # Auto-link ke City
                if rest.get("city"):
                    self.neo4j.run_query(
                        """
                        MATCH (r:Restaurant {name: $name})
                        MERGE (c:City {name: $city})
                        MERGE (r)-[:IS_IN]->(c)
                        """,
                        {"name": rest["name"], "city": rest["city"]},
                    )

                counts["restaurants"] += 1

            except Exception as e:
                logger.warning(f"Gagal simpan restaurant '{rest.get('name')}': {e}")
                counts["errors"] += 1

        # --- Simpan Relationships ---
        for rel in extracted.get("relationships", []):
            try:
                self._create_relationship(rel)
                counts["relationships"] += 1
            except Exception as e:
                logger.warning(f"Gagal buat relationship {rel}: {e}")
                counts["errors"] += 1

        return counts

    def _create_relationship(self, rel: dict):
        from_name = rel.get("from")
        to_name = rel.get("to")
        rel_type = rel.get("type", "RELATED_TO").upper().replace(" ", "_")
        properties = rel.get("properties") or {}

        if not from_name or not to_name:
            return

        # Relasi antara node apapun (Destination, Restaurant, City)
        query = f"""
        MATCH (a) WHERE a.name = $from_name
        MATCH (b) WHERE b.name = $to_name
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $properties
        """
        self.neo4j.run_query(query, {
            "from_name": from_name,
            "to_name": to_name,
            "properties": properties,
        })

    # ------------------------------------------------------------------
    # Step 3: Ringkasan natural language
    # ------------------------------------------------------------------

    def _generate_summary(self, extracted: dict, stored: dict, source: str) -> str:
        entities = extracted.get("entities", {})
        dest_names = [d.get("name") for d in entities.get("destinations", []) if d.get("name")]
        rest_names = [r.get("name") for r in entities.get("restaurants", []) if r.get("name")]

        parts = []
        if dest_names:
            parts.append(f"{len(dest_names)} destinasi ({', '.join(dest_names[:3])}{'...' if len(dest_names) > 3 else ''})")
        if rest_names:
            parts.append(f"{len(rest_names)} restoran ({', '.join(rest_names[:3])}{'...' if len(rest_names) > 3 else ''})")
        n_rel = stored.get("relationships", 0)
        if n_rel:
            parts.append(f"{n_rel} relasi antar entitas")

        if not parts:
            return f"Tidak ada entitas yang berhasil diekstrak dari sumber '{source}'."

        return (
            f"Berhasil mengekstrak dan menyimpan ke Neo4j dari sumber '{source}': "
            + ", ".join(parts) + "."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 3000,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "LLMGraphBuilder",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _parse_json_safe(response: str) -> dict:
        """Ekstrak JSON dari response LLM, toleran terhadap markdown code block."""
        # Coba ekstrak dari ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", response, re.IGNORECASE)
        json_str = match.group(1).strip() if match else response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse snippet: {response[:300]}")
            return {
                "entities": {"destinations": [], "restaurants": [], "cities": []},
                "relationships": [],
            }
