from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None

async def connect_db():
    global client, db
    try:
        mongodb_url = os.getenv("MONGODB_URL")
        db_name = os.getenv("MONGODB_DB_NAME", "dream_to_do")
        if not mongodb_url:
            raise ValueError("MONGODB_URL environment variable is not set")
        logger.info(f"[DB] MongoDB URL: {mongodb_url[:50]}...")
        logger.info(f"[DB] Database name: {db_name}")

        logger.info("[DB] Creating AsyncIOMotorClient...")
        client = AsyncIOMotorClient(mongodb_url)
        logger.info("[DB] AsyncIOMotorClient created")

        logger.info("[DB] Getting database reference...")
        db = client[db_name]
        logger.info("[DB] Database reference obtained")

        logger.info("[DB] Pinging MongoDB...")
        await client.admin.command("ping")
        logger.info("[DB] Successfully connected to MongoDB!")

        logger.info("[DB] Creating indexes...")
        await create_indexes()
        logger.info("[DB] Indexes created successfully")
    except Exception as e:
        logger.error(f"[DB] Failed to connect to MongoDB: {e}", exc_info=True)
        raise

async def close_db():
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")

async def create_indexes():
    """Create necessary database indexes"""
    if db is None:
        raise RuntimeError("Database not connected")

    try:
        # Users collection
        logger.info("[DB] Creating index: users.email (unique)")
        await db.users.create_index("email", unique=True)
        logger.info("[DB] Index created: users.email")

        logger.info("[DB] Creating index: users.created_at")
        await db.users.create_index("created_at")
        logger.info("[DB] Index created: users.created_at")

        # Roadmaps collection
        logger.info("[DB] Creating index: roadmaps.user_id")
        await db.roadmaps.create_index("user_id")
        logger.info("[DB] Index created: roadmaps.user_id")

        logger.info("[DB] Creating index: roadmaps (user_id, created_at)")
        await db.roadmaps.create_index([("user_id", 1), ("created_at", -1)])
        logger.info("[DB] Index created: roadmaps (user_id, created_at)")

        # Challenges collection
        logger.info("[DB] Creating index: challenges.user_id")
        await db.challenges.create_index("user_id")
        logger.info("[DB] Index created: challenges.user_id")

        logger.info("[DB] Creating index: challenges (user_id, roadmap_id)")
        await db.challenges.create_index([("user_id", 1), ("roadmap_id", 1)])
        logger.info("[DB] Index created: challenges (user_id, roadmap_id)")

        logger.info("[DB] Creating index: challenges.completed_at (sparse)")
        await db.challenges.create_index("completed_at", sparse=True)
        logger.info("[DB] Index created: challenges.completed_at")

        # Streaks collection
        logger.info("[DB] Creating index: streaks.user_id (unique)")
        await db.streaks.create_index("user_id", unique=True)
        logger.info("[DB] Index created: streaks.user_id")

        logger.info("[DB] All database indexes created successfully")
    except Exception as e:
        logger.error(f"[DB] Failed to create indexes: {e}", exc_info=True)
        raise

def get_db():
    return db
