"""Disk persistence and reload tests."""
import json

import numpy as np

from app.core.store import WorldStore
from app.models.cell import Cell


def test_disk_persistence_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("ORGANIC4D_PERSISTENCE_BACKEND", "disk")
    monkeypatch.setenv("ORGANIC4D_STATE_DIR", str(tmp_path))

    store = WorldStore()
    wid = store.create(
        t_max=5,
        initial_cell_count=1,
        genesis_prompt="persistent world",
        role_catalog=["citizen"],
    )
    entry = store.get(wid)
    assert entry is not None
    entry["snapshot_store"].save(
        3.0,
        [
            Cell(
                cell_id="persisted-cell",
                x=1.0,
                y=0.0,
                z=0.0,
                t=3.0,
                energy=77.0,
                gene_vec=np.zeros(32),
                emotion_vec=np.zeros(8),
                thought_vec=np.zeros(256),
                worldview_vec=np.zeros(384),
                memory=["t=3 social_observation neighbors=1 alignment=ally"],
                short_memory=[
                    {
                        "t": 3.0,
                        "kind": "social_observation",
                        "summary": "t=3 social_observation neighbors=1 alignment=ally",
                        "importance": 0.7,
                        "source": "test",
                        "payload": {},
                        "tags": ["interaction"],
                    }
                ],
                behavior_log=[
                    {
                        "schema_version": "behavior-log/v1",
                        "t": 3.0,
                        "event_type": "social_observation",
                        "source": "test",
                        "summary": "t=3 social_observation neighbors=1 alignment=ally",
                        "quality_score": 0.7,
                        "payload": {},
                    }
                ],
                relationship_state={
                    "peer-1": {
                        "peer_id": "peer-1",
                        "trust": 0.61,
                        "tension": 0.14,
                        "alignment": 0.18,
                        "dialogue_count": 3,
                        "last_t": 2.0,
                        "last_summary": "shared local concern",
                    }
                },
                role_key="citizen",
                role_label="citizen",
            )
        ],
    )
    raw = json.loads((tmp_path / f"{wid}.json").read_text(encoding="utf-8"))
    assert raw["schema_version"] == "organic4d-file-envelope/v1"
    assert raw["payload_schema_version"] == "world-entry/v3"
    assert raw["integrity"]["algorithm"] == "sha256"
    assert raw["payload"]["snapshot_index"][0]["cell_count"] == 1
    assert raw["payload"]["snapshot_archive"]["archived_count"] == 0

    reloaded = WorldStore()
    loaded_entry = reloaded.get(wid)
    assert loaded_entry is not None
    loaded_snap = loaded_entry["snapshot_store"].get(3.0)
    assert loaded_snap is not None
    assert loaded_snap.cells[0].cell_id == "persisted-cell"
    assert loaded_snap.cells[0].memory[-1].endswith("alignment=ally")
    assert loaded_snap.cells[0].short_memory[0]["kind"] == "social_observation"
    assert loaded_snap.cells[0].behavior_log[0]["schema_version"] == "behavior-log/v1"
    assert loaded_snap.cells[0].relationship_state["peer-1"]["dialogue_count"] == 3
    assert loaded_snap.cells[0].zone_id == "zone-0"
    assert loaded_snap.cells[0].z == 0.0
    assert loaded_entry["config_version"]
    assert loaded_entry["snapshot_store"].snapshot_index()[0]["digest"]
