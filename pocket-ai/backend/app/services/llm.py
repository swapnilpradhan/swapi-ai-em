"""LLM access, routed by tier.

Capabilities declare the tier they need; the registry resolves it to a model id. This
keeps a long-corpus operation affordable without hard-coding model names across the
codebase.
"""

from __future__ import annotations

from ..core.config import Settings
from ..core.logging import get_logger
from ..models import ModelTier

log = get_logger(__name__)


class StubLLMService:
    """Deterministic, offline responses.

    Returns something structurally plausible so downstream parsing and validation are
    exercised. It is intentionally obvious that the output is synthetic — stub output
    that looks real is a trap.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.calls: list[tuple[ModelTier, str]] = []

    async def complete(self, prompt: str, *, tier: ModelTier = ModelTier.FAST) -> str:
        self.calls.append((tier, prompt))
        log.debug("llm.stub", tier=tier.value, prompt_chars=len(prompt))
        return f"[stub:{tier.value}] no model configured; set ANTHROPIC_API_KEY for real output"


class AnthropicLLMService:
    """Real model access. Requires the ``llm`` extra and ``ANTHROPIC_API_KEY``."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    def _model_for(self, tier: ModelTier) -> str:
        return (
            self.settings.llm_model_reasoning
            if tier is ModelTier.REASONING
            else self.settings.llm_model_fast
        )

    async def complete(self, prompt: str, *, tier: ModelTier = ModelTier.FAST) -> str:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError("anthropic is not installed; run `uv sync --extra llm`") from exc

        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        response = await self._client.messages.create(
            model=self._model_for(tier),
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
