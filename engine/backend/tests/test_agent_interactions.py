"""Agent interaction memory and internal flywheel tests."""
import numpy as np

from app.core.agent_interactions import apply_agent_interactions
from app.models.cell import Cell


def _cell(cell_id: str, x: float, role: str = "agent") -> Cell:
    return Cell(
        cell_id=cell_id,
        x=x,
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
    )


def test_agent_interactions_write_nearby_social_memory_only_on_interval():
    cells = [_cell("a", 0.0, "citizen"), _cell("b", 1.0, "regulator"), _cell("c", 50.0)]

    skipped = apply_agent_interactions(cells, current_t=9)
    assert skipped[0].memory == []

    updated = apply_agent_interactions(cells, current_t=10, radius=4.0)
    assert any("social_observation" in line for line in updated[0].memory)
    assert any("regulator" in line for line in updated[0].memory)
    assert any("alignment=" in line for line in updated[0].memory)
    assert updated[2].memory == []
