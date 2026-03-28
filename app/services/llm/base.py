"""
Abstract base class for LLM services.
All providers (Ollama, OpenAI) must implement this interface.
Swapping providers requires only changing LLM_BACKEND in .env.
"""

from abc import ABC, abstractmethod


class BaseLLMService(ABC):
    """Interface-driven LLM abstraction."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt and return the model's text response."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the LLM backend is reachable."""
        ...
