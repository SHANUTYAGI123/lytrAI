import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import (
    check_db_health,
    get_session_messages,
    init_db,
    session_exists,
)
from app.gateway import handle_chat_request, is_cache_active
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MessageMetadata,
    SessionHistoryResponse,
    SessionMessageItem,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lyftr.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite directory & tables exist
    logger.info("Initializing database...")
    await init_db()
    logger.info(f"Database initialized. Key pool count: {len(settings.get_api_keys())}")
    yield
    logger.info("Application shutting down...")


app = FastAPI(
    title="Lyftr AI Chatbot Gateway",
    description="LLM Chatbot with Key Failover and Response Caching",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
origins = settings.get_allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


from fastapi.encoders import jsonable_encoder

# Exception handler for Request Validation Errors (FastAPI default shape is fine)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())}
    )


# Exception handler to ensure NO unhandled exception returns an HTML error page or stack trace
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal server error"}
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Returns 200 once the app is running, the database is reachable and the key pool is loaded.
    { "status": "ok", "keys_configured": 2, "cache_enabled": true }
    """
    db_ok = await check_db_health()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unreachable"
        )

    keys = settings.get_api_keys()
    cache_enabled = is_cache_active()

    return HealthResponse(
        status="ok",
        keys_configured=len(keys),
        cache_enabled=cache_enabled
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    x_simulate_failure: Optional[str] = Header(None, alias="X-Simulate-Failure")
):
    """
    Handles chat message with response caching and key failover.
    """
    return await handle_chat_request(
        session_id=req.session_id,
        user_message=req.message,
        system_prompt=req.system_prompt,
        simulate_failure_header=x_simulate_failure
    )


@app.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str):
    """
    Returns the stored history of one session from SQLite, oldest first, without the system prompt.
    If session is unknown, returns 404 {"detail": "session not found"}.
    """
    exists = await session_exists(session_id)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found"
        )

    records = await get_session_messages(session_id)
    message_items = []
    for rec in records:
        meta_obj = None
        if rec["metadata"] and isinstance(rec["metadata"], dict):
            try:
                meta_obj = MessageMetadata(
                    resolution_source=rec["metadata"].get("resolution_source", "LIVE_INFERENCE"),
                    input_tokens=rec["metadata"].get("input_tokens", 0),
                    output_tokens=rec["metadata"].get("output_tokens", 0)
                )
            except Exception:
                meta_obj = None

        message_items.append(
            SessionMessageItem(
                role=rec["role"],
                content=rec["content"],
                metadata=meta_obj
            )
        )

    return SessionHistoryResponse(
        session_id=session_id,
        messages=message_items
    )
