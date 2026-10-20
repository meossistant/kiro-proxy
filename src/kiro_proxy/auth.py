from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from kiro_proxy.config import settings

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def verify_api_key(
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    header_key: str | None = Security(api_key_header)
) -> bool:
    """
    Verify API key if configured in settings.API_KEY.
    Allows either Bearer token or x-api-key header.
    """
    expected_key = settings.API_KEY
    if not expected_key:
        return True

    provided_key = None
    if bearer and bearer.credentials:
        provided_key = bearer.credentials
    elif header_key:
        provided_key = header_key

    if not provided_key or provided_key.strip() != expected_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return True
