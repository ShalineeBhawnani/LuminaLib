"""
OpenAI LLM provider.
Conforms to BaseLLMService — swappable by setting LLM_BACKEND=openai in .env.
"""

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMService


class OpenAILLMService(BaseLLMService):
    def __init__(self) -> None:
        self._api_key = settings.OPENAI_API_KEY
        self._model = settings.OPENAI_MODEL
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=60.0,
        )

    async def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.post(
                "/chat/completions",
                json={"model": self._model, "messages": messages, "max_tokens": 1024},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/models")
            return r.status_code == 200
        except httpx.HTTPError:
            return False
