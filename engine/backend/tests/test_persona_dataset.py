"""Persona dataset adapter."""
import json

from app.core.persona_dataset import (
    infer_country_from_prompt,
    load_persona_seeds,
    persona_source_info,
    persona_source_label,
)
from app.graph.time_flow import _create_initial_cells


def test_infer_country_from_prompt_defaults_to_korea_hint():
    assert infer_country_from_prompt("한국 청년 고용 시장을 시뮬레이션") == "KR"
    assert infer_country_from_prompt("US housing policy scenario") == "US"


def test_load_persona_seeds_from_jsonl(tmp_path, monkeypatch):
    p = tmp_path / "kr.jsonl"
    rows = [
        {
            "uuid": "a",
            "professional_persona": "서울의 제조업 기술자",
            "occupation": "기술자",
            "age": 34,
            "province": "서울특별시",
            "country": "KR",
        },
        {
            "uuid": "b",
            "persona": "부산의 자영업자",
            "occupation": "자영업자",
            "age": 51,
            "province": "부산광역시",
            "country": "KR",
        },
    ]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    monkeypatch.setenv("ORGANIC4D_PERSONA_DATASET_DIR", str(tmp_path))

    personas = load_persona_seeds("KR", count=2, seed_text="시장 정책")
    assert len(personas) == 2
    assert {p.role_label for p in personas} == {"기술자", "자영업자"}
    assert all(p.persona_text for p in personas)
    assert persona_source_label("KR").startswith("local:")
    info = persona_source_info("KR")
    assert info["configured"] is True
    assert info["country"] == "KR"


def test_hf_source_info_for_known_korea_dataset(monkeypatch):
    monkeypatch.delenv("ORGANIC4D_PERSONA_DATASET_DIR", raising=False)
    monkeypatch.setenv("ORGANIC4D_PERSONA_HF_DATASET_KR", "nvidia/Nemotron-Personas-Korea")
    info = persona_source_info("KR")
    assert info["source"] == "hf:nvidia/Nemotron-Personas-Korea"
    assert info["license"] == "CC BY 4.0"
    assert info["attribution_required"] is True


def test_initial_cells_use_persona_catalog():
    cells = _create_initial_cells(
        count=1,
        persona_catalog=[
            {
                "persona_id": "p1",
                "persona_text": "서울의 제조업 기술자",
                "role_key": "기술자",
                "role_label": "기술자",
                "country": "KR",
                "attrs": {"age": 34},
            }
        ],
    )
    assert cells[0].role_label == "기술자"
    assert cells[0].persona_id == "p1"
    assert cells[0].persona_country == "KR"
    assert cells[0].memory == ["서울의 제조업 기술자"]
