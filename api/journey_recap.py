"""
Journey Recap API endpoints - Share completed dream journeys
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateJourneyRecapRequest(BaseModel):
    """Request schema for creating a journey recap"""
    dreamId: str = Field(..., description="Thread ID of the completed dream")
    journeyStory: str = Field(..., min_length=10, max_length=500, description="User's reflection on the journey")
    keyMoment: str | None = Field(None, max_length=200, description="Most memorable moment (optional)")
    isAnonymous: bool = Field(False, description="Whether to share anonymously")


@router.post("", status_code=201, tags=["journey-recap"])
async def create_journey_recap(
    journey_data: CreateJourneyRecapRequest,
    user_id: str = Query(..., description="ID of the user creating the journey recap")
):
    """
    Create a journey recap for a completed dream.

    Args:
        journey_data: Journey recap details (story, key moment, etc.)
        user_id: The user ID (passed as query param)

    Returns:
        dict: Created journey recap with ID and courage points awarded

    Raises:
        400: Invalid data or dream not complete
        404: Dream not found
        409: Journey recap already exists for this dream
        500: Database error
    """
    try:
        db = get_db()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection not available")

        logger.info(f"Creating journey recap for dream {journey_data.dreamId} by user {user_id}")

        # 1. Verify user and dream exist
        user_doc = await db.users.find_one(
            {"user_id": user_id, "dreams.thread_id": journey_data.dreamId}
        )

        if not user_doc:
            raise HTTPException(status_code=404, detail="User or dream not found")

        # 2. Find the dream
        dream = next(
            (d for d in user_doc.get("dreams", []) if d.get("thread_id") == journey_data.dreamId),
            None
        )

        if not dream:
            raise HTTPException(status_code=404, detail="Dream not found")

        # 3. Verify dream is completed
        if not dream.get("isComplete", False):
            raise HTTPException(
                status_code=400,
                detail="Cannot create journey recap for incomplete dream"
            )

        # 4. Check if journey recap already exists
        existing_recap = await db.journey_recaps.find_one({
            "userId": user_id,
            "dreamId": journey_data.dreamId
        })

        if existing_recap:
            raise HTTPException(
                status_code=409,
                detail="Journey recap already exists for this dream"
            )

        # 5. Calculate journey stats
        milestones = dream.get("roadmap", {}).get("milestones", [])
        total_milestones = len(milestones)

        # Get completion dates
        completed_dates = [
            m.get("completedDate")
            for m in milestones
            if m.get("completedDate") is not None
        ]

        dream_start_date = min(completed_dates) if completed_dates else None
        dream_completed_date = dream.get("completed_at")

        # Calculate duration
        duration_days = 0
        if dream_start_date and dream_completed_date:
            start = datetime.fromisoformat(dream_start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(dream_completed_date.replace('Z', '+00:00'))
            duration_days = max(0, (end - start).days)

        # 6. Get user profile info
        user_display_name = "Anonymous"
        user_location = None
        user_age = None

        if not journey_data.isAnonymous:
            user_display_name = user_doc.get("firstname", "User")
            community_profile = user_doc.get("communityProfile", {})
            user_location = community_profile.get("location")
            user_age = community_profile.get("age")

        # 7. Create journey recap document
        journey_recap = {
            "userId": user_id,
            "userDisplayName": user_display_name,
            "userLocation": user_location,
            "userAge": user_age,
            "dreamId": journey_data.dreamId,
            "dreamTitle": dream.get("dream", ""),
            "dreamCategory": dream.get("category", "achievement_goals"),
            "journeyStory": journey_data.journeyStory,
            "totalMilestones": total_milestones,
            "durationDays": duration_days,
            "keyMoment": journey_data.keyMoment,
            "completedDate": dream_completed_date or datetime.now(timezone.utc).isoformat(),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "courageBoosts": 0,
            "permissionsCount": 0,
            "meTooCount": 0,
            "isAnonymous": journey_data.isAnonymous
        }

        # 8. Insert into database
        result = await db.journey_recaps.insert_one(journey_recap)
        journey_recap_id = str(result.inserted_id)

        # 9. Award courage points (+10 for journey vs +5 for victory)
        courage_points_awarded = 10
        await db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"couragePoints": courage_points_awarded}}
        )

        logger.info(f"Journey recap created: {journey_recap_id}, awarded {courage_points_awarded} courage points")

        return {
            "success": True,
            "journeyRecapId": journey_recap_id,
            "couragePointsAwarded": courage_points_awarded
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating journey recap: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create journey recap: {str(e)}")
