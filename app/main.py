from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import logging

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Set up logging
from .logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# Create limiter
limiter = Limiter(key_func=get_remote_address)

load_dotenv()

app = FastAPI(
    title="Nebulyze API",
    description="High-performance media conversion platform",
    version="1.0.0"
)

# Add rate limiting exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from .db.database import init_db

@app.on_event("startup")
async def on_startup():
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Warning: Database initialization timed out or failed: {e}")
        logger.warning("API will continue to start without immediate DB sync.")

# CORS for Next.js frontend - restrict origins in production
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if os.getenv("ENVIRONMENT") == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    return {"status": "Nebulyze Engine Online", "version": "1.0.0"}

# Include routers
from .api.endpoints import router
app.include_router(router, prefix="/api/v1")
