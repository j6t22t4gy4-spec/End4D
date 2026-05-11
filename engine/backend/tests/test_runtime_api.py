"""Local runtime status API tests."""
import json

from fastapi.testclient import TestClient
import numpy as np

from app.llm.facade import llm_facade
from app.main import app
from app.models.cell import Cell

client = TestClient(app)


def _cell(role: str = "citizen") -> Cell:
    return Cell(
        cell_id=f"{role}-1",
        x=0.0,
        y=0.0,
        z=0.0,
        t=0.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key=role,
        role_label=role,
        persona_text=f"{role} persona",
    )


def test_runtime_local_status_lists_installed_packs(tmp_path, monkeypatch):
    llm_facade.reset_stats()
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
    assert "task_budgets" in data["llm_runtime"]
    assert "task_priorities" in data["llm_runtime"]
    assert "health" in data["llm_runtime"]
    assert data["installed_pack_count"] == 1
    assert data["available_countries"] == ["KR"]
    assert data["packs"][0]["pack_id"] == "nemotron-kr-core"
    assert data["packs"][0]["installed"] is True
    assert data["packs"][0]["pinned"] is False


def test_runtime_data_pack_sync_merges_remote_manifest(tmp_path, monkeypatch):
    llm_facade.reset_stats()
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


def test_runtime_data_pack_install_validate_and_pin(tmp_path, monkeypatch):
    llm_facade.reset_stats()
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    src = source_dir / "kr_persona.jsonl"
    src.write_text(
        json.dumps({"uuid": "p1", "professional_persona": "서울의 기술자", "occupation": "기술자"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "data-packs/v2",
        "packs": [
            {
                "pack_id": "nemotron-kr-core",
                "kind": "persona",
                "country": "KR",
                "version": "draft",
                "relative_path": "kr/pack.jsonl",
                "license": "CC BY 4.0",
                "dataset_id": "nvidia/Nemotron-Personas-Korea",
            }
        ],
    }
    manifest_path = packs_dir / "packs.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(manifest_path))

    install = client.post(
        "/runtime/data-packs/install",
        json={
            "pack_id": "nemotron-kr-core",
            "source_path": str(src),
            "version": "2026.05",
            "dataset_id": "nvidia/Nemotron-Personas-Korea",
        },
    )
    assert install.status_code == 200
    install_data = install.json()
    assert install_data["installed"] is True
    assert install_data["exists"] is True
    assert install_data["row_count_estimate"] >= 1

    pin = client.post(
        "/runtime/data-packs/pin",
        json={"pack_id": "nemotron-kr-core", "pinned_version": "2026.05"},
    )
    assert pin.status_code == 200
    assert pin.json()["pinned"] is True

    status = client.get("/runtime/local-status")
    assert status.status_code == 200
    pack = next(item for item in status.json()["packs"] if item["pack_id"] == "nemotron-kr-core")
    assert pack["pinned"] is True
    assert pack["pinned_version"] == "2026.05"
    assert pack["validation"]["row_count_estimate"] >= 1


def test_runtime_data_pack_verify_reports_schema_health(tmp_path, monkeypatch):
    llm_facade.reset_stats()
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    src = source_dir / "kr_persona.jsonl"
    src.write_text(
        json.dumps(
            {
                "uuid": "p1",
                "country": "KR",
                "professional_persona": "부산의 항만 물류 관리자",
                "occupation": "물류 관리자",
                "province": "Busan",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "data-packs/v2",
        "packs": [
            {
                "pack_id": "nemotron-kr-core",
                "kind": "persona",
                "country": "KR",
                "version": "draft",
                "relative_path": "kr/pack.jsonl",
                "license": "CC BY 4.0",
                "dataset_id": "nvidia/Nemotron-Personas-Korea",
            }
        ],
    }
    manifest_path = packs_dir / "packs.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(manifest_path))

    install = client.post(
        "/runtime/data-packs/install",
        json={
            "pack_id": "nemotron-kr-core",
            "source_path": str(src),
            "version": "2026.05",
            "dataset_id": "nvidia/Nemotron-Personas-Korea",
        },
    )
    assert install.status_code == 200

    verify = client.post("/runtime/data-packs/verify", json={"pack_id": "nemotron-kr-core"})
    assert verify.status_code == 200
    payload = verify.json()
    assert payload["pack_id"] == "nemotron-kr-core"
    assert payload["exists"] is True
    assert payload["schema_health"] in {"healthy", "partial"}
    assert "persona_text" in payload["field_coverage"]
    assert payload["ready_for_genesis"] is True


def test_runtime_data_pack_rollback_uses_history(tmp_path, monkeypatch):
    llm_facade.reset_stats()
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    src = source_dir / "kr_persona.jsonl"
    src.write_text(
        json.dumps(
            {
                "uuid": "p1",
                "country": "KR",
                "professional_persona": "서울의 행정 담당자",
                "occupation": "행정 담당자",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "data-packs/v2",
        "packs": [
            {
                "pack_id": "nemotron-kr-core",
                "kind": "persona",
                "country": "KR",
                "version": "draft",
                "relative_path": "kr/pack.jsonl",
                "license": "CC BY 4.0",
                "dataset_id": "nvidia/Nemotron-Personas-Korea",
            }
        ],
    }
    manifest_path = packs_dir / "packs.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(manifest_path))

    assert client.post(
        "/runtime/data-packs/install",
        json={
            "pack_id": "nemotron-kr-core",
            "source_path": str(src),
            "version": "2026.05",
            "dataset_id": "nvidia/Nemotron-Personas-Korea",
        },
    ).status_code == 200
    assert client.post(
        "/runtime/data-packs/pin",
        json={"pack_id": "nemotron-kr-core", "pinned_version": "2026.06"},
    ).status_code == 200

    status = client.get("/runtime/local-status")
    assert status.status_code == 200
    pack = next(item for item in status.json()["packs"] if item["pack_id"] == "nemotron-kr-core")
    history = pack["history"]
    assert history

    rollback = client.post(
        "/runtime/data-packs/rollback",
        json={"pack_id": "nemotron-kr-core", "history_index": 0},
    )
    assert rollback.status_code == 200
    rollback_payload = rollback.json()
    assert rollback_payload["rolled_back"] is True

    status_after = client.get("/runtime/local-status")
    assert status_after.status_code == 200
    pack_after = next(item for item in status_after.json()["packs"] if item["pack_id"] == "nemotron-kr-core")
    assert len(pack_after["history"]) >= len(history)


def test_runtime_local_status_includes_llm_runtime_stats(monkeypatch):
    llm_facade.reset_stats()

    def fake_batch(prompts, *, task):
        prompt_list = list(prompts)
        return {
            "texts": ["ok" for _ in prompt_list],
            "meta": {
                "task": task,
                "provider": "stub",
                "model": "stub",
                "prompt_count_in": len(prompt_list),
                "prompt_count_sent": len(prompt_list),
                "used_fallback": False,
                "fallback_reason": "",
            },
        }

    monkeypatch.setattr("app.llm.facade.generate_reasoning_batch", fake_batch)
    llm_facade.think([_cell("citizen")])
    llm_facade.decide_actions([_cell("regulator")])

    response = client.get("/runtime/local-status")
    assert response.status_code == 200
    data = response.json()
    assert data["llm_runtime"]["task_totals"]["thought"]["calls"] == 1
    assert data["llm_runtime"]["task_totals"]["action"]["calls"] == 1
    assert data["llm_runtime"]["recent_runs"][-1]["task"] == "action"
    assert data["llm_runtime"]["health"]["recent_call_count"] >= 2


def test_runtime_llm_config_can_be_saved(tmp_path, monkeypatch):
    llm_facade.reset_stats()
    state_dir = tmp_path / "state" / "worlds"
    state_dir.mkdir(parents=True)
    monkeypatch.setenv("ORGANIC4D_STATE_DIR", str(state_dir))

    response = client.post(
        "/runtime/llm-config",
        json={
            "enabled": True,
            "provider": "openai-compatible",
            "model": "local-model",
            "base_url": "http://127.0.0.1:8001/v1",
            "api_key": "test-key",
            "temperature": 0.3,
            "timeout_s": 12,
            "runtime_profile": "llm-first",
            "strict_mode": "llm-preferred",
            "cycle_prompt_budget": 420,
            "agent_sample_size": 512,
            "dialogue_max_pairs": 88,
            "group_deliberation_max_groups": 20,
            "task_budgets": {"thought": 144, "action": 120, "dialogue": 96},
            "task_priorities": {"thought": 0, "action": 1, "dialogue": 1},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["provider"] == "openai-compatible"
    assert payload["model"] == "local-model"
    assert payload["has_api_key"] is True
    assert payload["runtime_profile"] == "llm-first"
    assert payload["strict_mode"] == "llm-preferred"
    assert payload["cycle_prompt_budget"] == 420
    assert payload["agent_sample_size"] == 512
    assert payload["dialogue_max_pairs"] == 88
    assert payload["group_deliberation_max_groups"] == 20
    assert payload["task_budgets"]["thought"] == 144
    assert payload["task_priorities"]["thought"] == 0

    status = client.get("/runtime/local-status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["llm"]["enabled"] is True
    assert status_payload["llm"]["provider"] == "openai-compatible"
    assert status_payload["llm"]["has_api_key"] is True
    assert status_payload["llm"]["runtime_profile"] == "llm-first"
    assert status_payload["llm"]["strict_mode"] == "llm-preferred"
    assert status_payload["llm_runtime"]["cycle_prompt_budget"] == 420
    assert status_payload["llm_runtime"]["agent_sample_size"] == 512
    assert status_payload["llm_runtime"]["dialogue_max_pairs"] == 88
    assert status_payload["llm_runtime"]["group_deliberation_max_groups"] == 20
    assert status_payload["llm_runtime"]["task_budgets"]["thought"] == 144
    assert status_payload["llm_runtime"]["task_priorities"]["dialogue"] == 1


def test_runtime_llm_test_endpoint_reports_runtime_result(monkeypatch):
    llm_facade.reset_stats()

    def fake_batch(prompts, *, task):
        return {
            "texts": ["runtime cognition connected"],
            "meta": {
                "task": task,
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "prompt_count_in": 1,
                "prompt_count_sent": 1,
                "used_fallback": False,
                "fallback_reason": "",
            },
        }

    monkeypatch.setattr("app.api.runtime.generate_reasoning_batch", fake_batch)
    response = client.post("/runtime/llm-config/test")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "openai"
    assert payload["preview"] == "runtime cognition connected"


def test_runtime_data_pack_diff_preview_returns_changed_fields(tmp_path, monkeypatch):
    llm_facade.reset_stats()
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    src = source_dir / "kr_persona.jsonl"
    src.write_text(
        json.dumps(
            {
                "uuid": "p1",
                "country": "KR",
                "professional_persona": "서울의 연구 관리자",
                "occupation": "연구 관리자",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "data-packs/v2",
        "packs": [
            {
                "pack_id": "nemotron-kr-core",
                "kind": "persona",
                "country": "KR",
                "version": "draft",
                "relative_path": "kr/pack.jsonl",
                "license": "CC BY 4.0",
                "dataset_id": "nvidia/Nemotron-Personas-Korea",
            }
        ],
    }
    manifest_path = packs_dir / "packs.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(manifest_path))

    assert client.post(
        "/runtime/data-packs/install",
        json={
            "pack_id": "nemotron-kr-core",
            "source_path": str(src),
            "version": "2026.05",
            "dataset_id": "nvidia/Nemotron-Personas-Korea",
        },
    ).status_code == 200
    assert client.post(
        "/runtime/data-packs/pin",
        json={"pack_id": "nemotron-kr-core", "pinned_version": "2026.06"},
    ).status_code == 200

    status = client.get("/runtime/local-status")
    assert status.status_code == 200
    pack = next(item for item in status.json()["packs"] if item["pack_id"] == "nemotron-kr-core")
    history = pack["history"]
    assert history

    response = client.post(
        "/runtime/data-packs/diff",
        json={"pack_id": "nemotron-kr-core", "history_index": 0},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["pack_id"] == "nemotron-kr-core"
    assert isinstance(payload["changes"], list)
