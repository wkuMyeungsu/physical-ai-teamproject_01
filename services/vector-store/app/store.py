"""텍스트 + 벡터 저장소 (SQLite 파일 + 메모리 행렬).

- 영구 저장: SQLite (DB_PATH, 기본 /app/data/vectors.db)
- 검색: 시작할 때 벡터를 메모리 행렬로 올려 두고 코사인 유사도(정규화 벡터의 내적)로 찾는다.
  수업 프로젝트 규모(수만 건 이하)에서는 별도 벡터 DB 없이도 충분히 빠르다.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text        TEXT NOT NULL,
    text_hash   TEXT NOT NULL UNIQUE,
    source      TEXT,
    frame_id    TEXT,
    metadata    TEXT,
    created_at  REAL NOT NULL,
    embedding   BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_created ON chunks(created_at);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


@dataclass
class Record:
    id: str
    doc_id: str
    chunk_index: int
    text: str
    source: str | None
    frame_id: str | None
    metadata: dict = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "source": self.source,
            "frame_id": self.frame_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class VectorStore:
    def __init__(self, path: str, dim: int, model_name: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.dim = dim
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._check_model(model_name)
        self._ids: list[str] = []
        self._matrix = np.zeros((0, dim), dtype=np.float32)
        self._load()

    # ---- 내부 ----
    def _check_model(self, model_name: str) -> None:
        """모델을 바꾸면 기존 벡터와 차원·공간이 달라지므로 섞이지 않게 막는다."""
        row = self._db.execute("SELECT value FROM meta WHERE key='model'").fetchone()
        if row is None:
            self._db.execute("INSERT INTO meta VALUES ('model', ?)", (model_name,))
            self._db.commit()
        elif row["value"] != model_name:
            raise RuntimeError(
                f"DB는 '{row['value']}' 모델로 만들어졌는데 지금 모델은 '{model_name}'입니다. "
                "DB 파일을 지우거나 같은 모델을 쓰세요."
            )

    def _load(self) -> None:
        rows = self._db.execute("SELECT id, embedding FROM chunks ORDER BY created_at").fetchall()
        self._ids = [r["id"] for r in rows]
        if rows:
            self._matrix = np.vstack(
                [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]
            )

    @staticmethod
    def _row_to_record(r: sqlite3.Row) -> Record:
        return Record(
            id=r["id"],
            doc_id=r["doc_id"],
            chunk_index=r["chunk_index"],
            text=r["text"],
            source=r["source"],
            frame_id=r["frame_id"],
            metadata=json.loads(r["metadata"] or "{}"),
            created_at=r["created_at"],
        )

    # ---- 조회 ----
    def has_hash(self, h: str) -> bool:
        with self._lock:
            return (
                self._db.execute("SELECT 1 FROM chunks WHERE text_hash=?", (h,)).fetchone()
                is not None
            )

    def nearest(self, vec: np.ndarray) -> tuple[str | None, float]:
        with self._lock:
            if not self._ids:
                return None, 0.0
            sims = self._matrix @ vec
            i = int(np.argmax(sims))
            return self._ids[i], float(sims[i])

    def search(self, qvec: np.ndarray, top_k: int, min_score: float, source: str | None = None):
        with self._lock:
            if not self._ids:
                return []
            sims = self._matrix @ qvec
            order = np.argsort(-sims)
            out = []
            for i in order:
                score = float(sims[i])
                if score < min_score:
                    break
                rec = self.get(self._ids[i])
                if rec is None or (source and rec.source != source):
                    continue
                out.append((rec, score))
                if len(out) >= top_k:
                    break
            return out

    def get(self, rid: str) -> Record | None:
        with self._lock:
            r = self._db.execute("SELECT * FROM chunks WHERE id=?", (rid,)).fetchone()
            return self._row_to_record(r) if r else None

    def list(self, limit: int = 50, offset: int = 0, since: float | None = None) -> list[Record]:
        with self._lock:
            if since is not None:
                rows = self._db.execute(
                    "SELECT * FROM chunks WHERE created_at > ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (since, limit, offset),
                ).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT * FROM chunks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return len(self._ids)

    def doc_count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks").fetchone()[0]

    def last_created_at(self) -> float | None:
        with self._lock:
            return self._db.execute("SELECT MAX(created_at) FROM chunks").fetchone()[0]

    # ---- 쓰기 ----
    def add(
        self,
        doc_id: str,
        chunk_index: int,
        text: str,
        h: str,
        vec: np.ndarray,
        source: str | None,
        frame_id: str | None,
        metadata: dict,
    ) -> Record:
        rec = Record(
            id=uuid.uuid4().hex,
            doc_id=doc_id,
            chunk_index=chunk_index,
            text=text,
            source=source,
            frame_id=frame_id,
            metadata=metadata,
            created_at=time.time(),
        )
        vec = np.asarray(vec, dtype=np.float32).reshape(self.dim)
        with self._lock:
            self._db.execute(
                "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    rec.id, doc_id, chunk_index, text, h, source, frame_id,
                    json.dumps(metadata, ensure_ascii=False), rec.created_at, vec.tobytes(),
                ),
            )
            self._db.commit()
            self._ids.append(rec.id)
            self._matrix = np.vstack([self._matrix, vec[None, :]])
        return rec

    def delete(self, rid: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM chunks WHERE id=?", (rid,))
            self._db.commit()
            if cur.rowcount == 0:
                return False
            i = self._ids.index(rid)
            self._ids.pop(i)
            self._matrix = np.delete(self._matrix, i, axis=0)
            return True

    def clear(self) -> int:
        with self._lock:
            n = len(self._ids)
            self._db.execute("DELETE FROM chunks")
            self._db.commit()
            self._ids = []
            self._matrix = np.zeros((0, self.dim), dtype=np.float32)
            return n
