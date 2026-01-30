"""
Milestone API endpoints - Update and manage milestones in roadmaps
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateMilestoneRequest(BaseModel):
    """Request schema for updating a milestone"""
    status: str = Field(..., description="New status for the milestone (e.g., 'completed', 'pending', 'in_progress')")
    evidence: str | None = Field(None, max_length=200, description="Evidence/proof text, max 200 characters")
    impact: str | None = Field(None, description="Impact level - 'critical', 'high', 'medium', or 'low'")


@router.put("/update-status/{user_id}/{thread_id}/{milestone_id}", status_code=200, tags=["milestone"])
async def update_milestone_status(
    user_id: str,
    thread_id: str,
    milestone_id: str,
    update_data: UpdateMilestoneRequest
):
    """
    Update a milestone's status in a dream.

    Args:
        user_id: The user ID who owns the dream
        thread_id: The thread ID of the dream containing the milestone
        milestone_id: The ID of the milestone to update
        update_data: Request body containing the new status

    Returns:
        dict: Updated milestone data with the new status

    Raises:
        404: User, dream, or milestone not found
        500: Database error
    """
    try:
        db = get_db()
        if db is None:
            logger.error("Database connection not available")
            raise HTTPException(
                status_code=500,
                detail="Database connection not available"
            )

        logger.info(f"Updating milestone {milestone_id} in dream {thread_id} for user {user_id} to status: {update_data.status}")

        # First verify the document exists
        verify_doc = await db.users.find_one(
            {
                "user_id": user_id,
                "dreams.thread_id": thread_id
            }
        )

        if not verify_doc:
            logger.warning(f"User {user_id} with dream {thread_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"User or dream not found"
            )

        # Verify milestone exists in the dream
        milestone_found = False
        for dream in verify_doc.get("dreams", []):
            if dream.get("thread_id") == thread_id:
                for milestone in dream.get("roadmap", {}).get("milestones", []):
                    if milestone.get("id") == milestone_id:
                        milestone_found = True
                        break
                break

        if not milestone_found:
            logger.warning(f"Milestone {milestone_id} not found in dream {thread_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Milestone not found"
            )

        logger.info(f"Found user, dream, and milestone. Proceeding with update.")

        # Check if roadmap status is "started", if not set it
        for dream in verify_doc.get("dreams", []):
            if dream.get("thread_id") == thread_id:
                roadmap_status = dream.get("roadmap", {}).get("status")
                if roadmap_status != "started":
                    logger.info(f"Roadmap status is '{roadmap_status}', setting to 'started'")
                    # Update roadmap status to "started"
                    await db.users.update_one(
                        {
                            "user_id": user_id,
                            "dreams.thread_id": thread_id
                        },
                        {
                            "$set": {
                                "dreams.$[d].roadmap.status": "started"
                            }
                        },
                        array_filters=[
                            {"d.thread_id": thread_id}
                        ]
                    )
                break

        # Prepare update data with completedDate timestamp
        update_fields = {
            "dreams.$[d].roadmap.milestones.$[m].status": update_data.status
        }

        # Add completedDate if status is being set to 'completed'
        if update_data.status == "completed":
            update_fields["dreams.$[d].roadmap.milestones.$[m].completedDate"] = datetime.now(timezone.utc).isoformat()

        # Add evidence if provided (for community features)
        if update_data.evidence is not None:
            update_fields["dreams.$[d].roadmap.milestones.$[m].evidence"] = update_data.evidence

        # Add impact if provided and valid (for community features)
        if update_data.impact is not None:
            valid_impacts = ["critical", "high", "medium", "low"]
            if update_data.impact in valid_impacts:
                update_fields["dreams.$[d].roadmap.milestones.$[m].impact"] = update_data.impact
            else:
                logger.warning(f"Invalid impact level: {update_data.impact}. Using default.")

        # Update the milestone status using array filters
        # This uses $set to update ONLY the status field, preserving all other milestone data
        # Only query by user_id - the array filters will handle the nested matching
        result = await db.users.find_one_and_update(
            {
                "user_id": user_id
            },
            {
                "$set": update_fields
            },
            array_filters=[
                {"d.thread_id": thread_id},
                {"m.id": milestone_id}
            ],
            return_document=True
        )

        if not result:
            logger.error(f"Failed to update milestone despite verification passing")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update milestone"
            )

        # Find the updated milestone from the result
        updated_dream = next(
            (dream for dream in result.get("dreams", [])
             if dream.get("thread_id") == thread_id),
            None
        )

        updated_milestone = next(
            (m for m in updated_dream.get("roadmap", {}).get("milestones", [])
             if m.get("id") == milestone_id),
            None
        )

        # Update dream's metadata.score with milestone xp_points
        xp_points = updated_milestone.get("xp_points", 0)

        if xp_points > 0 and updated_dream:
            # Check if dream metadata.score exists
            dream_metadata = updated_dream.get("metadata", {})
            current_score = dream_metadata.get("score", None)

            if current_score is None:
                # Score doesn't exist, set it to xp_points (don't increment)
                new_score = xp_points
                logger.info(f"Creating dream metadata.score with value {xp_points}")
            else:
                # Score exists, increment it
                new_score = current_score + xp_points
                logger.info(f"Incrementing dream metadata.score from {current_score} to {new_score}")

            # Calculate total XP from all milestones in the dream
            total_xp = sum(
                m.get("xp_points", 0) for m in updated_dream.get("roadmap", {}).get("milestones", [])
            )

            # Check if dream is complete (score equals total XP)
            is_complete = new_score == total_xp
            logger.info(f"Dream completion check: score={new_score}, total_xp={total_xp}, isComplete={is_complete}")

            # Update the dream's metadata.score and isComplete flag
            update_dream_fields = {
                "dreams.$[d].metadata.score": new_score
            }
            if is_complete:
                update_dream_fields["dreams.$[d].isComplete"] = True
                update_dream_fields["dreams.$[d].completed_at"] = datetime.now(timezone.utc).isoformat()
                update_dream_fields["dreams.$[d].status"] = "completed"
                logger.info(f"Dream {thread_id} is now complete! Setting status to completed.")

            await db.users.update_one(
                {
                    "user_id": user_id,
                    "dreams.thread_id": thread_id
                },
                {
                    "$set": update_dream_fields
                },
                array_filters=[
                    {"d.thread_id": thread_id}
                ]
            )

        logger.info(f"Successfully updated milestone {milestone_id} to status: {update_data.status}")

        # Build milestone response data
        milestone_response = None
        if updated_milestone:
            milestone_response = {
                "id": updated_milestone.get("id"),
                "title": updated_milestone.get("title"),
                "status": updated_milestone.get("status"),
                "evidence": updated_milestone.get("evidence"),
                "impact": updated_milestone.get("impact"),
                "completedDate": updated_milestone.get("completedDate"),
                "xp_points": updated_milestone.get("xp_points"),
                "challenge_type": updated_milestone.get("challenge_type"),
                "streak_eligible": updated_milestone.get("streak_eligible")
            }

        response = {
            "success": True,
            "message": f"Milestone updated",
            "milestone": milestone_response
        }

        # Add isComplete to response if dream is complete
        if xp_points > 0 and updated_dream:
            # Recalculate is_complete for response
            total_xp = sum(
                m.get("xp_points", 0) for m in updated_dream.get("roadmap", {}).get("milestones", [])
            )
            dream_metadata = updated_dream.get("metadata", {})
            current_score = dream_metadata.get("score", 0)
            new_score = current_score + xp_points
            is_complete_response = new_score == total_xp
            response["isComplete"] = is_complete_response
            response["dreamCompleted"] = is_complete_response  # NEW: explicit flag for journey recap

            # Add dream stats for Journey Recap if dream is complete
            if is_complete_response:
                all_milestones = updated_dream.get("roadmap", {}).get("milestones", [])
                total_milestone_count = len(all_milestones)

                # Count completed milestones
                completed_milestones = [
                    m for m in all_milestones
                    if m.get("status") == "completed"
                ]
                completed_milestone_count = len(completed_milestones)

                # Find earliest completedDate (dream start date)
                completed_dates = [
                    m.get("completedDate")
                    for m in all_milestones
                    if m.get("completedDate") is not None
                ]
                dream_start_date = min(completed_dates) if completed_dates else None

                # Get dream completion date
                dream_completed_date = updated_dream.get("completed_at")

                # Calculate duration in days
                duration_days = 0
                if dream_start_date and dream_completed_date:
                    try:
                        start = datetime.fromisoformat(dream_start_date.replace('Z', '+00:00'))
                        end = datetime.fromisoformat(dream_completed_date.replace('Z', '+00:00'))
                        duration_days = max(0, (end - start).days)
                    except Exception as e:
                        logger.warning(f"Failed to calculate duration: {e}")
                        duration_days = 0

                response["dreamStats"] = {
                    "totalMilestones": total_milestone_count,
                    "completedMilestones": completed_milestone_count,
                    "completionPercentage": 100,
                    "dreamStartDate": dream_start_date,
                    "dreamCompletedDate": dream_completed_date,
                    "durationDays": duration_days
                }

                logger.info(f"Dream complete! Stats: {response['dreamStats']}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating milestone {milestone_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update milestone: {str(e)}"
        )
