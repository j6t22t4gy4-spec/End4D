"""Agent group observability API tests."""
import numpy as np
from fastapi.testclient import TestClient

from app.core.store import world_store
from app.main import app
from app.models.cell import Cell

client = TestClient(app)


def test_agent_summary_groups_latest_snapshot_by_role():
    wid = world_store.create(
        t_max=11,
        initial_cell_count=4,
        role_catalog=["citizen", "regulator"],
        persona_country="KR",
        persona_source="local:test",
        persona_catalog=[
            {
                "persona_id": "p1",
                "persona_text": "서울의 정책 관심 시민",
                "role_key": "citizen",
                "role_label": "citizen",
                "country": "KR",
            },
            {
                "persona_id": "p2",
                "persona_text": "부산의 시장 규제 담당자",
                "role_key": "regulator",
                "role_label": "regulator",
                "country": "KR",
            },
        ],
    )
    store = world_store.get_snapshot_store(wid)
    assert store is not None
    cells = [
        Cell(
            cell_id=f"cell-{i}",
            x=float(i),
            y=0.0,
            z=0.0,
            t=11.0,
            energy=50.0 + i,
            gene_vec=np.zeros(32),
            emotion_vec=np.ones(8) * 0.1,
            thought_vec=np.zeros(256),
            worldview_vec=np.zeros(384),
            role_key="citizen" if i < 2 else "regulator",
            role_label="citizen" if i < 2 else "regulator",
            persona_country="KR",
            memory=["seed", "t=10 social_observation neighbors=1"],
        )
        for i in range(4)
    ]
    store.save(11.0, cells)

    response = client.get(f"/worlds/{wid}/agents/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["world_id"] == wid
    assert data["t"] == 11.0
    assert data["group_count"] >= 2
    assert data["cell_count"] >= 4
    assert any(group["role_key"] == "citizen" for group in data["groups"])
    assert all("dominant_emotion" in group for group in data["groups"])
    assert all("avg_interaction_quality" in group for group in data["groups"])

    stance_response = client.get(f"/worlds/{wid}/agents/stance-summary")
    assert stance_response.status_code == 200
    stance_data = stance_response.json()
    assert stance_data["world_id"] == wid
    assert stance_data["groups"]
    assert all("stance" in group for group in stance_data["groups"])
