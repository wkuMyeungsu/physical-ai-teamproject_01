"""텍스트 → 벡터 변환.

기본은 sentence-transformers 모델(사전학습 모델을 가져다 쓰기만 함, 학습 X).
EMBED_BACKEND=hash 로 두면 모델 없이 동작하는 가벼운 해시 임베딩을 쓴다
(테스트·오프라인 확인용, 검색 품질은 낮음).
"""
from __future__ import annotations

import hashlib
import os
import re

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    name: str
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:  # (n, dim), L2 정규화된 float32
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self._model = SentenceTransformer(model_name, device="cpu")
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = self._model.encode(
            texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32)


class HashEmbedder(Embedder):
    """단어 해시 기반 bag-of-words 벡터. 모델 다운로드 없이 파이프라인을 확인할 때 쓴다."""

    def __init__(self, dim: int = 384):
        self.name = f"hash-{dim}"
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
                out[i, h % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


def load_embedder() -> Embedder:
    backend = os.getenv("EMBED_BACKEND", "sentence-transformers").lower()
    if backend == "hash":
        return HashEmbedder()
    return SentenceTransformerEmbedder(os.getenv("EMBED_MODEL", DEFAULT_MODEL))
