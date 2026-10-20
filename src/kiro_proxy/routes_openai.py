import json
import time
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from kiro_proxy.auth import verify_api_key
from kiro_proxy.formatters import format_openai_messages
from kiro_proxy.registry import registry
from kiro_proxy.kiro_runner import run_kiro_stream, run_kiro_complete
from kiro_proxy.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ModelListResponse,
    ModelCard,
    Usage
)

router = APIRouter(dependencies=[Depends(verify_api_key)])

@router.get("/v1/models", response_model=ModelListResponse)
@router.get("/models", response_model=ModelListResponse)
async def list_models():
    """
    List models dynamically extracted from kiro-cli (or catalog fallback).
    """
    now = int(time.time())
    active_models = await registry.get_available_models()
    cards = [
        ModelCard(
            id=m["model_id"],
            created=now,
            owned_by="kiro"
        )
        for m in active_models
    ]
    return ModelListResponse(data=cards)

@router.post("/v1/chat/completions")
@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible Chat Completions endpoint with dynamic routing and stream-json parsing.
    Defaults to gpt-5.6-terra (or best available general model in active tier).
    """
    mapped_model = await registry.resolve_model(request.model, api_flavor="openai")
    prompt = format_openai_messages(request.messages)
    req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    if request.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            last_stop_reason = "stop"
            async for event in run_kiro_stream(prompt, model=mapped_model):
                if event["type"] == "chunk":
                    chunk_payload = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": mapped_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": event["text"]},
                                "finish_reason": None
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n"
                elif event["type"] == "done":
                    last_stop_reason = event.get("stop_reason", "stop")

            # Final finish_reason chunk
            final_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": mapped_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": last_stop_reason
                    }
                ]
            }
            yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    # Non-streaming response
    text, stop_reason = await run_kiro_complete(prompt, model=mapped_model)

    prompt_tokens = max(1, len(prompt.split()))
    completion_tokens = max(1, len(text.split()))

    return ChatCompletionResponse(
        id=req_id,
        created=created_ts,
        model=mapped_model,
        choices=[
            ChatCompletionResponseChoice(
                index=0,
                message={"role": "assistant", "content": text},
                finish_reason=stop_reason
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
    )
