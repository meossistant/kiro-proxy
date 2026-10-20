import json
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from kiro_proxy.auth import verify_api_key
from kiro_proxy.formatters import map_model_name, format_anthropic_messages
from kiro_proxy.kiro_runner import run_kiro_stream, run_kiro_complete
from kiro_proxy.models import (
    AnthropicMessageRequest,
    AnthropicMessageResponse,
    AnthropicContentBlock,
    AnthropicUsage
)

router = APIRouter(dependencies=[Depends(verify_api_key)])

@router.post("/v1/messages")
@router.post("/messages")
async def anthropic_messages(request: AnthropicMessageRequest):
    """
    Anthropic-compatible Messages API supporting both streaming SSE and JSON responses.
    """
    mapped_model = map_model_name(request.model)
    prompt = format_anthropic_messages(request.messages, system=request.system)
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
            async for event in run_kiro_stream(prompt, model=mapped_model):
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
    text, _ = await run_kiro_complete(prompt, model=mapped_model)
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
