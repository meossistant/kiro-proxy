import json
import logging
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from kiro_proxy.auth import verify_api_key
from kiro_proxy.formatters import format_anthropic_messages
from kiro_proxy.registry import registry
from kiro_proxy.sessions import session_manager
from kiro_proxy.kiro_runner import run_kiro_stream, run_kiro_complete, SessionNotFoundError
from kiro_proxy.models import (
    AnthropicMessageRequest,
    AnthropicMessageResponse,
    AnthropicContentBlock,
    AnthropicUsage
)

logger = logging.getLogger("kiro-proxy.anthropic")

router = APIRouter(dependencies=[Depends(verify_api_key)])

@router.post("/v1/messages")
@router.post("/messages")
async def anthropic_messages(request: AnthropicMessageRequest, raw_request: Request):
    """
    Anthropic-compatible Messages API with dynamic routing, stream-json parsing,
    and automatic conversation continuation for cached token reuse.
    """
    mapped_model = await registry.resolve_model(request.model, api_flavor="anthropic")
    
    # Extract client conversation identifier (e.g. from Claude Code CLI x-claude-code-session-id)
    client_key = session_manager.extract_client_key(
        headers=dict(raw_request.headers),
        body_metadata=request.metadata,
        messages=request.messages,
        system=request.system
    )

    resume_id, delta_messages, is_continuation = session_manager.prepare_turn(
        client_key, request.messages, mapped_model
    )
    prompt = format_anthropic_messages(
        delta_messages, system=request.system, is_continuation=is_continuation
    )

    msg_id = f"msg_{uuid.uuid4().hex[:20]}"
    prompt_tokens = max(1, len(prompt.split()))

    if request.stream:
        async def event_generator() -> AsyncGenerator[str, None]:
            # 1. message_start
            start_payload = {
                "type": "message_start",
                "message": {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": mapped_model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": prompt_tokens,
                        "output_tokens": 0
                    }
                }
            }
            yield f"event: message_start\ndata: {json.dumps(start_payload, ensure_ascii=False)}\n\n"

            # 2. content_block_start
            block_start_payload = {
                "type": "content_block_start",
                "index": 0,
                "content_block": {
                    "type": "text",
                    "text": ""
                }
            }
            yield f"event: content_block_start\ndata: {json.dumps(block_start_payload, ensure_ascii=False)}\n\n"

            accumulated_output = ""
            captured_session_id = resume_id

            try:
                async for event in run_kiro_stream(prompt, model=mapped_model, resume_id=resume_id):
                    if event["type"] == "chunk":
                        chunk_text = event["text"]
                        accumulated_output += chunk_text
                        delta_payload = {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {
                                "type": "text_delta",
                                "text": chunk_text
                            }
                        }
                        yield f"event: content_block_delta\ndata: {json.dumps(delta_payload, ensure_ascii=False)}\n\n"
                    elif event["type"] == "done":
                        if event.get("session_id"):
                            captured_session_id = event["session_id"]
            except SessionNotFoundError:
                logger.warning(f"Resume failed for session '{resume_id}'. Invalidate and retry from scratch.")
                session_manager.invalidate_session(client_key=client_key)
                # Fallback to full prompt without resume_id
                full_prompt = format_anthropic_messages(
                    request.messages, system=request.system, is_continuation=False
                )
                async for event in run_kiro_stream(full_prompt, model=mapped_model, resume_id=None):
                    if event["type"] == "chunk":
                        chunk_text = event["text"]
                        accumulated_output += chunk_text
                        delta_payload = {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {
                                "type": "text_delta",
                                "text": chunk_text
                            }
                        }
                        yield f"event: content_block_delta\ndata: {json.dumps(delta_payload, ensure_ascii=False)}\n\n"
                    elif event["type"] == "done":
                        if event.get("session_id"):
                            captured_session_id = event["session_id"]

            # Record session state on completion
            if captured_session_id:
                session_manager.record_session(
                    client_key, captured_session_id, len(request.messages), mapped_model
                )

            # 3. content_block_stop
            block_stop_payload = {
                "type": "content_block_stop",
                "index": 0
            }
            yield f"event: content_block_stop\ndata: {json.dumps(block_stop_payload, ensure_ascii=False)}\n\n"

            # 4. message_delta
            output_tokens = max(1, len(accumulated_output.split()))
            msg_delta_payload = {
                "type": "message_delta",
                "delta": {
                    "stop_reason": "end_turn",
                    "stop_sequence": None
                },
                "usage": {
                    "output_tokens": output_tokens
                }
            }
            yield f"event: message_delta\ndata: {json.dumps(msg_delta_payload, ensure_ascii=False)}\n\n"

            # 5. message_stop
            yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"

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
        text, _, sid = await run_kiro_complete(prompt, model=mapped_model, resume_id=resume_id)
        if sid:
            captured_session_id = sid
    except SessionNotFoundError:
        logger.warning(f"Resume failed for session '{resume_id}'. Invalidate and retry from scratch.")
        session_manager.invalidate_session(client_key=client_key)
        full_prompt = format_anthropic_messages(
            request.messages, system=request.system, is_continuation=False
        )
        text, _, sid = await run_kiro_complete(full_prompt, model=mapped_model, resume_id=None)
        if sid:
            captured_session_id = sid

    if captured_session_id:
        session_manager.record_session(
            client_key, captured_session_id, len(request.messages), mapped_model
        )

    output_tokens = max(1, len(text.split()))

    return AnthropicMessageResponse(
        id=msg_id,
        model=mapped_model,
        content=[AnthropicContentBlock(type="text", text=text)],
        stop_reason="end_turn",
        usage=AnthropicUsage(
            input_tokens=prompt_tokens,
            output_tokens=output_tokens
        )
    )
