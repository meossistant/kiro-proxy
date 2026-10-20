import json
import logging
import time
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from kiro_proxy.auth import verify_api_key
from kiro_proxy.formatters import format_openai_messages
from kiro_proxy.registry import registry
from kiro_proxy.sessions import session_manager
from kiro_proxy.kiro_runner import run_kiro_stream, run_kiro_complete, SessionNotFoundError
from kiro_proxy.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ModelListResponse,
    ModelCard,
    Usage
)

logger = logging.getLogger("kiro-proxy.openai")

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
async def chat_completions(request: ChatCompletionRequest, raw_request: Request):
    """
    OpenAI-compatible Chat Completions endpoint with dynamic routing, stream-json parsing,
    and automatic conversation continuation for cached token reuse.
    """
    mapped_model = await registry.resolve_model(request.model, api_flavor="openai")

    # Extract client key from header, user field, or message prefix hash
    client_key = session_manager.extract_client_key(
        headers=dict(raw_request.headers),
        body_user=request.user,
        messages=request.messages
    )

    resume_id, delta_messages, is_continuation = session_manager.prepare_turn(
        client_key, request.messages, mapped_model
    )
    prompt = format_openai_messages(delta_messages, is_continuation=is_continuation)

    req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    if request.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            last_stop_reason = "stop"
            captured_session_id = resume_id

            try:
                async for event in run_kiro_stream(prompt, model=mapped_model, resume_id=resume_id):
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
                        if event.get("session_id"):
                            captured_session_id = event["session_id"]
            except SessionNotFoundError:
                logger.warning(f"Resume failed for session '{resume_id}'. Invalidate and retry from scratch.")
                session_manager.invalidate_session(client_key=client_key)
                full_prompt = format_openai_messages(request.messages, is_continuation=False)
                async for event in run_kiro_stream(full_prompt, model=mapped_model, resume_id=None):
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
                        if event.get("session_id"):
                            captured_session_id = event["session_id"]

            if captured_session_id:
                session_manager.record_session(
                    client_key, captured_session_id, len(request.messages), mapped_model
                )

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
    captured_session_id = resume_id
    try:
        text, stop_reason, sid = await run_kiro_complete(prompt, model=mapped_model, resume_id=resume_id)
        if sid:
            captured_session_id = sid
    except SessionNotFoundError:
        logger.warning(f"Resume failed for session '{resume_id}'. Invalidate and retry from scratch.")
        session_manager.invalidate_session(client_key=client_key)
        full_prompt = format_openai_messages(request.messages, is_continuation=False)
        text, stop_reason, sid = await run_kiro_complete(full_prompt, model=mapped_model, resume_id=None)
        if sid:
            captured_session_id = sid

    if captured_session_id:
        session_manager.record_session(
            client_key, captured_session_id, len(request.messages), mapped_model
        )

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
