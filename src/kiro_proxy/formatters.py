from typing import Any
from kiro_proxy.models import ChatMessage, AnthropicMessage

VALID_KIRO_MODELS = [
    "auto",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "deepseek-3.2",
    "minimax-m2.5",
    "minimax-m2.1",
    "glm-5",
    "qwen3-coder-next",
]

def map_model_name(requested_model: str | None) -> str:
    """
    Resolve requested model name to one of the valid Kiro CLI model identifiers.
    """
    if not requested_model:
        return "auto"

    model_lower = requested_model.strip().lower()

    # Exact match check
    if model_lower in VALID_KIRO_MODELS:
        return model_lower

    # Keyword / prefix heuristic mapping
    if "haiku" in model_lower or "mini" in model_lower or "3.5" in model_lower:
        return "claude-haiku-4.5"
    if "sonnet" in model_lower or "gpt-4" in model_lower or "opus" in model_lower:
        return "claude-sonnet-4.5"
    if "deepseek" in model_lower:
        return "deepseek-3.2"
    if "qwen" in model_lower:
        return "qwen3-coder-next"
    if "minimax" in model_lower:
        return "minimax-m2.5"
    if "glm" in model_lower:
        return "glm-5"

    return "auto"

def _extract_text(content: str | list[dict[str, Any]] | None) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    parts.append(str(item.get("text", "")))
                elif item_type == "tool_use":
                    tool_name = item.get("name", "tool")
                    tool_input = item.get("input", {})
                    parts.append(f"[Tool Request: {tool_name}\nArguments: {tool_input}]")
                elif item_type == "tool_result":
                    tool_res = item.get("content", "")
                    tool_id = item.get("tool_use_id", "")
                    parts.append(f"[Tool Result ({tool_id}):\n{tool_res}]")
                elif "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)

def format_openai_messages(messages: list[ChatMessage], is_continuation: bool = False) -> str:
    """
    Format a sequence of OpenAI chat messages into a prompt.
    If is_continuation is True, skips system instructions and formats only the delta turns.
    """
    if not messages:
        return ""

    system_instructions: list[str] = []
    conversation: list[tuple[str, str]] = []

    for msg in messages:
        role = msg.role.lower()
        text = _extract_text(msg.content)
        if not text:
            continue
        if role == "system":
            if not is_continuation:
                system_instructions.append(text)
        elif role in ("user", "human"):
            conversation.append(("User", text))
        elif role in ("assistant", "ai", "bot"):
            conversation.append(("Assistant", text))
        else:
            conversation.append((role.capitalize(), text))

    prompt_parts: list[str] = []
    if system_instructions and not is_continuation:
        prompt_parts.append("[System Instructions]\n" + "\n\n".join(system_instructions))

    if len(conversation) == 1 and conversation[0][0] == "User":
        prompt_parts.append(conversation[0][1])
    elif conversation:
        history_lines: list[str] = []
        for speaker, speech in conversation:
            history_lines.append(f"{speaker}: {speech}")
        if is_continuation:
            prompt_parts.append("\n\n".join(history_lines))
        else:
            prompt_parts.append("[Conversation]\n" + "\n\n".join(history_lines))

    return "\n\n".join(prompt_parts).strip()

def format_anthropic_messages(
    messages: list[AnthropicMessage],
    system: str | list[dict[str, Any]] | None = None,
    is_continuation: bool = False
) -> str:
    """
    Format Anthropic messages and optional system prompt into a prompt string.
    If is_continuation is True, skips system prompt and formats only delta turns.
    """
    prompt_parts: list[str] = []

    if not is_continuation:
        system_text = _extract_text(system)
        if system_text:
            prompt_parts.append(f"[System Instructions]\n{system_text}")

    conversation: list[tuple[str, str]] = []
    for msg in messages:
        role = msg.role.lower()
        text = _extract_text(msg.content)
        if not text:
            continue
        if role in ("user", "human"):
            conversation.append(("User", text))
        elif role in ("assistant", "ai"):
            conversation.append(("Assistant", text))
        elif role == "system" and is_continuation:
            # Skip system in continuation
            continue
        else:
            conversation.append((role.capitalize(), text))

    if len(conversation) == 1 and conversation[0][0] == "User":
        prompt_parts.append(conversation[0][1])
    elif conversation:
        history_lines: list[str] = []
        for speaker, speech in conversation:
            history_lines.append(f"{speaker}: {speech}")
        if is_continuation:
            prompt_parts.append("\n\n".join(history_lines))
        else:
            prompt_parts.append("[Conversation]\n" + "\n\n".join(history_lines))

    return "\n\n".join(prompt_parts).strip()

