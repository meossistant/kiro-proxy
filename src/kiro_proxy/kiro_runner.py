import asyncio
import json
import logging
from typing import AsyncGenerator, Any
from fastapi import HTTPException
from kiro_proxy.config import settings

logger = logging.getLogger("kiro-proxy")

AUTH_ERROR_PATTERNS = [
    "not logged in",
    "welcome to kiro cli, let's get you signed in",
    "please try again with: kiro-cli login",
    "failed to open browser for authentication",
    "session expired",
    "unauthorized"
]

async def check_kiro_auth() -> dict[str, Any]:
    """
    Check if Kiro CLI currently has a valid authenticated session using 'kiro-cli whoami'.
    """
    cmd = [settings.KIRO_CLI_PATH, "whoami"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            info = stdout.decode("utf-8").strip()
            return {"authenticated": True, "info": info}
        else:
            return {"authenticated": False, "info": "Not logged in"}
    except Exception as e:
        logger.warning(f"Error checking kiro auth: {e}")
        return {"authenticated": False, "info": str(e)}

async def run_kiro_stream(
    prompt: str,
    model: str | None = None,
    agent: str | None = None,
    timeout_seconds: float = 60.0
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Run kiro-cli chat with stream-json output format.
    Safely detects expired/missing authentication and raises HTTP 401.
    """
    agent_name = agent or settings.KIRO_AGENT
    cmd = [
        settings.KIRO_CLI_PATH,
        "chat",
        "--agent", agent_name,
        "--output-format", "stream-json"
    ]
    if model and model != "auto":
        cmd.extend(["--model", model])

    logger.debug(f"Executing kiro command: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        logger.error(f"Kiro CLI binary not found at '{settings.KIRO_CLI_PATH}'")
        raise HTTPException(
            status_code=500,
            detail=f"Kiro CLI binary not found at '{settings.KIRO_CLI_PATH}'. Please ensure kiro-cli is installed."
        )

    # Send prompt via stdin and close stdin
    if process.stdin:
        process.stdin.write(prompt.encode("utf-8"))
        try:
            await process.stdin.drain()
        except Exception as e:
            logger.warning(f"Error draining stdin: {e}")
        process.stdin.close()
        try:
            await process.stdin.wait_closed()
        except Exception:
            pass

    accumulated_text = ""
    had_output = False
    stop_reason = "stop"
    stderr_captured: list[str] = []

    async def read_stdout():
        nonlocal had_output, accumulated_text, stop_reason
        if not process.stdout:
            return

        while True:
            line_bytes = await process.stdout.readline()
            if not line_bytes:
                break

            line_str = line_bytes.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            # Check if stdout contains an interactive sign-in prompt
            line_lower = line_str.lower()
            if any(pattern in line_lower for pattern in AUTH_ERROR_PATTERNS):
                try:
                    process.terminate()
                except Exception:
                    pass
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": {
                            "message": "Kiro CLI is signed out or session expired. Please re-authenticate using: kiro-cli login --use-device-flow",
                            "type": "authentication_error",
                            "code": "session_expired"
                        }
                    }
                )

            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                logger.debug(f"Non-JSON line from kiro-cli: {line_str}")
                continue

            event_type = event.get("type")
            data = event.get("data", {})

            if event_type == "sessionUpdate":
                update = data.get("update", {})
                if update.get("sessionUpdate") == "agent_message_chunk":
                    chunk_text = update.get("content", {}).get("text", "")
                    if chunk_text:
                        had_output = True
                        accumulated_text += chunk_text
                        yield {"type": "chunk", "text": chunk_text}

            elif event_type == "runFinished":
                final_text = data.get("finalText") or accumulated_text
                kiro_stop = data.get("stopReason") or "end_turn"
                stop_reason = "stop" if kiro_stop in ("end_turn", "complete", "stop") else kiro_stop
                yield {
                    "type": "done",
                    "text": final_text,
                    "stop_reason": stop_reason
                }

    try:
        # Wrap reading with timeout to prevent hanging on interactive prompt
        async for item in read_stdout():
            yield item
    except asyncio.TimeoutError:
        try:
            process.terminate()
        except Exception:
            pass
        raise HTTPException(
            status_code=504,
            detail="Timeout waiting for Kiro CLI response."
        )

    returncode = await process.wait()

    if returncode != 0 and not had_output:
        stderr_bytes = await process.stderr.read() if process.stderr else b""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        logger.error(f"kiro-cli exited with code {returncode}: {stderr_text}")

        stderr_lower = stderr_text.lower()
        if any(pat in stderr_lower for pat in AUTH_ERROR_PATTERNS):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "Kiro CLI session expired or not logged in. Run 'kiro-cli login --use-device-flow' to sign in.",
                        "type": "authentication_error",
                        "code": "session_expired",
                        "raw": stderr_text
                    }
                }
            )

        raise HTTPException(
            status_code=502,
            detail=f"Kiro CLI process failed (exit code {returncode}): {stderr_text}"
        )

async def run_kiro_complete(
    prompt: str,
    model: str | None = None,
    agent: str | None = None
) -> tuple[str, str]:
    """
    Execute kiro-cli and wait for the complete response.
    Returns (final_text, stop_reason).
    """
    final_text = ""
    stop_reason = "stop"

    async for event in run_kiro_stream(prompt, model=model, agent=agent):
        if event["type"] == "chunk":
            final_text += event["text"]
        elif event["type"] == "done":
            if event.get("text"):
                final_text = event["text"]
            stop_reason = event.get("stop_reason", "stop")

    return final_text, stop_reason
