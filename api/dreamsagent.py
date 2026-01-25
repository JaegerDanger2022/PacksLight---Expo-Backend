"""
Dreams API endpoints - Create and manage dreams in MongoDB
"""

import logging
import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import httpx
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class UserTraits(BaseModel):
    """User personality and work style traits"""
    work_style: Optional[str] = Field(None, description="How the user prefers to work")
    completion_style: Optional[str] = Field(None, description="User's completion style")


class UserPreferences(BaseModel):
    """User preferences and settings"""
    preferred_time: Optional[str] = Field(None, description="User's preferred time of day")


class UserProfile(BaseModel):
    """User profile information"""
    traits: Optional[UserTraits] = Field(default_factory=UserTraits, description="User traits")
    preferences: Optional[UserPreferences] = Field(default_factory=UserPreferences, description="User preferences")


class CreateDreamRequest(BaseModel):
    """Request schema for creating a new dream"""
    user_id: str = Field(..., description="Unique user identifier")
    user_request: str = Field(..., description="The dream or goal the user wants to achieve")
    user_profile: UserProfile = Field(..., description="User profile with traits and preferences")
    research_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Research data related to the dream")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Message history")
    roadmap: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dream roadmap/plan")
    tracks: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Dream tracks/milestones")
    status: Optional[str] = Field(default="", description="Current status of the dream")


@router.post("/create", status_code=201, tags=["dreams"])
async def create_dream(dream_data: CreateDreamRequest):
    """
    Create a new dream in the dreams collection and send to langgraph agent.

    Args:
        dream_data: Dream information including user request and profile

    Returns:
        dict: Created dream document with _id, thread_id, and created_at

    Raises:
        500: Database or langgraph agent error
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        logger.info(f"Creating dream for user: {dream_data.user_id}")

        # Generate thread_id for langgraph
        thread_id = str(uuid.uuid4())

        # Create dream document
        dream_doc = {
            "user_id": dream_data.user_id,
            "user_request": dream_data.user_request,
            "user_profile": dream_data.user_profile.model_dump(),
            "research_data": dream_data.research_data,
            "messages": dream_data.messages,
            "roadmap": dream_data.roadmap,
            "tracks": dream_data.tracks,
            "status": dream_data.status,
            "thread_id": thread_id,
            "created_at": datetime.now(timezone.utc)
        }

        # Insert into database
        result = await db.dreams.insert_one(dream_doc)

        # Get the created document
        created_dream = await db.dreams.find_one({"_id": result.inserted_id})

        # Convert ObjectId to string for JSON serialization
        if "_id" in created_dream:
            created_dream["_id"] = str(created_dream["_id"])
        if "created_at" in created_dream:
            created_dream["created_at"] = created_dream["created_at"].isoformat()

        logger.info(f"Successfully created dream for user: {dream_data.user_id} with thread_id: {thread_id}")

        # Send to langgraph agent
        langgraph_url = os.getenv("LANGGRAPH_AGENT_URL")
        if langgraph_url:
            try:
                agent_endpoint = f"{langgraph_url}/threads/{thread_id}/runs/wait"
                logger.info(f"Posting dream to langgraph agent: {agent_endpoint}")

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        agent_endpoint,
                        json=dream_data.model_dump(),
                        timeout=30.0
                    )
                    response.raise_for_status()

                logger.info(f"Successfully posted dream to langgraph agent for thread: {thread_id}")
            except Exception as e:
                logger.error(f"Error posting to langgraph agent: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Dream created but failed to send to agent: {str(e)}"
                )
        else:
            logger.warning("LANGGRAPH_AGENT_URL not set, skipping agent notification")

        return created_dream

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating dream for user {dream_data.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating dream"
        )
