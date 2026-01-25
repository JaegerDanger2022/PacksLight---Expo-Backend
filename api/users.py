"""
Users API endpoints - Retrieve user data from MongoDB
"""

import logging
from fastapi import APIRouter, HTTPException
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{user_id}", tags=["users"])
async def get_user(user_id: str):
    """
    Get a user by user_id from the users collection.

    Args:
        user_id: The user's unique identifier (string)

    Returns:
        dict: The complete user document

    Raises:
        404: User not found
        500: Database error
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        logger.info(f"Fetching user: {user_id}")

        # Query the users collection by user_id field
        user = await db.users.find_one({"user_id": user_id})

        if user is None:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=404,
                detail=f"User with id '{user_id}' not found"
            )

        # Convert ObjectId to string for JSON serialization
        if "_id" in user:
            user["_id"] = str(user["_id"])

        logger.info(f"Successfully retrieved user: {user_id}")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching user"
        )
