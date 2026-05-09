"""Local data-pack manifest helpers for the runtime."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import (
    get_data_cache_dir,
    get_llm_base_url,
    get_llm_chat_enabled,
    get_llm_model,
    get_llm_provider,
    get_runtime_profile,
    get_state_dir,
)

DATA_PACK_MANIFEST = "packs.json"


def _manifest_path() -> Path:
    explicit = os.getenv("ORGANIC4D_DATA_PACK_MANIFEST", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return get_data_cache_dir() / DATA_PACK_MANIFEST


def load_data_pack_manifest() -> Dict[str, Any]:
    path = _manifest_path()
    if not path.exists():
        return {"schema_version": "data-packs/v1", "packs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "data-packs/v1", "packs": []}
    if not isinstance(data, dict):
        return {"schema_version": "data-packs/v1", "packs": []}
    packs = data.get("packs")
    if not isinstance(packs, list):
        data["packs"] = []
    return data


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
                "updated_at": str(raw.get("updated_at") or ""),
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
