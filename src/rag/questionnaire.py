"""Step-by-step questionnaire untuk collect user travel preferences."""

import re
from datetime import date, timedelta
from typing import Any

SKIP_TOKENS = {"", "skip", "tidak tahu", "ga tau", "gak tau", "bingung", "lewat", "-", "n/a"}


def _is_skip(text: str) -> bool:
    return text.strip().lower() in SKIP_TOKENS


def _ask(prompt: str, default: Any = None) -> str:
    """Print prompt dan return raw input."""
    suffix = f" [default: {default}]" if default is not None else " [wajib]"
    return input(f"\n{prompt}{suffix}\n> ").strip()


def _ask_choice(prompt: str, options: list[str], default_index: int = 0) -> str:
    """Tampilkan numbered choices, return nilai yang dipilih."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if i - 1 == default_index else ""
        print(f"  {i}. {opt}{marker}")
    raw = input("> ").strip().lower()

    if _is_skip(raw):
        return options[default_index]

    # Terima angka
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]

    # Terima teks partial match
    for opt in options:
        if raw in opt.lower():
            return opt

    print(f"  Input tidak dikenali, pakai default: {options[default_index]}")
    return options[default_index]


def _ask_multi_choice(prompt: str, options: list[str], defaults: list[str]) -> list[str]:
    """Pilih beberapa opsi sekaligus (comma-separated nomor atau nama)."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"  (Pilih beberapa, pisahkan koma. Contoh: 1,3 atau Culture,Nature)")
    print(f"  default: {', '.join(defaults)}")
    raw = input("> ").strip()

    if _is_skip(raw):
        return defaults

    selected = []
    parts = [p.strip() for p in raw.split(",")]
    for part in parts:
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(options):
                selected.append(options[idx])
        else:
            for opt in options:
                if part.lower() in opt.lower():
                    selected.append(opt)
                    break

    return selected if selected else defaults


def _ask_date(prompt: str, default: date) -> str:
    """Minta input tanggal, return string YYYY-MM-DD."""
    while True:
        raw = _ask(prompt, default.strftime("%d/%m/%Y") + " (format: DD/MM/YYYY)")
        if _is_skip(raw):
            return default.isoformat()
        try:
            # Support beberapa format
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    return date(*[int(x) for x in re.split(r"[-/]", raw)][::-1] if fmt == "%d/%m/%Y"
                                 else []).isoformat()
                except Exception:
                    pass
            # Fallback: coba parse manual dd/mm/yyyy
            parts = re.split(r"[-/]", raw)
            if len(parts) == 3:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d).isoformat()
        except Exception:
            print("  Format tanggal tidak valid, coba lagi (DD/MM/YYYY)")


def run_questionnaire() -> dict:
    """
    Jalankan guided questionnaire dan return constraints dict.
    Output format sama dengan ConstraintExtractor sehingga pipeline tidak berubah.
    """
    print("\n" + "=" * 60)
    print("  ITINERARY RECOMMENDATION — TRAVEL PLANNER")
    print("=" * 60)
    print("Ketik 'skip' atau tekan Enter untuk pakai nilai default.\n")

    constraints = {}

    # ── 1. KOTA TUJUAN ─────────────────────────────────────────
    available_regions = [
        "Yogyakarta", "Bali", "Bandung", "Jakarta",
        "Surabaya", "Lombok", "Labuan Bajo", "Medan",
    ]
    city = _ask_choice("1. Mau liburan di kota / daerah mana?", available_regions, default_index=0)
    constraints["destination_area"] = city

    # ── 2. DURASI ──────────────────────────────────────────────
    while True:
        raw = _ask("2. Berapa hari rencananya?", default=3)
        if _is_skip(raw):
            constraints["duration_days"] = 3
            break
        if raw.isdigit() and int(raw) >= 1:
            constraints["duration_days"] = int(raw)
            break
        print("  Masukkan angka ≥ 1.")

    # ── 3. TANGGAL MULAI ───────────────────────────────────────
    default_start = date.today() + timedelta(days=7)
    start_str = _ask_date("3. Tanggal mulai keberangkatan?", default_start)
    start_date = date.fromisoformat(start_str)
    end_date = start_date + timedelta(days=constraints["duration_days"] - 1)
    constraints["travel_dates"] = {
        "start_date": start_str,
        "end_date": end_date.isoformat(),
    }
    print(f"  Periode: {start_str} s/d {end_date.isoformat()}")

    # ── 4. JENIS WISATA ────────────────────────────────────────
    interest_options = ["Culture", "Culinary", "Nature", "Beach", "Adventure", "Spiritual", "Shopping"]
    interests = _ask_multi_choice(
        "4. Suka wisata yang seperti apa? (boleh pilih lebih dari satu)",
        interest_options,
        defaults=["Culture", "Culinary"],
    )
    constraints["interests"] = interests

    # ── 5. BUDGET ──────────────────────────────────────────────
    budget_map = {
        "Budget (< Rp 500k/hari)": ("budget", 400000),
        "Medium (Rp 500k – 2jt/hari)": ("medium", 1500000),
        "Premium (> Rp 2jt/hari)": ("premium", 3000000),
    }
    budget_choice = _ask_choice(
        "5. Budget per hari kira-kira berapa?",
        list(budget_map.keys()),
        default_index=1,
    )
    constraints["budget_level"], constraints["daily_budget_idr"] = budget_map[budget_choice]

    # ── 6. PACE ────────────────────────────────────────────────
    pace_options = ["slow (2-3 destinasi/hari)", "normal (3-4 destinasi/hari)", "fast (4-5+ destinasi/hari)"]
    pace_raw = _ask_choice("6. Prefer jalan santai atau padat?", pace_options, default_index=0)
    constraints["pace"] = pace_raw.split()[0]  # ambil "slow" / "normal" / "fast"

    # ── 7. TIPE GRUP ───────────────────────────────────────────
    group_options = ["individual", "couple", "family", "group"]
    constraints["group_type"] = _ask_choice("7. Pergi sama siapa?", group_options, default_index=0)

    # ── 8. HALAL ───────────────────────────────────────────────
    halal_raw = _ask_choice(
        "8. Perlu filter restoran halal?",
        ["Ya", "Tidak"],
        default_index=0,
    )
    constraints["preferred_halal"] = halal_raw.lower() == "ya"

    # ── 9. PERJALANAN DENGAN ANAK? ─────────────────────────────
    kids_raw = _ask_choice(
        "9. Perjalanan bersama anak-anak? (filter destinasi ramah anak)",
        ["Ya", "Tidak"],
        default_index=1,
    )
    constraints["good_for_kids"] = kids_raw.lower() == "ya"

    # ── 10. KEBUTUHAN AKSESIBILITAS ────────────────────────────
    wheelchair_raw = _ask_choice(
        "10. Perlu akses kursi roda / ramah disabilitas?",
        ["Ya", "Tidak"],
        default_index=1,
    )
    constraints["needs_wheelchair"] = wheelchair_raw.lower() == "ya"

    # ── DEFAULTS ───────────────────────────────────────────────
    constraints["avoid_preferences"] = []
    constraints["start_location"] = "pusat kota"
    constraints["end_location"] = None
    constraints.setdefault("min_rating", 3.5)
    constraints.setdefault("include_culinary", True)

    # ── SUMMARY ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RINGKASAN PREFERENSI KAMU")
    print("=" * 60)
    print(f"  Kota          : {constraints['destination_area']}")
    print(f"  Durasi        : {constraints['duration_days']} hari")
    print(f"  Tanggal       : {constraints['travel_dates']['start_date']} s/d {constraints['travel_dates']['end_date']}")
    print(f"  Minat         : {', '.join(constraints['interests'])}")
    print(f"  Budget        : {constraints['budget_level']} (Rp {constraints['daily_budget_idr']:,}/hari)")
    print(f"  Pace          : {constraints['pace']}")
    print(f"  Grup          : {constraints['group_type']}")
    print(f"  Halal         : {'Ya' if constraints['preferred_halal'] else 'Tidak'}")
    print(f"  Ramah anak    : {'Ya' if constraints['good_for_kids'] else 'Tidak'}")
    print(f"  Akses kursi roda: {'Ya' if constraints['needs_wheelchair'] else 'Tidak'}")
    print("=" * 60)

    confirm = input("\nLanjut generate itinerary? (Enter = ya, ketik 'ulang' untuk mulai ulang)\n> ").strip().lower()
    if confirm == "ulang":
        return run_questionnaire()

    return constraints
