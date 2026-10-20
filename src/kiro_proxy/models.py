import time
import uuid
from typing import Any
from pydantic import BaseModel, Field

# ==============================================================================
# OpenAI Compatible Models
# ==============================================================================

class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]] | None = ""
    name: str | None = None

class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    user: str | None = None

class ChatCompletionResponseChoice(BaseModel):
    index: int = 0
    message: dict[str, Any]
    finish_reason: str = "stop"

class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionResponseChoice]
    usage: Usage = Field(default_factory=Usage)

class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: dict[str, Any]
    finish_reason: str | None = None

class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChunkChoice]

class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "kiro"

class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelCard]

# ==============================================================================
# Anthropic Compatible Models
# ==============================================================================

class AnthropicMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]

class AnthropicMessageRequest(BaseModel):
    model: str = "auto"
    messages: list[AnthropicMessage]
    system: str | list[dict[str, Any]] | None = None
    max_tokens: int = 4096
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    metadata: dict[str, Any] | None = None

class AnthropicContentBlock(BaseModel):
    type: str = "text"
    text: str

class AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

class AnthropicMessageResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:20]}")
    type: str = "message"
    role: str = "assistant"
    content: list[AnthropicContentBlock]
    model: str
    stop_reason: str = "end_turn"
    stop_sequence: str | None = None
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)
