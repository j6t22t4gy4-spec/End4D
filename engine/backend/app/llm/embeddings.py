"""텍스트 → 고정 차원 벡터 (sentence-transformers 우선, 실패 시 결정적 스텁).

Worldview 384차원, Thought 256차원은 앞쪽 차원을 잘라 사용.
"""
from __future__ import annotations

import hashlib
import os
from typing import List

import numpy as np

_MODEL = None


def _sha256_seed(text: str) -> int:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % (2**31)


def deterministic_embed_batch(texts: List[str], dim: int) -> np.ndarray:
    """LLM/임베딩 미설치 환경용 재현 가능한 저차원 노이즈."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        seed = (_sha256_seed(text) + i * 9973) % (2**31)
        rng = np.random.RandomState(seed)
        v = rng.randn(dim).astype(np.float32) * 0.12
        n = np.linalg.norm(v) + 1e-8
        out[i] = v / n
    return out


def _project_dim(emb: np.ndarray, target_dim: int) -> np.ndarray:
    if emb.shape[-1] == target_dim:
        return emb.astype(np.float32)
    if emb.shape[-1] > target_dim:
        return emb[..., :target_dim].astype(np.float32)
    pad = np.zeros((*emb.shape[:-1], target_dim), dtype=np.float32)
    pad[..., : emb.shape[-1]] = emb.astype(np.float32)
    return pad


def embed_texts(texts: List[str], target_dim: int) -> np.ndarray:
    """(len(texts), target_dim) float32. 배치 단위."""
    if not texts:
        return np.zeros((0, target_dim), dtype=np.float32)

    if os.environ.get("ORGANIC4D_EMBED_BACKEND", "").strip().lower() == "stub":
        return deterministic_embed_batch(texts, target_dim)

    global _MODEL
    try:
        from sentence_transformers import SentenceTransformer

        if _MODEL is None:
            _MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        raw = _MODEL.encode(
            list(texts),
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if raw.ndim == 1:
            raw = raw.reshape(1, -1)
        projected = _project_dim(raw, target_dim)
        # L2 정규화 (cosine 유사도 안정화)
        norms = np.linalg.norm(projected, axis=1, keepdims=True) + 1e-8
        return (projected / norms).astype(np.float32)
    except Exception:
        return deterministic_embed_batch(texts, target_dim)
