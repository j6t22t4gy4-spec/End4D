"""pytest: 임베딩은 기본 스텁으로 고정해 속도·의존성 분리."""
import os

os.environ.setdefault("ORGANIC4D_EMBED_BACKEND", "stub")
