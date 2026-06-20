"""Extract structured constraints dari natural language user request."""

import logging
import json
import requests
from typing import Dict, Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class ConstraintExtractor:
    """Extract user preferences menjadi structured constraints."""

    CONSTRAINT_SCHEMA = {
        "destination_area": "str (e.g., 'Yogyakarta')",
        "duration_days": "int",
        "budget_level": "'budget' | 'medium' | 'premium'",
        "daily_budget_idr": "int (IDR)",
        "interests": "list of ['Culture', 'Culinary', 'Nature', 'Beach', 'Adventure', 'Spiritual', 'Shopping']",
        "pace": "'slow' (2-3 dest/day) | 'normal' (3-4) | 'fast' (4-5+)",
        "start_location": "str (e.g., 'Stasiun Tugu')",
        "end_location": "str or null",
        "avoid_preferences": "list of str",
        "group_type": "'individual' | 'couple' | 'family' | 'group'",
        "travel_dates": "{'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD'}",
        "min_rating": "float (3.0-5.0)",
        "preferred_halal": "bool",
        "good_for_kids": "bool (true jika bawa anak-anak)",
        "needs_wheelchair": "bool (true jika butuh akses kursi roda)",
        "include_culinary": "bool (default true)",
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = settings.llm_model
        self.base_url = settings.llm_base_url

    def extract(self, user_message: str) -> Dict[str, Any]:
        """
        Extract constraints dari natural language input.

        Args:
            user_message: User's natural language request

        Returns:
            dict: Structured constraints
        """

        system_prompt = f"""
Anda adalah expert dalam ekstraksi preferensi wisata dari natural language.
Analisis input user dan ekstrak constraint travel dalam format JSON yang terstandar.

CRITICAL RULES:
1. Output HARUS valid JSON saja, tanpa preamble atau markdown fence.
2. Jika value tidak disebut, gunakan default atau null.
3. Pastikan semua field ada di output JSON.

SCHEMA:
{json.dumps(self.CONSTRAINT_SCHEMA, indent=2, ensure_ascii=False)}

CONTOH OUTPUT:
{{
  "destination_area": "Yogyakarta",
  "duration_days": 3,
  "budget_level": "medium",
  "daily_budget_idr": 1500000,
  "interests": ["Culture", "Culinary"],
  "pace": "slow",
  "start_location": "Stasiun Tugu",
  "end_location": null,
  "avoid_preferences": ["crowded places", "outdoor in rain"],
  "group_type": "individual",
  "travel_dates": {{
    "start_date": "2024-07-15",
    "end_date": "2024-07-17"
  }},
  "min_rating": 3.5,
  "preferred_halal": true,
  "good_for_kids": false,
  "needs_wheelchair": false,
  "include_culinary": true
}}
"""

        try:
            logger.info("Extracting constraints dari user message...")

            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "ItineraryRecommendationSystem",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1000,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                },
                timeout=30,
            )
            if not response.ok:
                logger.error(f"OpenRouter error {response.status_code}: {response.text[:300]}")
            response.raise_for_status()

            # Parse JSON response — strip markdown fence jika model menambahkannya
            json_text = response.json()["choices"][0]["message"]["content"].strip()
            if json_text.startswith("```"):
                json_text = json_text.split("```")[1]
                if json_text.startswith("json"):
                    json_text = json_text[4:]
            constraints = json.loads(json_text.strip())
            
            # Validate constraints
            self._validate_constraints(constraints)
            
            logger.info(f"Constraints extracted successfully: {constraints}")
            return constraints
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            raise ValueError("Failed to parse LLM response as JSON")
        except Exception as e:
            logger.error(f"Constraint extraction error: {str(e)}")
            raise
    
    def find_missing_required(self, constraints: Dict[str, Any]) -> list:
        """
        Identifikasi field kritis yang belum diisi user.
        Dipanggil setelah extract() untuk tahu apa yang perlu ditanyakan.

        Returns:
            List of field names yang perlu ditanya ke user.
        """
        missing = []

        duration = constraints.get("duration_days")
        if not duration or not isinstance(duration, (int, float)) or duration < 1:
            missing.append("duration_days")

        # destination_area default ke Yogyakarta untuk MVP
        if not constraints.get("destination_area"):
            constraints["destination_area"] = "Yogyakarta"

        return missing

    @staticmethod
    def _validate_constraints(constraints: Dict[str, Any]) -> bool:
        """
        Validate struktur constraints — hanya cek tipe, bukan kelengkapan.
        Field yang null/kosong ditangani via find_missing_required + ask_missing_fields.
        """
        interests = constraints.get("interests")
        if interests is not None and not isinstance(interests, list):
            constraints["interests"] = []

        travel_dates = constraints.get("travel_dates")
        if travel_dates is not None and not isinstance(travel_dates, dict):
            constraints["travel_dates"] = None

        return True
