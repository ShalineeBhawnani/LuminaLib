"""
Ollama LLM provider (local Llama 3 via Ollama).
Conforms to BaseLLMService — swappable without touching business logic.
"""

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMService


class OllamaLLMService(BaseLLMService):
    def __init__(self) -> None:
        self._base_url = settings.OLLAMA_BASE_URL
        self._model = settings.OLLAMA_MODEL
        self._client = httpx.AsyncClient(timeout=120.0)

    async def generate(self, prompt: str, system: str | None = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

    async def health_check(self) -> bool:
        try:
            r = await self._client.get(f"{self._base_url}/api/tags")
            return r.status_code == 200
        except httpx.HTTPError:
            return False
