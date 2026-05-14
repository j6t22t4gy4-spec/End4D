"""Persona dataset adapter for world genesis.

Datasets stay outside the repo and are configured per country. The adapter
supports JSONL/CSV snapshots so large Hugging Face datasets can be pre-sampled
without making the engine depend on heavyweight data loaders.
"""
from __future__ import annotations

import csv
import hashlib
import heapq
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.core.data_packs import resolve_country_pack_info, resolve_country_pack_path


COUNTRY_ALIASES = {
    "kr": "KR",
    "kor": "KR",
    "korea": "KR",
    "south_korea": "KR",
    "south korea": "KR",
    "대한민국": "KR",
    "한국": "KR",
    "us": "US",
    "usa": "US",
    "united states": "US",
    "미국": "US",
    "jp": "JP",
    "japan": "JP",
    "일본": "JP",
}

PERSONA_TEXT_FIELDS = (
    "professional_persona",
    "persona",
    "concise_persona",
    "summary_persona",
    "sports_persona",
    "arts_persona",
    "travel_persona",
    "culinary_persona",
    "family_persona",
)

ROLE_FIELDS = ("occupation", "role", "job", "profession")

ATTR_FIELDS = (
    "name",
    "agent_name",
    "display_name",
    "sex",
    "age",
    "marital_status",
    "education_level",
    "occupation",
    "district",
    "province",
    "country",
    "cultural_background",
    "skills_and_expertise",
    "hobbies_and_interests",
    "career_goals_and_ambitions",
)

KNOWN_HF_DATASETS = {
    "nvidia/Nemotron-Personas-Korea": {
        "license": "CC BY 4.0",
        "url": "https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea",
        "attribution_required": True,
        "citation": "Nemotron-Personas-Korea: Synthetic Personas Aligned to Real-World Distributions for Korea, NVIDIA Corporation, 2026.",
    }
}


@dataclass
class PersonaSeed:
    persona_id: str
    persona_text: str
    role_key: str = "agent"
    role_label: str = "agent"
    country: str = ""
    attrs: Dict[str, Any] = field(default_factory=dict)


def normalize_country(value: Optional[str]) -> str:
    if not value:
        return ""
    key = value.strip().lower()
    return COUNTRY_ALIASES.get(key, value.strip().upper())


def infer_country_from_prompt(prompt: str) -> str:
    text = prompt.lower()
    for key, code in COUNTRY_ALIASES.items():
        if key.lower() in text:
            return code
    return ""


def configured_persona_path(country: str) -> Optional[Path]:
    code = normalize_country(country)
    specific = os.getenv(f"ORGANIC4D_PERSONA_DATASET_{code}", "").strip()
    if specific:
        return Path(specific)

    base_dir = os.getenv("ORGANIC4D_PERSONA_DATASET_DIR", "").strip()
    if base_dir and code:
        for ext in ("jsonl", "json", "csv"):
            p = Path(base_dir) / f"{code.lower()}.{ext}"
            if p.exists():
                return p

    if configured_hf_dataset(code):
        return None

    pack_path = resolve_country_pack_path(code, kind="persona")
    if pack_path is not None and pack_path.exists():
        return pack_path
    return None


def configured_hf_dataset(country: str) -> str:
    code = normalize_country(country)
    return os.getenv(f"ORGANIC4D_PERSONA_HF_DATASET_{code}", "").strip()


def persona_source_label(country: str) -> str:
    path = configured_persona_path(country)
    if path is not None and path.exists():
        pack = resolve_country_pack_info(normalize_country(country), kind="persona")
        if pack is not None and str(pack.get("path") or "") == str(path):
            return f"local-pack:{pack['pack_id']}@{pack['version']}"
        return f"local:{path}"
    hf_dataset = configured_hf_dataset(country)
    if hf_dataset:
        return f"hf:{hf_dataset}"
    return f"not_configured:{normalize_country(country)}"


def persona_source_info(country: str) -> dict:
    """Return configured source and attribution metadata for a country."""
    code = normalize_country(country)
    path = configured_persona_path(code)
    hf_dataset = configured_hf_dataset(code)

    if path is not None and path.exists():
        pack = resolve_country_pack_info(code, kind="persona")
        if pack is not None and str(pack.get("path") or "") == str(path):
            return {
                "country": code,
                "source": f"local-pack:{pack['pack_id']}@{pack['version']}",
                "dataset_id": str(pack.get("dataset_id") or pack.get("pack_id") or ""),
                "path": str(path),
                "license": str(pack.get("license") or ""),
                "url": str(pack.get("source_url") or ""),
                "attribution_required": bool(pack.get("license")),
                "citation": "",
                "configured": True,
            }
        return {
            "country": code,
            "source": f"local:{path}",
            "dataset_id": "",
            "path": str(path),
            "license": "",
            "url": "",
            "attribution_required": False,
            "citation": "",
            "configured": True,
        }

    if hf_dataset:
        meta = KNOWN_HF_DATASETS.get(hf_dataset, {})
        return {
            "country": code,
            "source": f"hf:{hf_dataset}",
            "dataset_id": hf_dataset,
            "path": "",
            "license": str(meta.get("license", "")),
            "url": str(meta.get("url", "")),
            "attribution_required": bool(meta.get("attribution_required", False)),
            "citation": str(meta.get("citation", "")),
            "configured": True,
        }

    return {
        "country": code,
        "source": f"not_configured:{code}",
        "dataset_id": "",
        "path": "",
        "license": "",
        "url": "",
        "attribution_required": False,
        "citation": "",
        "configured": False,
    }


def persona_source_info_from_label(country: str, source: str, configured: bool) -> dict:
    """Build source metadata from the source stored on a world."""
    code = normalize_country(country)
    if source.startswith("hf:"):
        dataset_id = source[3:]
        meta = KNOWN_HF_DATASETS.get(dataset_id, {})
        return {
            "country": code,
            "source": source,
            "dataset_id": dataset_id,
            "path": "",
            "license": str(meta.get("license", "")),
            "url": str(meta.get("url", "")),
            "attribution_required": bool(meta.get("attribution_required", False)),
            "citation": str(meta.get("citation", "")),
            "configured": configured,
        }
    if source.startswith("local:"):
        return {
            "country": code,
            "source": source,
            "dataset_id": "",
            "path": source[6:],
            "license": "",
            "url": "",
            "attribution_required": False,
            "citation": "",
            "configured": configured,
        }
    if source.startswith("local-pack:"):
        pack = resolve_country_pack_info(code, kind="persona") or {}
        pack_id_version = source[len("local-pack:") :]
        pack_id = pack_id_version.split("@", 1)[0]
        return {
            "country": code,
            "source": source,
            "dataset_id": str(pack.get("dataset_id") or pack_id),
            "path": str(pack.get("path") or ""),
            "license": str(pack.get("license") or ""),
            "url": str(pack.get("source_url") or ""),
            "attribution_required": bool(pack.get("license")),
            "citation": "",
            "configured": configured,
        }
    return persona_source_info(code)


def _max_scan_rows() -> int:
    raw = os.getenv("ORGANIC4D_PERSONA_MAX_SCAN", "20000").strip()
    try:
        return max(100, int(raw))
    except ValueError:
        return 20000


def _iter_rows(path: Path) -> Iterable[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        yield row
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        rows = data if isinstance(data, list) else data.get("rows", [])
        for row in rows:
            if isinstance(row, dict):
                yield row
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)


def _iter_hf_rows(dataset_id: str) -> Iterable[Dict[str, Any]]:
    try:
        from datasets import load_dataset
    except Exception:
        return

    ds = load_dataset(dataset_id, split="train", streaming=True)
    for row in ds:
        if isinstance(row, dict):
            yield row


def _row_to_persona(row: Dict[str, Any], fallback_country: str) -> PersonaSeed:
    persona_text = ""
    for field_name in PERSONA_TEXT_FIELDS:
        v = str(row.get(field_name, "") or "").strip()
        if v:
            persona_text = v
            break

    role = "agent"
    for field_name in ROLE_FIELDS:
        v = str(row.get(field_name, "") or "").strip()
        if v:
            role = v
            break

    raw_id = str(row.get("uuid") or row.get("id") or "").strip()
    if not raw_id:
        raw_id = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

    country = normalize_country(str(row.get("country", "") or fallback_country))
    attrs = {k: row[k] for k in ATTR_FIELDS if k in row and row[k] not in ("", None)}
    return PersonaSeed(
        persona_id=raw_id,
        persona_text=persona_text or role,
        role_key=role,
        role_label=role,
        country=country,
        attrs=attrs,
    )


def load_persona_seeds(
    country: str,
    count: int,
    seed_text: str,
) -> List[PersonaSeed]:
    """Load a deterministic sample of personas for a country.

    Returns an empty list when no configured dataset is available.
    """
    if count <= 0:
        return []

    path = configured_persona_path(country)
    hf_dataset = configured_hf_dataset(country)
    if path is not None and path.exists():
        rows = _iter_rows(path)
    elif hf_dataset:
        rows = _iter_hf_rows(hf_dataset)
    else:
        return []

    heap: list[tuple[int, int, Dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        if idx >= _max_scan_rows():
            break
        raw_id = str(row.get("uuid") or row.get("id") or idx)
        digest = hashlib.sha256(f"{seed_text}|{raw_id}|{idx}".encode("utf-8")).digest()
        score = int.from_bytes(digest[:8], "big")
        item = (-score, idx, row)
        if len(heap) < count:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)

    selected = [row for _, _, row in sorted(heap, reverse=True)]
    return [_row_to_persona(row, fallback_country=country) for row in selected]


def personas_to_dicts(personas: List[PersonaSeed]) -> List[dict]:
    return [
        {
            "persona_id": p.persona_id,
            "persona_text": p.persona_text,
            "role_key": p.role_key,
            "role_label": p.role_label,
            "country": p.country,
            "attrs": dict(p.attrs),
        }
        for p in personas
    ]


def summarize_persona_distribution(personas: List[PersonaSeed]) -> dict:
    role_counts: dict[str, int] = {}
    region_counts: dict[str, int] = {}
    age_buckets = {"youth": 0, "working": 0, "senior": 0, "unknown": 0}

    for persona in personas:
        role = (persona.role_label or persona.role_key or "agent").strip() or "agent"
        role_counts[role] = role_counts.get(role, 0) + 1

        region = _persona_region(persona) or (persona.country or "unknown")
        region_counts[region] = region_counts.get(region, 0) + 1

        age_buckets[_age_bucket(persona.attrs.get("age"))] += 1

    top_roles = sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))
    top_regions = sorted(region_counts.items(), key=lambda item: (-item[1], item[0]))
    total = max(1, len(personas))
    diversity = round(len(role_counts) / total, 4)
    regionality = round(len(region_counts) / total, 4)
    return {
        "persona_count": len(personas),
        "role_counts": role_counts,
        "top_roles": [{"label": label, "count": count} for label, count in top_roles[:8]],
        "region_counts": region_counts,
        "top_regions": [{"label": label, "count": count} for label, count in top_regions[:8]],
        "age_buckets": age_buckets,
        "role_diversity": diversity,
        "regional_diversity": regionality,
    }


def infer_role_catalog_from_personas(personas: List[PersonaSeed], *, limit: int = 8) -> List[str]:
    summary = summarize_persona_distribution(personas)
    roles = [str(item["label"]).strip() for item in summary["top_roles"] if str(item.get("label") or "").strip()]
    return roles[: max(1, limit)]


def persona_genesis_bias(personas: List[PersonaSeed]) -> dict:
    summary = summarize_persona_distribution(personas)
    persona_count = max(1, int(summary["persona_count"]))
    top_regions = list(summary["top_regions"])
    top_roles = list(summary["top_roles"])
    youth_share = summary["age_buckets"]["youth"] / persona_count
    senior_share = summary["age_buckets"]["senior"] / persona_count
    working_share = summary["age_buckets"]["working"] / persona_count
    market_share = _persona_token_share(
        personas,
        ["entrepreneur", "founder", "business", "trader", "investor", "자영업", "사업", "투자", "상인", "시장"],
    )
    public_share = _persona_token_share(
        personas,
        ["teacher", "nurse", "social worker", "care", "public", "교사", "간호", "복지", "공무", "정부", "공공"],
    )
    mobile_share = _persona_token_share(
        personas,
        ["driver", "delivery", "field", "sales", "logistics", "운전", "배송", "영업", "물류", "이동"],
    )
    urban_share = _persona_token_share(
        personas,
        ["capital", "seoul", "metro", "urban", "서울", "수도권", "도심", "부산", "대구", "인천"],
    )
    zone_count = max(1, min(8, len(top_regions) or 1))
    z_mode = "influence" if len(top_roles) >= 4 else "hybrid"
    nutrient_multiplier = 1.0 + min(0.45, summary["role_diversity"] * 1.2)
    if senior_share > 0.35:
        nutrient_multiplier += 0.08
    if youth_share > 0.35:
        nutrient_multiplier += 0.06
    return {
        "summary": summary,
        "role_catalog": [item["label"] for item in top_roles[:8]],
        "zone_count": zone_count,
        "zone_layout": "bands" if zone_count >= 3 else "grid",
        "regional_labels": [item["label"] for item in top_regions[:8]],
        "nutrient_multiplier": round(nutrient_multiplier, 4),
        "z_mode": z_mode,
        "z_scale_multiplier": round(1.0 + min(0.22, summary["regional_diversity"] * 0.8), 4),
        "zone_influence_step": round(0.06 + min(0.08, public_share * 0.08 + urban_share * 0.04), 4),
        "zone_friction_step": round(0.06 + min(0.1, mobile_share * 0.05 + summary["regional_diversity"] * 0.08), 4),
        "initial_bias": {
            "energy_offset": round((working_share * 1.2) + (senior_share * 2.0) - (youth_share * 1.2) + (market_share * 1.3), 4),
            "cooperation_delta": round(public_share * 0.08 + senior_share * 0.02, 4),
            "policy_sensitivity_delta": round(public_share * 0.07 + urban_share * 0.04 + youth_share * 0.02, 4),
            "resource_delta": round(market_share * 0.1 + working_share * 0.02, 4),
            "mobility_delta": round(mobile_share * 0.1 + youth_share * 0.04 - senior_share * 0.03, 4),
        },
    }


def _persona_token_share(personas: List[PersonaSeed], tokens: List[str]) -> float:
    if not personas:
        return 0.0
    hits = 0
    lowered_tokens = [token.lower() for token in tokens]
    for persona in personas:
        attrs = dict(persona.attrs or {})
        text = " ".join(
            [
                persona.role_key,
                persona.role_label,
                persona.persona_text,
                str(attrs.get("occupation", "")),
                str(attrs.get("hobbies_and_interests", "")),
                str(attrs.get("province", "")),
                str(attrs.get("district", "")),
                str(attrs.get("region", "")),
                str(attrs.get("city", "")),
            ]
        ).lower()
        if any(token in text for token in lowered_tokens):
            hits += 1
    return hits / max(1, len(personas))


def _persona_region(persona: PersonaSeed) -> str:
    for key in ("district", "province", "region", "city"):
        value = str(persona.attrs.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _age_bucket(value: Any) -> str:
    try:
        age = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if age < 30:
        return "youth"
    if age < 60:
        return "working"
    return "senior"
