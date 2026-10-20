import json
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kiro_proxy.config import settings
from kiro_proxy.agent_setup import ensure_custom_agent
from kiro_proxy.registry import registry
from kiro_proxy.kiro_runner import check_kiro_auth
from kiro_proxy.routes_openai import router as openai_router
from kiro_proxy.routes_anthropic import router as anthropic_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("kiro-proxy")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Kiro Proxy Server...")
    # 1. Ensure custom generic agent exists
    agent_path = ensure_custom_agent(settings.KIRO_AGENT)
    logger.info(f"Custom agent '{settings.KIRO_AGENT}' confirmed at {agent_path}")

    # 2. Preload and log active models from kiro-cli
    models = await registry.get_available_models()
    model_ids = [m["model_id"] for m in models]
    logger.info(f"Kiro CLI active models ({len(model_ids)}): {', '.join(model_ids)}")
    logger.info(f"Kiro CLI binary path: {settings.KIRO_CLI_PATH}")
    yield
    logger.info("Shutting down Kiro Proxy Server...")

app = FastAPI(
    title="Kiro Proxy Server",
    description="OpenAI & Anthropic Compatible Proxy Server for AWS Kiro AI CLI with Dynamic Model Auto-Routing",
    version="0.2.0",
    lifespan=lifespan
)

# Enable CORS for all origins by default for local dev and tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from kiro_proxy.sessions import session_manager

# Mount API Routers
app.include_router(openai_router, tags=["OpenAI Compatible"])
app.include_router(anthropic_router, tags=["Anthropic Compatible"])

@app.get("/")
@app.get("/health")
async def health_check():
    active_models = await registry.get_available_models()
    auth_status = await check_kiro_auth()
    return {
        "status": "healthy" if auth_status["authenticated"] else "unauthenticated",
        "service": "kiro-proxy",
        "version": "0.3.0",
        "kiro_auth": auth_status,
        "kiro_agent": settings.KIRO_AGENT,
        "default_model_openai": await registry.resolve_model(None, api_flavor="openai"),
        "default_model_anthropic": await registry.resolve_model(None, api_flavor="anthropic"),
        "available_models_count": len(active_models),
        "available_models": [m["model_id"] for m in active_models],
        "sessions": session_manager.get_stats(),
        "endpoints": {
            "openai_chat": "/v1/chat/completions",
            "openai_models": "/v1/models",
            "anthropic_messages": "/v1/messages",
            "sessions": "/v1/sessions"
        }
    }

@app.get("/v1/sessions")
@app.get("/sessions")
async def list_sessions():
    """Diagnostic endpoint to inspect active resumed conversations and token savings."""
    return session_manager.get_stats()

@app.api_route("/api/hello", methods=["GET", "HEAD"])
async def api_hello():
    """Endpoint probed by Claude Code and other CLI tools for health/connectivity."""
    return {"status": "ok"}



def start():
    """CLI entrypoint for running the proxy server."""
    logger.info(f"Starting server on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("kiro_proxy.main:app", host=settings.HOST, port=settings.PORT, reload=False)

if __name__ == "__main__":
    start()
