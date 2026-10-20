import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kiro_proxy.config import settings
from kiro_proxy.agent_setup import ensure_custom_agent
from kiro_proxy.routes_openai import router as openai_router
from kiro_proxy.routes_anthropic import router as anthropic_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("kiro-proxy")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure custom agent is ready in ~/.kiro/agents/
    logger.info("Initializing Kiro Proxy Server...")
    agent_path = ensure_custom_agent(settings.KIRO_AGENT)
    logger.info(f"Custom agent '{settings.KIRO_AGENT}' confirmed at {agent_path}")
    logger.info(f"Kiro CLI binary path: {settings.KIRO_CLI_PATH}")
    yield
    logger.info("Shutting down Kiro Proxy Server...")

app = FastAPI(
    title="Kiro Proxy Server",
    description="OpenAI & Anthropic Compatible Proxy Server for AWS Kiro AI CLI",
    version="0.1.0",
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

# Mount API Routers
app.include_router(openai_router, tags=["OpenAI Compatible"])
app.include_router(anthropic_router, tags=["Anthropic Compatible"])

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "kiro-proxy",
        "version": "0.1.0",
        "kiro_agent": settings.KIRO_AGENT,
        "default_model": settings.DEFAULT_MODEL,
        "endpoints": {
            "openai_chat": "/v1/chat/completions",
            "openai_models": "/v1/models",
            "anthropic_messages": "/v1/messages"
        }
    }

def start():
    """CLI entrypoint for running the proxy server."""
    logger.info(f"Starting server on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("kiro_proxy.main:app", host=settings.HOST, port=settings.PORT, reload=False)

if __name__ == "__main__":
    start()
