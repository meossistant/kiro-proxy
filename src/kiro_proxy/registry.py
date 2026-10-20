import asyncio
import json
import logging
import time
from typing import Any
from kiro_proxy.config import settings

logger = logging.getLogger("kiro-proxy")

# Known catalog of models across both Free and Paid (Pro) tiers
ALL_KNOWN_MODELS = [
    {
        "model_id": "auto",
        "model_name": "auto",
        "description": "Models chosen by task for optimal usage and consistent quality",
        "context_window_tokens": 1000000,
        "rate_multiplier": 1.0,
        "rate_unit": "Credit"
    },
    {
        "model_id": "claude-opus-5.5",
        "model_name": "claude-opus-5.5",
        "description": "Experimental preview of Claude Opus 5.5 model with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 2.0,
        "rate_unit": "Credit"
    },
    {
        "model_id": "claude-sonnet-5.5",
        "model_name": "claude-sonnet-5.5",
        "description": "Claude Sonnet 5.5 model with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 1.3,
        "rate_unit": "Credit"
    },
    {
        "model_id": "claude-opus-5",
        "model_name": "claude-opus-5",
        "description": "Claude Opus 5 model with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 2.2,
        "rate_unit": "Credit"
    },
    {
        "model_id": "claude-sonnet-5",
        "model_name": "claude-sonnet-5",
        "description": "Claude Sonnet 5 model with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 1.3,
        "rate_unit": "Credit"
    },
    {
        "model_id": "claude-opus-4.8",
        "model_name": "claude-opus-4.8",
        "description": "Claude Opus 4.8 model with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 2.2,
        "rate_unit": "Credit"
    },
    {
        "model_id": "claude-sonnet-4.5",
        "model_name": "claude-sonnet-4.5",
        "description": "Claude Sonnet 4.5 model with 200k context window",
        "context_window_tokens": 200000,
        "rate_multiplier": 1.3,
        "rate_unit": "Credit"
    },
    {
        "model_id": "claude-haiku-4.5",
        "model_name": "claude-haiku-4.5",
        "description": "The latest Claude Haiku model",
        "context_window_tokens": 200000,
        "rate_multiplier": 0.4,
        "rate_unit": "Credit"
    },
    {
        "model_id": "gpt-5.6-sol",
        "model_name": "gpt-5.6-sol",
        "description": "Experimental preview of OpenAI GPT 5.6 Sol with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 4.4,
        "rate_unit": "Credit"
    },
    {
        "model_id": "gpt-5.6-terra",
        "model_name": "gpt-5.6-terra",
        "description": "Experimental preview of OpenAI GPT 5.6 Terra with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 2.2,
        "rate_unit": "Credit"
    },
    {
        "model_id": "gpt-5.6-luna",
        "model_name": "gpt-5.6-luna",
        "description": "Experimental preview of OpenAI GPT 5.6 Luna with 1M context window",
        "context_window_tokens": 1000000,
        "rate_multiplier": 0.6,
        "rate_unit": "Credit"
    },
    {
        "model_id": "deepseek-3.2",
        "model_name": "deepseek-3.2",
        "description": "Experimental preview of DeepSeek V3.2",
        "context_window_tokens": 164000,
        "rate_multiplier": 0.25,
        "rate_unit": "Credit"
    },
    {
        "model_id": "minimax-m2.5",
        "model_name": "minimax-m2.5",
        "description": "MiniMax M2.5 model",
        "context_window_tokens": 196000,
        "rate_multiplier": 0.25,
        "rate_unit": "Credit"
    },
    {
        "model_id": "minimax-m2.1",
        "model_name": "minimax-m2.1",
        "description": "Experimental preview of MiniMax M2.1",
        "context_window_tokens": 196000,
        "rate_multiplier": 0.15,
        "rate_unit": "Credit"
    },
    {
        "model_id": "glm-5",
        "model_name": "glm-5",
        "description": "GLM-5 model",
        "context_window_tokens": 200000,
        "rate_multiplier": 0.5,
        "rate_unit": "Credit"
    },
    {
        "model_id": "qwen3-coder-next",
        "model_name": "qwen3-coder-next",
        "description": "Experimental preview of Qwen3 Coder Next",
        "context_window_tokens": 256000,
        "rate_multiplier": 0.05,
        "rate_unit": "Credit"
    }
]

class ModelRegistry:
    def __init__(self, cache_ttl_seconds: int = 300):
        self._cached_models: list[dict[str, Any]] = []
        self._last_fetched_ts: float = 0.0
        self._cache_ttl: int = cache_ttl_seconds
        self._lock = asyncio.Lock()

    async def get_available_models(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """
        Dynamically query kiro-cli for available models with TTL caching.
        """
        now = time.time()
        if not force_refresh and self._cached_models and (now - self._last_fetched_ts < self._cache_ttl):
            return self._cached_models

        async with self._lock:
            # Recheck after acquiring lock
            if not force_refresh and self._cached_models and (time.time() - self._last_fetched_ts < self._cache_ttl):
                return self._cached_models

            models = await self._fetch_from_cli()
            if models:
                self._cached_models = models
                self._last_fetched_ts = time.time()
                logger.info(f"Discovered {len(models)} active models from kiro-cli: {[m['model_id'] for m in models]}")
            elif not self._cached_models:
                # Fallback to catalog
                self._cached_models = ALL_KNOWN_MODELS
                self._last_fetched_ts = time.time()
                logger.warning("Could not fetch models from kiro-cli; using catalog fallback.")

            return self._cached_models

    async def _fetch_from_cli(self) -> list[dict[str, Any]]:
        cmd = [settings.KIRO_CLI_PATH, "chat", "--list-models", "--format", "json"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0 and stdout:
                data = json.loads(stdout.decode("utf-8"))
                models = data.get("models", [])
                if isinstance(models, list) and models:
                    return models
        except Exception as e:
            logger.warning(f"Failed to query kiro-cli --list-models: {e}")
        return []

    def get_available_model_ids_sync(self) -> list[str]:
        """Return currently cached model IDs or catalog IDs."""
        if self._cached_models:
            return [m["model_id"] for m in self._cached_models]
        return [m["model_id"] for m in ALL_KNOWN_MODELS]

    async def resolve_model(self, requested_model: str | None, api_flavor: str = "openai") -> str:
        """
        Smart resolution and auto-routing for requested model:
        - Default for anthropic: sonnet (claude-sonnet-5.5 -> claude-sonnet-5 -> claude-sonnet-4.5)
        - Default for openai: gpt-5.6-terra (or fallback to available sonnet)
        - Maps requests (e.g. gpt-4o, claude-opus, etc.) to best available models in current tier.
        """
        active_models = await self.get_available_models()
        active_ids = {m["model_id"] for m in active_models}

        # Helper to pick first available model from candidate list
        def pick_first_available(candidates: list[str]) -> str | None:
            for cand in candidates:
                if cand in active_ids:
                    return cand
            return None

        # Best available Sonnet in active tier
        sonnet_candidates = ["claude-sonnet-5.5", "claude-sonnet-5", "claude-sonnet-4.5"]
        best_sonnet = pick_first_available(sonnet_candidates) or "auto"

        # Best available Terra / GPT in active tier
        gpt_candidates = ["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-luna"]
        best_gpt = pick_first_available(gpt_candidates) or best_sonnet

        # Best available Opus in active tier
        opus_candidates = ["claude-opus-5.5", "claude-opus-5", "claude-opus-4.8"]
        best_opus = pick_first_available(opus_candidates) or best_sonnet

        # Best available Haiku in active tier
        haiku_candidates = ["claude-haiku-4.5", "gpt-5.6-luna"]
        best_haiku = pick_first_available(haiku_candidates) or best_sonnet

        # If no model requested or empty, use defaults per prompt instructions
        if not requested_model or requested_model.strip().lower() in ("", "default", "auto"):
            if api_flavor == "anthropic":
                return best_sonnet
            else:
                return best_gpt

        req_clean = requested_model.strip().lower().replace("_", "-")

        # 1. Exact match with an active model in kiro-cli
        if req_clean in active_ids:
            return req_clean

        # 2. GPT / OpenAI Family
        if any(k in req_clean for k in ["sol", "o1", "o3", "reasoning", "r1"]):
            return pick_first_available(["gpt-5.6-sol"]) or best_opus

        if any(k in req_clean for k in ["terra", "gpt-4", "gpt-5", "chatgpt"]):
            return best_gpt

        if any(k in req_clean for k in ["luna", "mini", "flash", "small"]):
            return best_haiku

        if "gpt" in req_clean:
            return best_gpt

        # 3. Claude / Anthropic Family
        if "opus" in req_clean:
            if "5.5" in req_clean and "claude-opus-5.5" in active_ids:
                return "claude-opus-5.5"
            if "5" in req_clean and "claude-opus-5" in active_ids:
                return "claude-opus-5"
            if "4.8" in req_clean and "claude-opus-4.8" in active_ids:
                return "claude-opus-4.8"
            return best_opus

        if "sonnet" in req_clean:
            if "5.5" in req_clean and "claude-sonnet-5.5" in active_ids:
                return "claude-sonnet-5.5"
            if "5" in req_clean and "claude-sonnet-5" in active_ids:
                return "claude-sonnet-5"
            if "4.5" in req_clean and "claude-sonnet-4.5" in active_ids:
                return "claude-sonnet-4.5"
            return best_sonnet

        if "haiku" in req_clean:
            return best_haiku

        if "claude" in req_clean:
            return best_sonnet

        # 4. Other Model Families
        if "deepseek" in req_clean:
            return pick_first_available(["deepseek-3.2"]) or best_sonnet

        if "qwen" in req_clean:
            return pick_first_available(["qwen3-coder-next"]) or best_sonnet

        if "minimax" in req_clean:
            if "2.1" in req_clean and "minimax-m2.1" in active_ids:
                return "minimax-m2.1"
            return pick_first_available(["minimax-m2.5", "minimax-m2.1"]) or best_sonnet

        if "glm" in req_clean:
            return pick_first_available(["glm-5"]) or best_sonnet

        # 5. Fuzzy / Substring Match against active models
        for m_id in active_ids:
            if req_clean in m_id or m_id in req_clean:
                return m_id

        # 6. Fallback based on API flavor
        return best_sonnet if api_flavor == "anthropic" else best_gpt

registry = ModelRegistry()
