"""
Dreams API endpoints - Create and manage dreams in MongoDB
"""

import logging
import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
import httpx

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
    assistant_id: str = Field(..., description="LangGraph assistant ID")
    research_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Research data related to the dream")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Message history")
    roadmap: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dream roadmap/plan")
    tracks: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Dream tracks/milestones")
    status: Optional[str] = Field(default="", description="Current status of the dream")


@router.post("/create", status_code=201, tags=["dreams"])
async def create_dream(dream_data: CreateDreamRequest):
    """
    Send dream to langgraph agent for processing.

    Args:
        dream_data: Dream information including user request and profile

    Returns:
        dict: Dream with generated thread_id

    Raises:
        500: Langgraph agent error
    """
    try:
        logger.info(f"Processing dream for user: {dream_data.user_id}")

        # Generate thread_id for langgraph
        thread_id = str(uuid.uuid4())
        logger.info(f"Generated thread_id: {thread_id}")

        # Send to langgraph agent
        langgraph_url = os.getenv("LANGGRAPH_AGENT_URL", "https://ht-healthy-icicle-70-9182269482ef54bcb331b5ec631f931e.us.langgraph.app")
        if not langgraph_url:
            logger.error("LANGGRAPH_AGENT_URL environment variable not set")
            raise HTTPException(
                status_code=500,
                detail="LANGGRAPH_AGENT_URL not configured"
            )

        try:
            agent_endpoint = f"{langgraph_url}/threads/{thread_id}/runs/wait"
            logger.info(f"Posting dream to langgraph agent: {agent_endpoint}")

            # Get API key from environment
            api_key = os.getenv("LANGGRAPH_API_KEY")
            if not api_key:
                logger.error("LANGGRAPH_API_KEY environment variable not set")
                raise HTTPException(
                    status_code=500,
                    detail="LANGGRAPH_API_KEY not configured"
                )

            # Build headers - API key can be passed in multiple ways
            headers = {}
            if api_key:
                headers["x-api-key"] = api_key

            logger.info(f"Request headers: {list(headers.keys())}")
            logger.info(f"Request body keys: {list(dream_data.model_dump().keys())}")

            async with httpx.AsyncClient() as client:
                logger.info(f"Sending POST request to {agent_endpoint}")
                response = await client.post(
                    agent_endpoint,
                    json=dream_data.model_dump(),
                    headers=headers,
                    timeout=30.0
                )
                logger.info(f"Response status code: {response.status_code}")
                response.raise_for_status()
                agent_response = response.json()
                logger.info(f"Agent response received, keys: {list(agent_response.keys()) if isinstance(agent_response, dict) else 'not a dict'}")

            logger.info(f"Successfully posted dream to langgraph agent for thread: {thread_id}")
            return agent_response
        except httpx.HTTPError as e:
            logger.error(f"HTTP Error posting to langgraph agent: {type(e).__name__}: {e}", exc_info=True)
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                try:
                    logger.error(f"Response body: {e.response.text}")
                except:
                    pass
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send dream to agent: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error posting to langgraph agent: {type(e).__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send dream to agent: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing dream for user {dream_data.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing dream"
        )
