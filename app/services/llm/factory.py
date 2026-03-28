"""
LLM service factory.
Returns the correct provider based on LLM_BACKEND config.
Swap Ollama ↔ OpenAI by changing a single env var — zero business logic changes.
"""

from app.services.llm.base import BaseLLMService


def get_llm_service(backend: str) -> BaseLLMService:
    if backend == "openai":
        from app.services.llm.openai_service import OpenAILLMService
        return OpenAILLMService()

    # Default: ollama (local Llama 3)
    from app.services.llm.ollama_service import OllamaLLMService
    return OllamaLLMService()
