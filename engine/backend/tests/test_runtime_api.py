"""Local runtime status API tests."""
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_runtime_local_status_lists_installed_packs(tmp_path, monkeypatch):
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    (packs_dir / "kr_pack.jsonl").write_text("", encoding="utf-8")
    manifest = {
        "schema_version": "data-packs/v1",
        "packs": [
            {
                "pack_id": "nemotron-kr-core",
                "kind": "persona",
                "country": "KR",
                "version": "2026.05",
                "relative_path": "kr_pack.jsonl",
                "license": "CC BY 4.0",
            }
        ],
    }
    manifest_path = packs_dir / "packs.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(manifest_path))
    monkeypatch.setenv("ORGANIC4D_RUNTIME_PROFILE", "local-enterprise")
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "1")
    monkeypatch.setenv("ORGANIC4D_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ORGANIC4D_LLM_MODEL", "llama3.1")
    monkeypatch.setenv("ORGANIC4D_LLM_BASE_URL", "http://127.0.0.1:11434")

    response = client.get("/runtime/local-status")
    assert response.status_code == 200
    data = response.json()
    assert data["runtime_profile"] == "local-enterprise"
    assert data["llm"]["enabled"] is True
    assert data["llm"]["provider"] == "ollama"
    assert data["llm"]["model"] == "llama3.1"
    assert data["installed_pack_count"] == 1
    assert data["available_countries"] == ["KR"]
    assert data["packs"][0]["pack_id"] == "nemotron-kr-core"
    assert data["packs"][0]["installed"] is True


def test_runtime_data_pack_sync_merges_remote_manifest(tmp_path, monkeypatch):
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()
    (packs_dir / "us_persona.jsonl").write_text("", encoding="utf-8")
    remote_manifest = {
        "schema_version": "data-packs/v1",
        "packs": [
            {
                "pack_id": "persona-us-core",
                "kind": "persona",
                "country": "US",
                "version": "2026.05",
                "relative_path": "us_persona.jsonl",
                "license": "CC BY 4.0",
                "dataset_id": "example/us-personas",
            }
        ],
    }
    remote_path = remote_dir / "packs.remote.json"
    remote_path.write_text(json.dumps(remote_manifest, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(packs_dir / "packs.json"))

    response = client.post("/runtime/data-packs/sync", json={"remote_url": str(remote_path)})
    assert response.status_code == 200
    data = response.json()
    assert data["synced"] is True
    assert data["pack_count"] >= 2

    status = client.get("/runtime/local-status").json()
    us_pack = next(pack for pack in status["packs"] if pack["pack_id"] == "persona-us-core")
    assert us_pack["installed"] is True
    assert us_pack["dataset_id"] == "example/us-personas"
