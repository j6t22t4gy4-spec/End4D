"""Versioned file envelope and integrity helpers for local persistence."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict

ENVELOPE_SCHEMA_VERSION = "organic4d-file-envelope/v1"
WORLD_ENTRY_SCHEMA_VERSION = "world-entry/v3"


def canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_digest(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def wrap_payload(payload: Dict[str, Any], *, payload_schema_version: str = WORLD_ENTRY_SCHEMA_VERSION) -> Dict[str, Any]:
    digest = payload_digest(payload)
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "payload_schema_version": payload_schema_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "integrity": {
            "algorithm": "sha256",
            "digest": digest,
        },
        "payload": payload,
    }


def unwrap_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    if raw.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        return raw
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Invalid persistence envelope: missing payload")
    integrity = raw.get("integrity") or {}
    expected = str(integrity.get("digest") or "")
    actual = payload_digest(payload)
    if expected and expected != actual:
        raise ValueError("Persistence integrity check failed")
    return payload
