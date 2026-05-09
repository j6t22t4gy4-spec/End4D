"""Local data-pack manifest helpers for the runtime."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import (
    get_data_cache_dir,
    get_data_pack_remote_manifest_url,
    get_llm_base_url,
    get_llm_chat_enabled,
    get_llm_model,
    get_llm_provider,
    get_runtime_profile,
    get_state_dir,
)

DATA_PACK_MANIFEST = "packs.json"
DATA_PACK_SCHEMA_VERSION = "data-packs/v1"

KNOWN_DATA_PACKS = [
    {
        "pack_id": "nemotron-kr-core",
        "kind": "persona",
        "country": "KR",
        "version": "hf:nvidia/Nemotron-Personas-Korea",
        "relative_path": "nemotron-personas-korea/personas.jsonl",
        "license": "CC BY 4.0",
        "source_url": "https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea",
        "dataset_id": "nvidia/Nemotron-Personas-Korea",
        "updated_at": "",
        "description": "Canonical Korea persona pack entry; install/sync fills the local cache path.",
    }
]


def _manifest_path() -> Path:
    explicit = os.getenv("ORGANIC4D_DATA_PACK_MANIFEST", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return get_data_cache_dir() / DATA_PACK_MANIFEST


def load_data_pack_manifest() -> Dict[str, Any]:
    path = _manifest_path()
    if not path.exists():
        return {"schema_version": DATA_PACK_SCHEMA_VERSION, "packs": list(KNOWN_DATA_PACKS)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": DATA_PACK_SCHEMA_VERSION, "packs": list(KNOWN_DATA_PACKS)}
    if not isinstance(data, dict):
        return {"schema_version": DATA_PACK_SCHEMA_VERSION, "packs": list(KNOWN_DATA_PACKS)}
    packs = data.get("packs")
    if not isinstance(packs, list):
        data["packs"] = []
    data["schema_version"] = str(data.get("schema_version") or DATA_PACK_SCHEMA_VERSION)
    data["packs"] = _merge_packs(list(KNOWN_DATA_PACKS), [p for p in data["packs"] if isinstance(p, dict)])
    return data


def sync_data_pack_manifest(remote_url: Optional[str] = None) -> Dict[str, Any]:
    """Merge a cloud-delivered manifest into the local cache manifest.

    The sync step updates metadata and paths. Actual large dataset transfer can
    be handled by an external installer, keeping the engine usable offline.
    """
    source = (remote_url or get_data_pack_remote_manifest_url()).strip()
    local = load_data_pack_manifest()
    if not source:
        return {
            "schema_version": DATA_PACK_SCHEMA_VERSION,
            "source": "",
            "synced": False,
            "pack_count": len(local.get("packs") or []),
            "installed_pack_count": len([p for p in list_installed_data_packs() if p["installed"]]),
        }

    remote = _fetch_manifest(source)
    merged = {
        "schema_version": DATA_PACK_SCHEMA_VERSION,
        "source": source,
        "packs": _merge_packs(list(local.get("packs") or []), list(remote.get("packs") or [])),
    }
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    installed = [p for p in list_installed_data_packs() if p["installed"]]
    return {
        "schema_version": DATA_PACK_SCHEMA_VERSION,
        "source": source,
        "synced": True,
        "pack_count": len(merged["packs"]),
        "installed_pack_count": len(installed),
    }


def _fetch_manifest(source: str) -> Dict[str, Any]:
    if source.startswith("http://") or source.startswith("https://") or source.startswith("file://"):
        with urllib.request.urlopen(source, timeout=20) as response:
            raw = response.read().decode("utf-8")
    else:
        raw = Path(source).expanduser().read_text(encoding="utf-8")
    data = json.loads(raw or "{}")
    if not isinstance(data, dict) or not isinstance(data.get("packs"), list):
        raise ValueError("Invalid data-pack manifest")
    return data


def _merge_packs(base: List[Dict[str, Any]], updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: dict[tuple[str, str, str], Dict[str, Any]] = {}
    for pack in base + updates:
        if not isinstance(pack, dict):
            continue
        key = (
            str(pack.get("pack_id") or ""),
            str(pack.get("kind") or ""),
            str(pack.get("country") or ""),
        )
        if not key[0]:
            continue
        merged = dict(by_key.get(key) or {})
        merged.update(pack)
        by_key[key] = merged
    return list(by_key.values())


def list_installed_data_packs() -> List[Dict[str, Any]]:
    manifest = load_data_pack_manifest()
    base_dir = _manifest_path().parent
    out: List[Dict[str, Any]] = []
    for raw in manifest.get("packs") or []:
        if not isinstance(raw, dict):
            continue
        rel = str(raw.get("relative_path") or "").strip()
        path = (base_dir / rel).resolve() if rel else None
        out.append(
            {
                "pack_id": str(raw.get("pack_id") or ""),
                "kind": str(raw.get("kind") or ""),
                "country": str(raw.get("country") or ""),
                "version": str(raw.get("version") or ""),
                "relative_path": rel,
                "path": str(path) if path is not None else "",
                "installed": bool(path and path.exists()),
                "license": str(raw.get("license") or ""),
                "source_url": str(raw.get("source_url") or ""),
                "dataset_id": str(raw.get("dataset_id") or ""),
                "updated_at": str(raw.get("updated_at") or ""),
                "description": str(raw.get("description") or ""),
            }
        )
    return out


def resolve_country_pack_path(country: str, *, kind: str = "persona") -> Optional[Path]:
    code = country.strip().upper()
    for pack in list_installed_data_packs():
        if pack["kind"] != kind or str(pack["country"]).upper() != code:
            continue
        if pack["installed"] and pack["path"]:
            return Path(pack["path"])
    return None


def resolve_country_pack_info(country: str, *, kind: str = "persona") -> Optional[Dict[str, Any]]:
    code = country.strip().upper()
    for pack in list_installed_data_packs():
        if pack["kind"] != kind or str(pack["country"]).upper() != code:
            continue
        return dict(pack)
    return None


def local_runtime_status() -> Dict[str, Any]:
    packs = list_installed_data_packs()
    installed = [pack for pack in packs if pack["installed"]]
    countries = sorted({str(pack["country"]) for pack in installed if pack["country"]})
    return {
        "runtime_profile": get_runtime_profile(),
        "state_dir": str(get_state_dir()),
        "data_cache_dir": str(get_data_cache_dir()),
        "manifest_path": str(_manifest_path()),
        "remote_manifest_url": get_data_pack_remote_manifest_url(),
        "llm": {
            "enabled": get_llm_chat_enabled(),
            "provider": get_llm_provider(),
            "model": get_llm_model(),
            "base_url": str(get_llm_base_url() or ""),
        },
        "installed_pack_count": len(installed),
        "available_countries": countries,
        "packs": packs,
    }
