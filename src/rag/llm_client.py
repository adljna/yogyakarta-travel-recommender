"""LLM client untuk generate itinerary dari graph context (data Google Maps)."""

import logging
import json
import re
import requests
from typing import Dict, Any

from config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Client untuk OpenRouter API + graph context dari Neo4j."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens
        self.base_url = settings.llm_base_url

    def generate_itinerary(
        self,
        constraints: Dict[str, Any],
        graph_context: Dict[str, Any],
    ) -> str:
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_prompt(constraints, graph_context)

        duration = constraints.get('duration_days', 3)
        region = constraints.get('destination_area', 'Yogyakarta')

        # Prefill paksa model mulai langsung dengan header itinerary,
        # bukan dengan reasoning/planning text
        assistant_prefill = f"# Itinerary {region}, {duration} Hari"

        try:
            logger.info("Generating itinerary via LLM...")
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
                    "max_tokens": self.max_tokens,
                    "include_reasoning": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                        # Prefill: model dipaksa lanjutkan dari sini
                        {"role": "assistant", "content": assistant_prefill},
                    ],
                },
                timeout=90,
            )
            if not response.ok:
                logger.error(f"OpenRouter error {response.status_code}: {response.text[:300]}")
            response.raise_for_status()

            raw = response.json()["choices"][0]["message"]["content"]
            itinerary = self._strip_reasoning(raw)

            # OpenRouter returns only the continuation after assistant prefill,
            # so prepend the header back if it's missing
            stripped = itinerary.lstrip()
            if not stripped.startswith('# Itinerary'):
                itinerary = f"{assistant_prefill}\n{itinerary}"

            logger.info("Itinerary generated successfully")
            return itinerary

        except Exception as e:
            logger.error(f"Error generating itinerary: {str(e)}")
            raise

    @staticmethod
    def _strip_reasoning(text: str) -> str:
        """Hapus reasoning dari output reasoning model (tagged dan plain-text)."""
        # 1. Hapus blok reasoning bertag (multiline, case-insensitive)
        tag_patterns = [
            r'<think>.*?</think>',
            r'<thinking>.*?</thinking>',
            r'<reasoning>.*?</reasoning>',
            r'<thought>.*?</thought>',
        ]
        for pattern in tag_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)

        # 2. Untuk plain-text reasoning, cari marker awal itinerary
        #    dan potong semua teks sebelumnya
        markers = ['# Itinerary', '## Hari 1', '## Ringkasan', '| Waktu |']
        for marker in markers:
            if marker in text:
                idx = text.index(marker)
                text = text[idx:]
                break

        return text.strip()

    @staticmethod
    def _get_system_prompt() -> str:
        return """Anda adalah formatter itinerary wisata. Destinasi per hari sudah ditentukan — tugas Anda HANYA memformat menjadi tabel markdown.

FORMAT OUTPUT (ikuti PERSIS, mulai langsung dari baris pertama):

**Periode:** X – Y | **Budget:** Z/hari | **Pace:** P | **Grup:** G

## Ringkasan
| Total Hari | Est. Budget | Highlight |
|------------|-------------|-----------|
| X hari | Rp X | Tempat A, B, C |

## Hari 1: YYYY-MM-DD
| Waktu | Aktivitas | Durasi | Info |
|-------|-----------|--------|------|
| 08:00 | Nama [Kategori] | 90 mnt | ⭐4.7 (1.2rb ulasan) • 08:00-17:00 • Rp 50k • Parkir gratis |
| 09:30 | 🚗 ke Tempat Berikut | 15 mnt | ~5 km |
| 12:30 | Makan siang: Nama Resto | 60 mnt | ⭐4.5 • Rp 30-60k |
| 18:00 | Makan malam: Nama Resto | 60 mnt | ⭐4.6 • Rp 40-80k |
**Biaya hari ini:** Rp X

[Ulangi untuk setiap hari]

## Tips
- [3 tips singkat]

## Rincian Budget
| Tiket | Makan | Transport | Total |
|-------|-------|-----------|-------|
| Rp X | Rp X | Rp X | Rp X |

ATURAN WAKTU WAJIB:
- Makan SIANG = TEPAT jam 12:00 (jangan geser, selalu 12:00).
- Makan MALAM = jam 18:00 ke atas, dan SELALU menjadi agenda TERAKHIR hari itu.
- Destinasi wisata diisi di slot PAGI (08:00–11:xx) dan SORE (setelah makan siang hingga ~17:xx).
- Makan malam TIDAK BOLEH dijadwalkan sebelum jam 18:00.
Estimasikan travel time antar destinasi. Budget per hari ≤ daily_budget.
"""

    @staticmethod
    def _fmt_dest(dest: dict, idx: int) -> str:
        """Format satu destinasi sebagai 1-2 baris teks ringkas (hemat token)."""
        amenities = []
        if dest.get('has_free_parking'):
            amenities.append('Parkir gratis')
        elif dest.get('has_parking'):
            amenities.append('Parkir')
        if dest.get('has_toilet'):
            amenities.append('Toilet')
        if dest.get('good_for_kids'):
            amenities.append('Cocok anak')
        if dest.get('wheelchair_accessible'):
            amenities.append('Kursi roda OK')
        if dest.get('requires_appointment'):
            amenities.append('BOOKING DULU')
        if dest.get('tickets_in_advance'):
            amenities.append('Beli tiket dulu')

        fac = ' | ' + ', '.join(amenities) if amenities else ''
        price = dest.get('price_range') or ''
        price_str = f' | {price}' if price else ''
        hours = dest.get('open_hours') or 'Jam: N/A'

        return (
            f"{idx}. {dest.get('name')} [{dest.get('category')}]"
            f" ⭐{dest.get('review_rating')} ({dest.get('review_count')} ulasan)"
            f" | {hours}{price_str}{fac}"
        )

    @staticmethod
    def _fmt_culinary(spot: dict, idx: int) -> str:
        """Format satu restoran/cafe secara ringkas."""
        flags = []
        if spot.get('great_coffee'):
            flags.append('Great coffee')
        if spot.get('great_food'):
            flags.append('Great food')
        extra = ' | ' + ', '.join(flags) if flags else ''
        price = spot.get('price_range') or 'N/A'
        return (
            f"{idx}. {spot.get('name')} [{spot.get('category')}]"
            f" ⭐{spot.get('review_rating')} ({spot.get('review_count')} ulasan)"
            f" | {spot.get('open_hours') or 'N/A'} | {price}{extra}"
        )

    def _build_user_prompt(
        self,
        constraints: Dict[str, Any],
        graph_context: Dict[str, Any],
    ) -> str:
        from datetime import date, timedelta

        duration = constraints.get('duration_days', 3)
        pace = constraints.get('pace', 'normal')
        c = constraints

        # Jumlah destinasi per hari
        spots_per_day = {'slow': 2, 'normal': 3, 'fast': 4}.get(pace, 3)
        total_spots = spots_per_day * duration

        all_dests = graph_context.get('destinations', [])
        all_culinary = graph_context.get('culinary_spots', [])

        # PRE-ALOKASI per hari di Python — model tidak perlu memutuskan ini
        # Round-robin interleave: dest[0]→hari1, dest[1]→hari2, ... supaya tiap hari dapat mix ranking
        pool = all_dests[:total_spots]
        day_dests: list[list] = [[] for _ in range(duration)]
        for i, dest in enumerate(pool):
            day_dests[i % duration].append(dest)

        # Pasangkan kuliner: 2 per hari (lunch + dinner)
        culinary_pool = all_culinary[:duration * 2]

        start_str = c.get('travel_dates', {}).get('start_date', '')
        end_str = c.get('travel_dates', {}).get('end_date', '')

        try:
            start_date = date.fromisoformat(start_str)
        except Exception:
            start_date = date.today()

        lines: list[str] = []

        # Header ringkas
        lines.append(
            f"Durasi: {duration} hari ({start_str}–{end_str}) | "
            f"Budget: {c.get('budget_level')} Rp{c.get('daily_budget_idr', 1500000):,}/hari | "
            f"Pace: {pace} | Grup: {c.get('group_type')} | "
            f"Interests: {', '.join(c.get('interests', []))}"
        )

        # Satu seksi per hari dengan destinasi yang sudah ditentukan
        for day_idx in range(duration):
            day_date = (start_date + timedelta(days=day_idx)).isoformat()
            lines.append(f"\n## HARI {day_idx + 1}: {day_date}")
            lines.append("Destinasi (format menjadi tabel, urut pagi→malam):")
            for i, dest in enumerate(day_dests[day_idx], 1):
                lines.append(self._fmt_dest(dest, i))

            lunch_idx = day_idx * 2
            dinner_idx = day_idx * 2 + 1
            if lunch_idx < len(culinary_pool):
                r = culinary_pool[lunch_idx]
                lines.append(
                    f"Makan siang (WAJIB jam 12:00): {r.get('name')} [{r.get('category')}]"
                    f" ⭐{r.get('review_rating')} ({r.get('review_count')} ulasan)"
                    f" | {r.get('open_hours') or 'N/A'} | {r.get('price_range') or 'N/A'}"
                )
            if dinner_idx < len(culinary_pool):
                r = culinary_pool[dinner_idx]
                lines.append(
                    f"Makan malam (WAJIB ≥18:00, agenda TERAKHIR hari ini): {r.get('name')} [{r.get('category')}]"
                    f" ⭐{r.get('review_rating')} ({r.get('review_count')} ulasan)"
                    f" | {r.get('open_hours') or 'N/A'} | {r.get('price_range') or 'N/A'}"
                )

        lines.append(
            f"\nFormat semua {duration} hari menjadi tabel markdown. "
            f"Tambahkan waktu mulai, durasi, dan 🚗 travel antar tempat. "
            f"Hitung biaya estimasi tiap hari. LANGSUNG output tabel.\n"
            f"WAJIB: makan siang selalu jam 12:00, makan malam selalu ≥18:00 dan menjadi baris terakhir hari itu. "
            f"Atur destinasi wisata di slot pagi (08:00–11:xx) dan sore (13:xx–17:xx) mengapit dua slot makan tersebut."
        )

        return '\n'.join(lines)
