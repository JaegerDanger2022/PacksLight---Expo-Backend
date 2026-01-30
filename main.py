import os
import json
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from api.users import router as users_router
from api.dreams import router as dreams_router
from api.milestone import router as milestone_router
from api.victories import router as victories_router
from api.community import router as community_router
from api.journey_recap import router as journey_recap_router
from core.database import connect_db, close_db

load_dotenv()

logger = logging.getLogger(__name__)

# Configure logging to show debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress verbose pymongo debug logs
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)
logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
logging.getLogger("pymongo.command").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("Starting up Dream-to-Do API...")
    logger.info("=" * 60)
    try:
        await connect_db()
        logger.info("[STARTUP] Database connection completed")
    except Exception as e:
        logger.error(f"[STARTUP] Database connection failed: {e}", exc_info=True)
        raise
    yield
    # Shutdown
    logger.info("Shutting down...")
    await close_db()


app = FastAPI(
    title="Dream-to-Do API",
    description="User data and profile API for Dream-to-Do",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", '["http://localhost:3000","http://localhost:8081","http://localhost:19000"]')
if isinstance(allowed_origins, str):
    try:
        allowed_origins = json.loads(allowed_origins)
    except:
        allowed_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(dreams_router, prefix="/api/dreams", tags=["dreams"])
app.include_router(milestone_router, prefix="/api/milestone", tags=["milestone"])
app.include_router(victories_router, prefix="/api/victories", tags=["victories"])
app.include_router(community_router, prefix="/api", tags=["community"])
app.include_router(journey_recap_router, prefix="/api/journey-recaps", tags=["journey-recap"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "dream-to-do-api"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
