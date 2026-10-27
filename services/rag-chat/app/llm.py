"""LLM 호출. 다른 회사 API로 바꿀 때는 complete()만 같은 모양으로 맞춘 클래스를 하나 더 만들면 된다."""
from __future__ import annotations


class LLMError(Exception):
    """LLM API 호출이 실패했을 때."""


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, model: str, timeout: float = 30.0):
        from anthropic import AsyncAnthropic  # ANTHROPIC_API_KEY 환경변수를 SDK가 읽는다

        self.model = model
        self._client = AsyncAnthropic(timeout=timeout, max_retries=2)

    async def complete(self, system: str, user: str, max_tokens: int = 500) -> str:
        import anthropic

        try:
            msg = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AnthropicError as e:
            raise LLMError(f"{type(e).__name__}: {e}") from e
        text = "".join(block.text for block in msg.content if block.type == "text").strip()
        if not text:
            raise LLMError("빈 응답")
        return text
