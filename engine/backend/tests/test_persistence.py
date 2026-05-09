"""Disk persistence and reload tests."""
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
                role_key="citizen",
                role_label="citizen",
            )
        ],
    )

    reloaded = WorldStore()
    loaded_entry = reloaded.get(wid)
    assert loaded_entry is not None
    loaded_snap = loaded_entry["snapshot_store"].get(3.0)
    assert loaded_snap is not None
    assert loaded_snap.cells[0].cell_id == "persisted-cell"
    assert loaded_snap.cells[0].memory[-1].endswith("alignment=ally")
