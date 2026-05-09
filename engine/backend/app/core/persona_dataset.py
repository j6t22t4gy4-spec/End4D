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

    pack_path = resolve_country_pack_path(code, kind="persona")
    if pack_path is not None and pack_path.exists():
        return pack_path

    base_dir = os.getenv("ORGANIC4D_PERSONA_DATASET_DIR", "").strip()
    if not base_dir or not code:
        return None
    for ext in ("jsonl", "json", "csv"):
        p = Path(base_dir) / f"{code.lower()}.{ext}"
        if p.exists():
            return p
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
                "dataset_id": str(pack.get("pack_id") or ""),
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
            "dataset_id": pack_id,
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
