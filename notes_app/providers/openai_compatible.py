import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from ..config import ProviderConfig

logger = logging.getLogger(__name__)

class OpenAIProviderClient:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def generate_notes(self, system_prompt: str, user_payload: Dict[str, Any]) -> str:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        api_key = self.config.api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        data = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ],
            "max_tokens": self.config.max_tokens
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP Error: {response.status}")
                
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data["choices"][0]["message"]["content"]

        except urllib.error.HTTPError as e:
            logger.warning(f"Provider {self.config.id} HTTP error: {e.code} - {e.reason}")
            raise
        except Exception as e:
            logger.warning(f"Provider {self.config.id} failed: {str(e)}")
            raise
