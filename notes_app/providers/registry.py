import logging
from typing import List, Dict, Any, Tuple
from ..config import ProviderConfig, load_providers
from .openai_compatible import OpenAIProviderClient

logger = logging.getLogger(__name__)

class ProviderRegistry:
    def __init__(self, config_path: str, local_override_path: str = None):
        self.providers: List[ProviderConfig] = load_providers(config_path, local_override_path)
        # Sort by priority, lowest number = highest priority (e.g. 1 is first)
        self.providers.sort(key=lambda p: p.priority)

    def get_client(self, provider: ProviderConfig) -> OpenAIProviderClient:
        if provider.protocol == "openai_compatible":
            return OpenAIProviderClient(provider)
        raise ValueError(f"Unsupported protocol: {provider.protocol}")

    def execute_with_fallback(self, system_prompt: str, user_payload: Dict[str, Any]) -> Tuple[str, ProviderConfig]:
        if not self.providers:
            raise RuntimeError("No enabled providers in the registry.")

        last_error = None
        for provider in self.providers:
            logger.info(f"Attempting notes generation with provider: {provider.id}")
            try:
                client = self.get_client(provider)
                result = client.generate_notes(system_prompt, user_payload)
                return result, provider
            except Exception as e:
                logger.warning(f"Provider {provider.id} failed with error: {e}. Trying next provider...")
                last_error = e
        
        raise RuntimeError(f"All providers failed. Last error: {last_error}")
