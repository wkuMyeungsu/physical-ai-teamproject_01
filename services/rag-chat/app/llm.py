"""LLM 호출: 컨테이너 안에서 작은 모델(GGUF)을 llama.cpp로 CPU에서 돌린다. 키·비용 없음.

다른 모델로 바꿀 때는 RAG_LOCAL_MODEL_REPO / RAG_LOCAL_MODEL_FILE만 바꾸면 된다.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

log = logging.getLogger("uvicorn.error")


class LLMError(Exception):
    """LLM 호출이 실패했을 때."""


class LLMUnavailable(Exception):
    """LLM을 준비할 수 없을 때 (모델 파일 없음 등). 서비스는 LLM 없이 계속 뜬다."""


def ensure_model_file(path: str, repo: str, filename: str) -> str:
    """모델 파일이 없으면 Hugging Face에서 받는다. 보통은 Docker 빌드 때 이미 받아 둔다."""
    if Path(path).is_file():
        return path
    if not repo:
        raise LLMUnavailable(f"모델 파일이 없습니다: {path}")
    log.info("모델 파일이 없어 내려받습니다: %s/%s", repo, filename)
    try:
        from huggingface_hub import hf_hub_download

        return hf_hub_download(repo_id=repo, filename=filename, local_dir=str(Path(path).parent))
    except Exception as e:  # 네트워크·저장소 이름 오류 등
        raise LLMUnavailable(f"모델을 내려받지 못했습니다 ({repo}/{filename}): {type(e).__name__}: {e}") from e


class LocalLLM:
    name = "local"

    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int | None = None):
        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise LLMUnavailable("llama-cpp-python이 설치되어 있지 않습니다.") from e
        try:
            self._llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads, verbose=False)
        except Exception as e:
            raise LLMUnavailable(f"모델을 불러오지 못했습니다 ({model_path}): {type(e).__name__}: {e}") from e
        self.model = Path(model_path).name
        self._lock = asyncio.Lock()  # llama.cpp 모델 하나는 한 번에 한 요청만 처리한다

    def _generate(self, system: str, user: str, max_tokens: int, temperature: float) -> str:
        out = self._llm.create_chat_completion(
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (out["choices"][0]["message"].get("content") or "").strip()

    async def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.2) -> str:
        async with self._lock:
            try:
                # CPU를 오래 쓰는 작업이라 별도 스레드에서 돌려 서버가 멈추지 않게 한다
                text = await asyncio.to_thread(self._generate, system, user, max_tokens, temperature)
            except Exception as e:
                raise LLMError(f"{type(e).__name__}: {e}") from e
        if not text:
            raise LLMError("빈 응답")
        return text

