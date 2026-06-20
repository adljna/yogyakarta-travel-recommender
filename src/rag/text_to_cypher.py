"""
Text-to-Cypher: Mengubah pertanyaan natural language menjadi Cypher query
menggunakan LLM, lalu mengeksekusinya ke Neo4j dan menjelaskan hasilnya.

Komponen wajib Tier 4: LLM untuk Text-to-Cypher.
"""

import json
import logging
import re
import requests
from typing import Optional

from config import settings
from src.database.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

# Deskripsi schema Neo4j — dikirim ke LLM sebagai konteks
GRAPH_SCHEMA = """
NODE LABELS & PROPERTIES:
- Destination: {destination_id, name, category, region, city, borough,
    latitude, longitude, review_rating (float 0-5), review_count (int),
    open_hours, price_range, good_for_kids (bool), wheelchair_accessible (bool),
    has_toilet (bool), has_parking (bool), has_free_parking (bool),
    requires_appointment (bool), tickets_in_advance (bool),
    popularity_score (float), google_maps_url}
- Restaurant: {restaurant_id, name, category, region, city, latitude, longitude,
    review_rating (float 0-5), review_count (int), open_hours, price_range,
    outdoor_seating (bool), dine_in (bool), delivery_available (bool),
    great_coffee (bool), great_food (bool), google_maps_url, popularity_score}
- Category: {name}

RELATIONSHIPS:
- (Destination)-[:HAS_CATEGORY]->(Category)
- (Restaurant)-[:NEAR {distance_km: float}]->(Destination)
- (Destination)-[:CONNECTED_TO {distance_km, duration_minutes_car,
    duration_minutes_bike, transport_mode}]->(Destination)

CONTOH CYPHER QUERY VALID:
-- Destinasi dengan rating tinggi di Yogyakarta
MATCH (d:Destination) WHERE d.region = 'Yogyakarta' AND d.review_rating >= 4.5
RETURN d.name, d.category, d.review_rating LIMIT 10

-- Restoran terdekat dari sebuah destinasi
MATCH (r:Restaurant)-[:NEAR]->(d:Destination)
WHERE toLower(d.name) CONTAINS 'borobudur'
RETURN r.name, r.review_rating, r.price_range LIMIT 10

-- Destinasi berdasarkan kategori
MATCH (d:Destination)-[:HAS_CATEGORY]->(c:Category)
WHERE toLower(c.name) CONTAINS 'museum'
RETURN d.name, d.city, d.review_rating ORDER BY d.review_rating DESC LIMIT 10

-- Rute antara dua destinasi
MATCH (a:Destination)-[r:CONNECTED_TO]->(b:Destination)
WHERE toLower(a.name) CONTAINS 'borobudur' AND toLower(b.name) CONTAINS 'prambanan'
RETURN a.name, b.name, r.distance_km, r.duration_minutes_car

-- Destinasi cocok untuk anak-anak
MATCH (d:Destination) WHERE d.region = 'Yogyakarta' AND d.good_for_kids = true
RETURN d.name, d.category, d.review_rating ORDER BY d.review_rating DESC LIMIT 10
"""


class TextToCypherConverter:
    """
    Mengubah pertanyaan natural language ke Cypher query menggunakan LLM,
    mengeksekusinya ke Neo4j, dan menjelaskan hasilnya dalam Bahasa Indonesia.
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        self.neo4j = neo4j_client or Neo4jClient()
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model
        self.base_url = settings.llm_base_url

    def convert_and_execute(self, question: str) -> dict:
        """
        Pipeline lengkap: pertanyaan → Cypher → eksekusi → penjelasan.

        Returns:
            dict dengan keys: question, cypher, results, explanation, error
        """
        logger.info(f"Text-to-Cypher: '{question}'")

        # Step 1: Generate Cypher dari pertanyaan
        cypher = self._generate_cypher(question)
        logger.info(f"Generated Cypher:\n{cypher}")

        # Step 2: Eksekusi ke Neo4j
        results, error = self._execute_cypher(cypher)

        # Step 3: Jelaskan hasil dalam Bahasa Indonesia
        explanation = self._explain_results(question, cypher, results, error)

        return {
            "question": question,
            "cypher": cypher,
            "results": results,
            "explanation": explanation,
            "error": error,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_cypher(self, question: str) -> str:
        system_prompt = f"""Anda adalah expert Neo4j Cypher query generator untuk sistem rekomendasi wisata Yogyakarta.

Berdasarkan schema graph di bawah, buat Cypher query yang valid untuk menjawab pertanyaan user.

SCHEMA:
{GRAPH_SCHEMA}

ATURAN WAJIB:
- Kembalikan HANYA Cypher query di dalam blok ```cypher ... ```
- Gunakan LIMIT 20 kecuali user meminta jumlah tertentu
- Gunakan toLower() untuk string matching agar case-insensitive
- JANGAN gunakan APOC procedures
- JANGAN gunakan DETACH DELETE atau DROP
- Selalu RETURN field yang bermakna (name, rating, dll.)
- Untuk filter region, gunakan: d.region = 'Yogyakarta'"""

        response = self._call_llm(system_prompt, question, temperature=0.1, max_tokens=600)
        return self._extract_cypher_block(response)

    def _execute_cypher(self, cypher: str) -> tuple[list, Optional[str]]:
        try:
            results = self.neo4j.run_query(cypher)
            return results, None
        except Exception as e:
            logger.error(f"Cypher execution error: {e}")
            return [], str(e)

    def _explain_results(
        self,
        question: str,
        cypher: str,
        results: list,
        error: Optional[str],
    ) -> str:
        if error:
            prompt = (
                f"Query gagal dengan error: {error}\n"
                f"Query yang dicoba:\n{cypher}\n\n"
                "Jelaskan secara singkat masalahnya dan saran perbaikan dalam Bahasa Indonesia."
            )
        elif not results:
            prompt = (
                f"Pertanyaan: {question}\n"
                "Query berhasil dijalankan tetapi tidak ada data yang ditemukan.\n"
                "Berikan penjelasan singkat dan saran alternatif dalam Bahasa Indonesia."
            )
        else:
            sample = results[:5]
            prompt = (
                f"Pertanyaan: {question}\n"
                f"Query Cypher yang digunakan:\n{cypher}\n\n"
                f"Hasil (menampilkan {len(sample)} dari {len(results)} total):\n"
                f"{json.dumps(sample, ensure_ascii=False, indent=2)}\n\n"
                "Rangkum hasil ini secara ramah dalam 2-3 kalimat Bahasa Indonesia."
            )

        return self._call_llm(
            "Anda adalah asisten wisata yang membantu. Jawab singkat dan ramah dalam Bahasa Indonesia.",
            prompt,
            temperature=0.3,
            max_tokens=300,
        )

    def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "TextToCypher",
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
        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _extract_cypher_block(llm_response: str) -> str:
        """Ekstrak Cypher dari blok ```cypher ... ``` atau kembalikan teks asli."""
        match = re.search(r"```(?:cypher)?\s*([\s\S]+?)```", llm_response, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback: coba ekstrak baris yang diawali MATCH/CALL/RETURN
        lines = [
            line for line in llm_response.splitlines()
            if re.match(r"^\s*(MATCH|CALL|RETURN|WITH|WHERE|CREATE|MERGE|OPTIONAL)", line, re.IGNORECASE)
        ]
        if lines:
            return "\n".join(lines).strip()
        return llm_response.strip()
