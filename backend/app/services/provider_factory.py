from app.core.config import settings as app_settings
from app.core.crypto import SecretCrypto
from app.models.settings import AppSettings
from app.providers.ai.base import AIProvider
from app.providers.ai.gemini_provider import GeminiProvider
from app.providers.ai.ollama_provider import OllamaProvider
from app.providers.ai.openai_provider import OpenAIProvider


def _decrypt_api_key(row: AppSettings) -> str | None:
    if not row.ai_api_key_encrypted:
        return None
    crypto = SecretCrypto(app_settings.encryption_key)
    value = crypto.decrypt(row.ai_api_key_encrypted)
    return value or None


def build_ai_provider(row: AppSettings) -> AIProvider:
    provider_name = (row.ai_provider or "openai").lower()
    api_key = _decrypt_api_key(row)
    if provider_name == "ollama":
        endpoint = row.ai_endpoint or "http://localhost:11434/api/generate"
        return OllamaProvider(endpoint=endpoint, model=row.ai_model)
    if provider_name == "gemini":
        endpoint = row.ai_endpoint or "https://generativelanguage.googleapis.com/v1beta"
        return GeminiProvider(endpoint=endpoint, model=row.ai_model, api_key=api_key)
    endpoint = row.ai_endpoint or "https://api.openai.com/v1/chat/completions"
    return OpenAIProvider(endpoint=endpoint, api_key=api_key, model=row.ai_model)
