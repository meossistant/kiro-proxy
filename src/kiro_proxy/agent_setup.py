import json
import logging
from pathlib import Path
from kiro_proxy.config import settings

logger = logging.getLogger("kiro-proxy")

DEFAULT_GENERIC_PROMPT = (
    "You are a helpful, knowledgeable, versatile, and direct AI assistant. "
    "Follow user instructions faithfully and answer clearly, accurately, and thoughtfully "
    "without assuming any specific IDE, platform, or terminal environment unless explicitly requested."
)

def ensure_custom_agent(agent_name: str | None = None) -> Path:
    """
    Ensure the custom agent JSON configuration exists in ~/.kiro/agents/<name>.json.
    """
    name = agent_name or settings.KIRO_AGENT
    agents_dir = Path.home() / ".kiro" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    agent_file = agents_dir / f"{name}.json"
    if not agent_file.exists():
        logger.info(f"Creating custom generic agent at {agent_file}")
        agent_data = {
            "name": name,
            "description": f"Custom generic agent '{name}' for versatile chat proxy",
            "prompt": DEFAULT_GENERIC_PROMPT,
            "tools": [],
            "allowedTools": [],
            "model": settings.DEFAULT_MODEL
        }
        with open(agent_file, "w", encoding="utf-8") as f:
            json.dump(agent_data, f, indent=2, ensure_ascii=False)
    else:
        logger.debug(f"Custom agent '{name}' already exists at {agent_file}")

    return agent_file
