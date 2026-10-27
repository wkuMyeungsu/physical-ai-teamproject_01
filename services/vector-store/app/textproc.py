"""OCR 텍스트 정리 · 청크 나누기 · 중복 판별용 정규화."""
from __future__ import annotations

import hashlib
import re

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")


def clean_ocr_text(text: str) -> str:
    """OCR 결과의 줄바꿈·하이픈 끊김·여분 공백을 정리한다."""
    t = text.replace("\r", "\n")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)  # 줄 끝 하이픈으로 끊긴 단어 잇기
    t = re.sub(r"\s*\n\s*", " ", t)
    t = re.sub(r"[ \t ]+", " ", t)
    return t.strip()


def normalize_for_hash(text: str) -> str:
    """중복 판별용: 대소문자·문장부호·공백 차이를 무시한다."""
    t = text.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def text_hash(text: str) -> str:
    return hashlib.sha1(normalize_for_hash(text).encode()).hexdigest()


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def chunk_text(text: str, max_chars: int = 500, overlap_sentences: int = 1) -> list[str]:
    """문장 단위로 묶어 max_chars 이하 청크를 만든다. 청크 사이에 문장을 겹쳐 문맥을 잇는다."""
    sents = split_sentences(text)
    if not sents:
        return []

    # 문장 하나가 너무 길면 단어 단위로 자른다
    pieces: list[str] = []
    for s in sents:
        if len(s) <= max_chars:
            pieces.append(s)
            continue
        words, buf = s.split(), ""
        for w in words:
            if buf and len(buf) + 1 + len(w) > max_chars:
                pieces.append(buf)
                buf = w
            else:
                buf = f"{buf} {w}".strip()
        if buf:
            pieces.append(buf)

    chunks: list[str] = []
    cur: list[str] = []
    for p in pieces:
        if cur and len(" ".join(cur + [p])) > max_chars:
            chunks.append(" ".join(cur))
            keep = cur[-overlap_sentences:] if overlap_sentences else []
            # 겹치는 문장 + 새 문장이 한도를 넘으면 겹침을 버린다
            cur = keep if len(" ".join(keep + [p])) <= max_chars else []
        cur.append(p)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def is_meaningful(text: str, min_chars: int = 15, min_words: int = 3) -> bool:
    """OCR 잡음(기호 몇 개, 단어 한두 개)을 걸러낸다."""
    letters = sum(c.isalpha() for c in text)
    words = re.findall(r"[A-Za-z]{2,}", text)
    return letters >= min_chars and len(words) >= min_words
