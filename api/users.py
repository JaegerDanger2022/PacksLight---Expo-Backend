"""
Users API endpoints - Retrieve and create user data from MongoDB
"""

import logging
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateUserRequest(BaseModel):
    """Request schema for creating a new user"""
    user_id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    firstname: str = Field(..., description="User first name")
    lastname: str = Field(..., description="User last name")


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

        # Convert image bytes to base64 for JSON serialization and frontend consumption
        if "dreams" in user and isinstance(user["dreams"], list):
            for dream in user["dreams"]:
                if isinstance(dream, dict) and "dream_image_bytes" in dream:
                    image_bytes = dream["dream_image_bytes"]
                    if isinstance(image_bytes, bytes):
                        # Convert binary bytes to base64 string
                        dream["dream_image_bytes"] = base64.b64encode(image_bytes).decode('utf-8')

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


@router.post("/register", status_code=201, tags=["users"])
async def register_user(user_data: CreateUserRequest):
    """
    Create a new user in the users collection.

    Args:
        user_data: User information (user_id, email, firstname, lastname)

    Returns:
        dict: Created user document with _id and created_at

    Raises:
        400: Invalid input or user_id already exists
        500: Database error
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        logger.info(f"Creating user: {user_data.user_id}")

        # Check if user already exists
        existing_user = await db.users.find_one({"user_id": user_data.user_id})
        if existing_user:
            logger.warning(f"User already exists: {user_data.user_id}")
            raise HTTPException(
                status_code=400,
                detail=f"User with id '{user_data.user_id}' already exists"
            )

        # Create user document
        user_doc = {
            "user_id": user_data.user_id,
            "email": user_data.email,
            "firstname": user_data.firstname,
            "lastname": user_data.lastname,
            "created_at": datetime.now(timezone.utc)
        }

        # Insert into database
        result = await db.users.insert_one(user_doc)

        # Get the created document
        created_user = await db.users.find_one({"_id": result.inserted_id})

        # Convert ObjectId to string for JSON serialization
        if "_id" in created_user:
            created_user["_id"] = str(created_user["_id"])
        if "created_at" in created_user:
            created_user["created_at"] = created_user["created_at"].isoformat()

        logger.info(f"Successfully created user: {user_data.user_id}")
        return created_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user {user_data.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating user"
        )
