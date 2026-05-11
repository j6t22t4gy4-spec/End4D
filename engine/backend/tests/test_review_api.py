"""Review summary API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_review_summary_returns_summary_and_annotations():
    created = client.post(
        "/worlds",
        json={"prompt": "청년 고용 정책이 장기 신념과 지역 격차에 미치는 영향을 본다"},
    )
    assert created.status_code == 200
    world_id = created.json()["world_id"]

    ran = client.post(f"/worlds/{world_id}/run", json={"stream": False})
    assert ran.status_code == 200

    review = client.get(f"/worlds/{world_id}/review/summary")
    assert review.status_code == 200
    payload = review.json()

    assert payload["world_id"] == world_id
    assert payload["summary"]
    assert payload["summary_mode"] in {"heuristic", "llm"}
    assert isinstance(payload["timeline_annotations"], list)
    assert "metrics" in payload
    assert "grounding" in payload
    assert "citations" in payload
    assert "review_meta" in payload


def test_review_diff_returns_comparison():
    base = client.post(
        "/worlds",
        json={"prompt": "기본 정책 시나리오로 청년 고용과 지역 불평등을 본다"},
    )
    assert base.status_code == 200
    base_world_id = base.json()["world_id"]
    assert client.post(f"/worlds/{base_world_id}/run", json={"stream": False}).status_code == 200

    target = client.post(
        "/worlds",
        json={"prompt": "강한 청년 고용 보조금 정책을 주입한 시나리오를 본다"},
    )
    assert target.status_code == 200
    target_world_id = target.json()["world_id"]
    assert client.post(f"/worlds/{target_world_id}/run", json={"stream": False}).status_code == 200

    diff = client.get(f"/worlds/{target_world_id}/review/diff", params={"base_world_id": base_world_id})
    assert diff.status_code == 200
    payload = diff.json()
    assert payload["base_world_id"] == base_world_id
    assert payload["target_world_id"] == target_world_id
    assert payload["summary"]
    assert isinstance(payload["key_deltas"], list)
    assert "compared_metrics" in payload
    assert "timeline_turning_point_delta" in payload["compared_metrics"]
    assert "group_drift_deltas" in payload["compared_metrics"]
    assert "policy_impact_delta" in payload["compared_metrics"]
    assert "citations" in payload


def test_review_query_returns_answer_and_grounding():
    created = client.post(
        "/worlds",
        json={"prompt": "지역 불평등과 정책 대상 집단 변화를 함께 본다"},
    )
    assert created.status_code == 200
    world_id = created.json()["world_id"]

    ran = client.post(f"/worlds/{world_id}/run", json={"stream": False})
    assert ran.status_code == 200

    response = client.post(
        f"/worlds/{world_id}/review/query",
        json={"question": "어떤 집단의 신념 변화가 가장 컸고 왜 그런가?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["world_id"] == world_id
    assert payload["answer"]
    assert isinstance(payload["evidence"], list)
    assert "grounding" in payload
    assert "citations" in payload
    assert payload["mode"] in {"heuristic", "llm"}


def test_review_diff_query_returns_answer_and_grounding():
    base = client.post(
        "/worlds",
        json={"prompt": "기준 시나리오로 사회적 고도와 집단 분열을 본다"},
    )
    assert base.status_code == 200
    base_world_id = base.json()["world_id"]
    assert client.post(f"/worlds/{base_world_id}/run", json={"stream": False}).status_code == 200

    target = client.post(
        "/worlds",
        json={"prompt": "강한 정책 주입으로 집단 분열과 지역 격차를 비교한다"},
    )
    assert target.status_code == 200
    target_world_id = target.json()["world_id"]
    assert client.post(f"/worlds/{target_world_id}/run", json={"stream": False}).status_code == 200

    response = client.post(
        f"/worlds/{target_world_id}/review/diff-query",
        params={"base_world_id": base_world_id},
        json={"question": "어떤 집단 분열과 정책 차이가 가장 크게 갈렸나?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["base_world_id"] == base_world_id
    assert payload["target_world_id"] == target_world_id
    assert payload["answer"]
    assert isinstance(payload["evidence"], list)
    assert "grounding" in payload
    assert "citations" in payload


def test_agent_interview_returns_persona_grounded_answer():
    created = client.post(
        "/worlds",
        json={"prompt": "지역 불평등과 개인 신념 변화를 함께 보는 시나리오"},
    )
    assert created.status_code == 200
    world_id = created.json()["world_id"]
    assert client.post(f"/worlds/{world_id}/run", json={"stream": False}).status_code == 200

    snapshot = client.get(f"/worlds/{world_id}/snapshots")
    assert snapshot.status_code == 200
    times = snapshot.json()["available_t"]
    latest_t = times[-1]
    latest = client.get(f"/worlds/{world_id}/snapshots", params={"t": latest_t})
    assert latest.status_code == 200
    cell_id = latest.json()["cells"][0]["cell_id"]

    response = client.post(
        f"/worlds/{world_id}/agents/{cell_id}/query",
        json={"question": "지금 상황을 너의 입장에서 어떻게 보고 있어?", "t": latest_t},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["world_id"] == world_id
    assert payload["cell_id"] == cell_id
    assert payload["answer"]
    assert isinstance(payload["grounding"], dict)
    assert isinstance(payload["citations"], list)


def test_agent_interview_diff_returns_change_grounded_answer():
    created = client.post(
        "/worlds",
        json={"prompt": "정책 주입 전후 개별 에이전트 입장 변화를 비교한다"},
    )
    assert created.status_code == 200
    world_id = created.json()["world_id"]
    assert client.post(f"/worlds/{world_id}/run", json={"stream": False}).status_code == 200

    snapshot = client.get(f"/worlds/{world_id}/snapshots")
    assert snapshot.status_code == 200
    times = snapshot.json()["available_t"]
    assert len(times) >= 2
    latest_t = times[-1]
    latest = client.get(f"/worlds/{world_id}/snapshots", params={"t": latest_t})
    assert latest.status_code == 200
    cell_id = latest.json()["cells"][0]["cell_id"]

    response = client.post(
        f"/worlds/{world_id}/agents/{cell_id}/diff-query",
        json={
            "question": "초기와 비교해서 지금 왜 달라졌어?",
            "base_t": times[0],
            "t": latest_t,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["world_id"] == world_id
    assert payload["cell_id"] == cell_id
    assert payload["answer"]
    assert isinstance(payload["grounding"], dict)
    assert isinstance(payload["citations"], list)
    assert payload["interview_meta"]["query"]["base_t"] == times[0]
