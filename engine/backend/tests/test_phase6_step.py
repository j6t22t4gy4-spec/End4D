"""Phase 6: 스텝 루프에 Emotion·Thought·메모리 연동."""
import numpy as np

from app.core.snapshot import SnapshotStore
from app.graph.time_flow import create_time_flow_graph


def test_graph_run_preserves_vector_shapes_and_advances_t():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    out = graph.invoke(
        {
            "initial_cell_count": 3,
            "t_max": 22,
            "snapshot_store": store,
        }
    )
    assert out["current_t"] == 22
    for c in out["cells"]:
        assert c.emotion_vec.shape == (8,)
        assert c.thought_vec.shape == (256,)
        assert c.worldview_vec.shape == (384,)
        assert isinstance(c.memory, list)


def test_thought_refresh_at_interval_changes_vector():
    """Thought는 current_t=20인 스텝에서 갱신되므로 t_max>20 필요."""
    store = SnapshotStore()
    graph = create_time_flow_graph()
    graph.invoke(
        {
            "initial_cell_count": 1,
            "t_max": 21,
            "snapshot_store": store,
        }
    )
    snap0 = store.get(0.0)
    snap21 = store.get(21.0)
    assert snap0 is not None and snap21 is not None
    assert not np.allclose(snap0.cells[0].thought_vec, snap21.cells[0].thought_vec)
