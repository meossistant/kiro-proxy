import time
import hashlib
import json
import logging
from typing import Any
from dataclasses import dataclass, field

logger = logging.getLogger("kiro-proxy.sessions")

@dataclass
class ConversationSession:
    kiro_session_id: str
    client_key: str
    message_count: int
    model: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

class SessionManager:
    """
    Manages client conversation continuity and maps client sessions to Kiro CLI sessions.
    Allows reusing existing kiro-cli conversations via '--resume-id' to take advantage
    of prompt token caching and avoid re-transmitting entire conversation histories.
    """

    def __init__(self, ttl_seconds: float = 7200.0, max_sessions: int = 1000):
        self.ttl = ttl_seconds
        self.max_sessions = max_sessions
        # Primary map: client_key -> ConversationSession
        self._sessions: dict[str, ConversationSession] = {}
        # Reverse map: kiro_session_id -> client_key
        self._kiro_to_key: dict[str, str] = {}

    def extract_client_key(
        self,
        headers: dict[str, str],
        body_user: str | None = None,
        body_metadata: dict[str, Any] | None = None,
        messages: list[Any] | None = None,
        system: Any = None
    ) -> str:
        """
        Extract or derive a consistent client key for the conversation.
        Priority:
        1. 'x-claude-code-session-id' (Claude Code CLI)
        2. 'x-session-id' or 'x-conversation-id' (Custom HTTP headers)
        3. metadata.session_id or metadata.conversation_id (Anthropic API)
        4. user field (OpenAI API)
        5. Stable hash of the first user message + system (Automatic fallback)
        """
        # 1. Header checks (case-insensitive)
        headers_lower = {k.lower(): v for k, v in headers.items()}
        for header_name in [
            "x-claude-code-session-id",
            "x-session-id",
            "x-conversation-id"
        ]:
            val = headers_lower.get(header_name)
            if val and val.strip():
                return f"hdr:{val.strip()}"

        # 2. Metadata checks
        if body_metadata and isinstance(body_metadata, dict):
            for key in ["session_id", "conversation_id"]:
                val = body_metadata.get(key)
                if val and str(val).strip():
                    return f"meta:{str(val).strip()}"

        # 3. OpenAI 'user' field
        if body_user and body_user.strip():
            return f"user:{body_user.strip()}"

        # 4. Content prefix hash fallback
        if messages and len(messages) > 0:
            first_msg = messages[0]
            first_content = ""
            if hasattr(first_msg, "content"):
                first_content = str(first_msg.content)
            elif isinstance(first_msg, dict):
                first_content = str(first_msg.get("content", ""))

            sys_str = str(system or "")
            prefix_data = f"{first_content[:500]}:{sys_str[:500]}"
            h = hashlib.sha256(prefix_data.encode("utf-8")).hexdigest()[:16]
            return f"hash:{h}"

        return "default"

    def prepare_turn(
        self,
        client_key: str,
        messages: list[Any],
        model: str
    ) -> tuple[str | None, list[Any], bool]:
        """
        Check if an active session exists for client_key.
        Returns:
            (resume_id, messages_to_send, is_continuation)
        """
        self._cleanup_expired()

        if client_key not in self._sessions:
            return None, messages, False

        session = self._sessions[client_key]
        now = time.time()

        # Check expiration
        if (now - session.updated_at) > self.ttl:
            logger.info(f"Session '{client_key}' expired (inactive for {now - session.updated_at:.0f}s). Starting fresh.")
            self.invalidate_session(client_key=client_key)
            return None, messages, False

        curr_len = len(messages)
        prev_len = session.message_count

        # If incoming message count is greater than previously recorded, we can resume!
        if curr_len > prev_len:
            messages_to_send = messages[prev_len:]
            logger.info(
                f"Resuming Kiro session '{session.kiro_session_id}' for client '{client_key}'. "
                f"Sending delta of {len(messages_to_send)} message(s) (total: {curr_len}, previous: {prev_len})."
            )
            return session.kiro_session_id, messages_to_send, True

        # If curr_len <= prev_len, user may have edited previous prompt or restarted conversation.
        # Fall back to starting fresh.
        logger.info(f"Message count changed non-linearly ({prev_len} -> {curr_len}) for '{client_key}'. Resetting session.")
        self.invalidate_session(client_key=client_key)
        return None, messages, False

    def record_session(
        self,
        client_key: str,
        kiro_session_id: str,
        message_count: int,
        model: str
    ) -> None:
        """
        Record or update an active session.
        """
        now = time.time()
        session = ConversationSession(
            kiro_session_id=kiro_session_id,
            client_key=client_key,
            message_count=message_count,
            model=model,
            created_at=self._sessions.get(client_key, None).created_at if client_key in self._sessions else now,
            updated_at=now
        )
        self._sessions[client_key] = session
        self._kiro_to_key[kiro_session_id] = client_key
        logger.debug(f"Saved session state: client='{client_key}' -> kiro='{kiro_session_id}' (messages={message_count})")

    def invalidate_session(
        self,
        client_key: str | None = None,
        kiro_session_id: str | None = None
    ) -> None:
        """
        Invalidate and remove a session from cache.
        """
        if kiro_session_id and kiro_session_id in self._kiro_to_key:
            client_key = self._kiro_to_key.pop(kiro_session_id, None)

        if client_key and client_key in self._sessions:
            s = self._sessions.pop(client_key, None)
            if s and s.kiro_session_id in self._kiro_to_key:
                self._kiro_to_key.pop(s.kiro_session_id, None)
            logger.info(f"Invalidated session for client '{client_key}'")

    def get_stats(self) -> dict[str, Any]:
        """Return diagnostic statistics on active sessions."""
        self._cleanup_expired()
        return {
            "active_sessions_count": len(self._sessions),
            "sessions": [
                {
                    "client_key": s.client_key,
                    "kiro_session_id": s.kiro_session_id,
                    "message_count": s.message_count,
                    "model": s.model,
                    "idle_seconds": int(time.time() - s.updated_at)
                }
                for s in list(self._sessions.values())[:20]
            ]
        }

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired_keys = [
            k for k, s in self._sessions.items()
            if (now - s.updated_at) > self.ttl
        ]
        for k in expired_keys:
            self.invalidate_session(client_key=k)

session_manager = SessionManager()
