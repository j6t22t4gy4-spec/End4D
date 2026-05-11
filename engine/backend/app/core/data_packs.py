"""Local data-pack manifest helpers for the runtime."""
from __future__ import annotations

import json
import os
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import (
    get_data_cache_dir,
    get_data_pack_remote_manifest_url,
    get_llm_api_key,
    get_llm_base_url,
    get_llm_chat_enabled,
    get_llm_model,
    get_llm_provider,
    get_runtime_profile,
    get_state_dir,
)
from app.llm.facade import llm_facade

DATA_PACK_MANIFEST = "packs.json"
DATA_PACK_SCHEMA_VERSION = "data-packs/v2"
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
    data["schema_version"] = DATA_PACK_SCHEMA_VERSION
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


def install_data_pack(
    *,
    pack_id: str,
    source_path: str,
    version: str = "",
    dataset_id: str = "",
    source_url: str = "",
) -> Dict[str, Any]:
    manifest = load_data_pack_manifest()
    pack = _find_pack(manifest, pack_id)
    if pack is None:
        raise ValueError(f"Unknown pack_id: {pack_id}")

    src = Path(source_path).expanduser()
    if not src.exists() or not src.is_file():
        raise ValueError("Install source_path not found")

    base_dir = _manifest_path().parent
    rel = str(pack.get("relative_path") or "").strip()
    if not rel:
        suffix = src.suffix or ".jsonl"
        rel = f"{pack_id}/{src.stem}{suffix}"
        pack["relative_path"] = rel
    dest = (base_dir / rel).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    pack["installed"] = True
    pack["updated_at"] = _now_iso()
    pack["installed_at"] = _now_iso()
    pack["version"] = version or str(pack.get("version") or "")
    pack["dataset_id"] = dataset_id or str(pack.get("dataset_id") or "")
    pack["source_url"] = source_url or str(pack.get("source_url") or "")
    _append_pack_history(
        pack,
        action="install",
        detail={
            "version": str(pack.get("version") or ""),
            "relative_path": str(pack.get("relative_path") or ""),
            "dataset_id": str(pack.get("dataset_id") or ""),
        },
    )
    _write_manifest(manifest)
    validation = validate_data_pack(pack_id)
    validation["installed"] = True
    return validation


def validate_data_pack(pack_id: str) -> Dict[str, Any]:
    manifest = load_data_pack_manifest()
    pack = _find_pack(manifest, pack_id)
    if pack is None:
        raise ValueError(f"Unknown pack_id: {pack_id}")

    rel = str(pack.get("relative_path") or "").strip()
    path = ((_manifest_path().parent / rel).resolve() if rel else None)
    exists = bool(path and path.exists() and path.is_file())
    row_count = 0
    sample_error = ""
    if exists:
        try:
            row_count = _sample_row_count(path)
        except Exception as exc:
            sample_error = type(exc).__name__
    pack["validated_at"] = _now_iso()
    pack["validation"] = {
        "exists": exists,
        "row_count_estimate": row_count,
        "sample_error": sample_error,
    }
    _append_pack_history(
        pack,
        action="validate",
        detail={"exists": exists, "row_count_estimate": row_count, "sample_error": sample_error},
    )
    _write_manifest(manifest)
    return {
        "pack_id": pack_id,
        "exists": exists,
        "row_count_estimate": row_count,
        "sample_error": sample_error,
        "validated_at": str(pack.get("validated_at") or ""),
        "version": str(pack.get("version") or ""),
    }


def verify_data_pack(pack_id: str) -> Dict[str, Any]:
    manifest = load_data_pack_manifest()
    pack = _find_pack(manifest, pack_id)
    if pack is None:
        raise ValueError(f"Unknown pack_id: {pack_id}")
    rel = str(pack.get("relative_path") or "").strip()
    path = ((_manifest_path().parent / rel).resolve() if rel else None)
    exists = bool(path and path.exists() and path.is_file())
    report = {
        "pack_id": pack_id,
        "exists": exists,
        "dataset_id": str(pack.get("dataset_id") or ""),
        "version": str(pack.get("version") or ""),
        "verified_at": _now_iso(),
        "schema_health": "missing",
        "field_coverage": {},
        "sample_roles": [],
        "sample_regions": [],
        "country_consistency": 0.0,
        "ready_for_genesis": False,
    }
    if not exists or path is None:
        pack["verification"] = report
        _write_manifest(manifest)
        return report

    rows = []
    for idx, row in enumerate(_iter_json_like_rows(path)):
        rows.append(row)
        if idx >= 299:
            break
    if not rows:
        report["schema_health"] = "empty"
    else:
        required = {
            "persona_text": PERSONA_TEXT_FIELDS,
            "role": ROLE_FIELDS,
            "country": ("country",),
        }
        coverage = {}
        for label, fields in required.items():
            hits = 0
            for row in rows:
                if any(str(row.get(field) or "").strip() for field in fields):
                    hits += 1
            coverage[label] = round(hits / max(1, len(rows)), 3)
        countries = [str(row.get("country") or "").strip().upper() for row in rows if str(row.get("country") or "").strip()]
        pack_country = str(pack.get("country") or "").strip().upper()
        if countries:
            same = sum(1 for country in countries if country == pack_country)
            report["country_consistency"] = round(same / len(countries), 3)
        roles = [
            str(next((row.get(field) for field in ROLE_FIELDS if str(row.get(field) or "").strip()), "")).strip()
            for row in rows
        ]
        regions = [
            str(row.get("province") or row.get("district") or "").strip()
            for row in rows
            if str(row.get("province") or row.get("district") or "").strip()
        ]
        report["schema_health"] = "healthy" if min(coverage.values()) >= 0.6 else "partial"
        report["field_coverage"] = coverage
        report["sample_roles"] = _top_terms(roles, limit=5)
        report["sample_regions"] = _top_terms(regions, limit=5)
        report["ready_for_genesis"] = (
            report["schema_health"] == "healthy"
            and report["country_consistency"] >= 0.5
            and coverage.get("persona_text", 0.0) >= 0.6
        )
    pack["verification"] = report
    _append_pack_history(
        pack,
        action="verify",
        detail={
            "schema_health": str(report.get("schema_health") or ""),
            "ready_for_genesis": bool(report.get("ready_for_genesis")),
            "country_consistency": float(report.get("country_consistency") or 0.0),
        },
    )
    _write_manifest(manifest)
    return report


def pin_data_pack(pack_id: str, *, pinned_version: str) -> Dict[str, Any]:
    manifest = load_data_pack_manifest()
    pack = _find_pack(manifest, pack_id)
    if pack is None:
        raise ValueError(f"Unknown pack_id: {pack_id}")
    pack["pinned"] = True
    pack["pinned_version"] = pinned_version.strip()
    pack["pinned_at"] = _now_iso()
    _append_pack_history(
        pack,
        action="pin",
        detail={"pinned_version": str(pack.get("pinned_version") or "")},
    )
    _write_manifest(manifest)
    return {
        "pack_id": pack_id,
        "pinned": True,
        "pinned_version": str(pack.get("pinned_version") or ""),
        "pinned_at": str(pack.get("pinned_at") or ""),
    }


def rollback_data_pack(pack_id: str, *, history_index: int) -> Dict[str, Any]:
    manifest = load_data_pack_manifest()
    pack = _find_pack(manifest, pack_id)
    if pack is None:
        raise ValueError(f"Unknown pack_id: {pack_id}")
    history = list(pack.get("history") or [])
    if history_index < 0 or history_index >= len(history):
        raise ValueError("Invalid history_index")
    snapshot = dict((history[history_index] or {}).get("snapshot") or {})
    if not snapshot:
        raise ValueError("No snapshot stored for this history entry")
    for key in (
        "version",
        "relative_path",
        "dataset_id",
        "source_url",
        "pinned",
        "pinned_version",
        "validation",
        "verification",
    ):
        if key in snapshot:
            pack[key] = snapshot[key]
    pack["updated_at"] = _now_iso()
    _append_pack_history(
        pack,
        action="rollback",
        detail={"history_index": history_index, "restored_version": str(pack.get("version") or "")},
    )
    _write_manifest(manifest)
    return {
        "pack_id": pack_id,
        "rolled_back": True,
        "version": str(pack.get("version") or ""),
        "history_index": history_index,
        "updated_at": str(pack.get("updated_at") or ""),
    }


def diff_data_pack_history(pack_id: str, *, history_index: int) -> Dict[str, Any]:
    manifest = load_data_pack_manifest()
    pack = _find_pack(manifest, pack_id)
    if pack is None:
        raise ValueError(f"Unknown pack_id: {pack_id}")
    history = list(pack.get("history") or [])
    if history_index < 0 or history_index >= len(history):
        raise ValueError("Invalid history_index")
    history_item = dict(history[history_index] or {})
    snapshot = dict(history_item.get("snapshot") or {})
    if not snapshot:
        raise ValueError("No snapshot stored for this history entry")
    current_verification = dict(pack.get("verification") or {})
    snapshot_verification = dict(snapshot.get("verification") or {})
    fields = [
        "version",
        "dataset_id",
        "relative_path",
        "source_url",
        "pinned",
        "pinned_version",
    ]
    changes = []
    for field in fields:
        current = pack.get(field)
        previous = snapshot.get(field)
        if current != previous:
            changes.append(
                {
                    "field": field,
                    "current": current,
                    "rollback": previous,
                }
            )
    verification_changes = []
    for field in ("schema_health", "ready_for_genesis", "country_consistency"):
        current = current_verification.get(field)
        previous = snapshot_verification.get(field)
        if current != previous:
            verification_changes.append(
                {
                    "field": field,
                    "current": current,
                    "rollback": previous,
                }
            )
    return {
        "pack_id": pack_id,
        "history_index": history_index,
        "selected_action": str(history_item.get("action") or ""),
        "selected_at": str(history_item.get("at") or ""),
        "changes": changes,
        "verification_changes": verification_changes,
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
        merged.setdefault("installed", False)
        merged.setdefault("pinned", False)
        merged.setdefault("pinned_version", "")
        merged.setdefault("installed_at", "")
        merged.setdefault("validated_at", "")
        merged.setdefault("validation", {})
        merged.setdefault("verification", {})
        merged.setdefault("history", [])
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
                "installed_at": str(raw.get("installed_at") or ""),
                "pinned": bool(raw.get("pinned", False)),
                "pinned_version": str(raw.get("pinned_version") or ""),
                "validated_at": str(raw.get("validated_at") or ""),
                "validation": dict(raw.get("validation") or {}),
                "verification": dict(raw.get("verification") or {}),
                "history": [dict(item) for item in list(raw.get("history") or [])[-20:]],
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
            "has_api_key": bool(get_llm_api_key()),
            "configured_via": "runtime-ui" if get_llm_chat_enabled() else "default",
        },
        "llm_runtime": llm_facade.snapshot_stats(),
        "installed_pack_count": len(installed),
        "available_countries": countries,
        "packs": packs,
    }


def _write_manifest(manifest: Dict[str, Any]) -> None:
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _find_pack(manifest: Dict[str, Any], pack_id: str) -> Optional[Dict[str, Any]]:
    for pack in manifest.get("packs") or []:
        if str(pack.get("pack_id") or "") == pack_id:
            return pack
    return None


def _append_pack_history(pack: Dict[str, Any], *, action: str, detail: Dict[str, Any]) -> None:
    history = list(pack.get("history") or [])
    history.append(
        {
            "at": _now_iso(),
            "action": action,
            "detail": dict(detail),
            "snapshot": {
                "version": str(pack.get("version") or ""),
                "relative_path": str(pack.get("relative_path") or ""),
                "dataset_id": str(pack.get("dataset_id") or ""),
                "source_url": str(pack.get("source_url") or ""),
                "pinned": bool(pack.get("pinned", False)),
                "pinned_version": str(pack.get("pinned_version") or ""),
                "validation": dict(pack.get("validation") or {}),
                "verification": dict(pack.get("verification") or {}),
            },
        }
    )
    pack["history"] = history[-20:]


def _sample_row_count(path: Path, limit: int = 5000) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
                if count >= limit:
                    break
    return count


def _iter_json_like_rows(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(row, dict):
                        yield row
        return
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    yield row
        return
    with path.open("r", encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        for line in handle:
            cols = line.rstrip("\n").split(",")
            if cols and header:
                yield {header[idx]: cols[idx] if idx < len(cols) else "" for idx in range(len(header))}


def _top_terms(values: list[str], *, limit: int) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value).strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [item[0] for item in ranked[:limit]]


def _now_iso() -> str:
    return datetime.utcnow().isoformat()
