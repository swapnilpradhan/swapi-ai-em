"""Service resolution.

The only module that imports concrete implementations. Everything else depends on the
protocols in ``protocols.py``, which is what keeps the seams honest — a service cannot
accidentally couple to a provider-specific detail when a stub has to satisfy the same
interface.
"""

from __future__ import annotations

from functools import lru_cache

from ..agents.coach import StubCoachService
from ..agents.slide_builder import StubSlideBuilder
from ..core.config import Backend, Settings, get_settings
from .diarization import (
    EmbeddingIdentificationService,
    PyannoteDiarizationService,
    StubDiarizationService,
    StubIdentificationService,
)
from .insights import LLMInsightsService, StubInsightsService
from .llm import AnthropicLLMService, StubLLMService
from .pocket import HttpPocketClient, StubPocketClient
from .retrieval import GroundedChatService, StubRetrievalService
from .storage import DriveStorageService, StubStorageService
from .validation import DefaultSpanValidator


class ServiceRegistry:
    """Resolves each capability to a concrete implementation based on config."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.llm = (
            AnthropicLLMService(settings)
            if settings.llm_backend is Backend.REAL
            else StubLLMService(settings)
        )
        self.storage = (
            DriveStorageService(settings)
            if settings.storage_backend is Backend.REAL
            else StubStorageService(settings)
        )
        self.pocket = (
            HttpPocketClient(settings)
            if settings.pocket_backend is Backend.REAL
            else StubPocketClient(settings)
        )
        if settings.diarization_backend is Backend.REAL:
            self.diarization = PyannoteDiarizationService(settings)
            self.identification = EmbeddingIdentificationService(settings)
        else:
            self.diarization = StubDiarizationService(settings)
            self.identification = StubIdentificationService(settings)

        # Insights follow the LLM backend: real synthesis needs a real model.
        self.insights = (
            LLMInsightsService(settings, self.llm)
            if settings.llm_backend is Backend.REAL
            else StubInsightsService(settings, self.llm)
        )

        # Retrieval stays in-memory until Phase 3 wires Chroma.
        self.retrieval = StubRetrievalService(settings)
        self.chat = GroundedChatService(settings, self.retrieval, self.llm)
        self.coach = StubCoachService(settings, self.llm)
        self.slides = StubSlideBuilder(settings, self.llm)
        self.validator = DefaultSpanValidator()

    @property
    def stub_backends(self) -> list[str]:
        return self.settings.using_stubs()


@lru_cache
def get_registry() -> ServiceRegistry:
    return ServiceRegistry(get_settings())
