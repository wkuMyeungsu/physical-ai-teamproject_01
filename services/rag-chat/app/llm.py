"""LLM 호출.

- LocalLLM (기본): 컨테이너 안에서 작은 모델(GGUF)을 llama.cpp로 CPU에서 돌린다. 키·비용 없음.
- AnthropicLLM (선택): RAG_LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY.

다른 모델·API로 바꿀 때는 같은 모양의 async complete()를 가진 클래스를 하나 더 만들면 된다.
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


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, model: str, timeout: float = 30.0):
        from anthropic import AsyncAnthropic  # ANTHROPIC_API_KEY 환경변수를 SDK가 읽는다

        self.model = model
        self._client = AsyncAnthropic(timeout=timeout, max_retries=2)

    async def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.2) -> str:
        import anthropic

        try:
            msg = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,  # 이 SDK 버전의 messages.create에는 temperature 인자가 없어서 넘기지 않는다
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AnthropicError as e:
            raise LLMError(f"{type(e).__name__}: {e}") from e
        text = "".join(block.text for block in msg.content if block.type == "text").strip()
        if not text:
            raise LLMError("빈 응답")
        return text

