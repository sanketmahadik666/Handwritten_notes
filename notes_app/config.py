import os
import yaml
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ProviderConfig:
    id: str
    label: str
    protocol: str
    enabled: bool
    priority: int
    base_url: str
    model: str
    api_key_env: Optional[str]
    timeout_s: int = 60
    max_tokens: int = 1200
    concurrency_limit: int = 2

    @property
    def api_key(self) -> Optional[str]:
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None

def load_providers(config_path: str, local_override_path: Optional[str] = None) -> List[ProviderConfig]:
    providers_data = []
    
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and "providers" in data:
                providers_data = data["providers"]
                
    if local_override_path and os.path.exists(local_override_path):
        with open(local_override_path, "r", encoding="utf-8") as f:
            local_data = yaml.safe_load(f)
            if local_data and "providers" in local_data:
                # Merge logic: if same id, override
                local_providers = {p["id"]: p for p in local_data["providers"]}
                merged = []
                for p in providers_data:
                    if p["id"] in local_providers:
                        p.update(local_providers[p["id"]])
                        del local_providers[p["id"]]
                    merged.append(p)
                for p in local_providers.values():
                    merged.append(p)
                providers_data = merged

    return [ProviderConfig(**p) for p in providers_data if p.get("enabled", True)]
