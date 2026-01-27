"""
Milestone API endpoints - Update and manage milestones in roadmaps
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateMilestoneRequest(BaseModel):
    """Request schema for updating a milestone"""
    status: str = Field(..., description="New status for the milestone (e.g., 'completed', 'pending', 'in_progress')")


@router.put("/update-status/{thread_id}/{milestone_id}", status_code=200, tags=["milestone"])
async def update_milestone_status(
    thread_id: str,
    milestone_id: str,
    update_data: UpdateMilestoneRequest
):
    """
    Update a milestone's status in a dream.

    Args:
        thread_id: The thread ID of the dream containing the milestone
        milestone_id: The ID of the milestone to update
        update_data: Request body containing the new status

    Returns:
        dict: Updated milestone data with the new status

    Raises:
        404: Dream or milestone not found
        500: Database error
    """
    try:
        db = get_db()
        if not db:
            logger.error("Database connection not available")
            raise HTTPException(
                status_code=500,
                detail="Database connection not available"
            )

        logger.info(f"Updating milestone {milestone_id} in dream {thread_id} to status: {update_data.status}")

        # Update the milestone status using array filters to target the specific milestone
        # This uses $set to update ONLY the status field, preserving all other milestone data
        result = await db.users.find_one_and_update(
            {
                "dreams.thread_id": thread_id
            },
            {
                "$set": {
                    "dreams.$[d].roadmap.milestones.$[m].status": update_data.status
                }
            },
            array_filters=[
                {"d.thread_id": thread_id},
                {"m.id": milestone_id}
            ],
            return_document=True
        )

        if not result:
            logger.warning(f"Dream with thread_id {thread_id} not found for update")
            raise HTTPException(
                status_code=404,
                detail=f"Dream with thread_id {thread_id} not found"
            )

        # Find and return the updated milestone
        dream_data = next(
            (dream for dream in result.get("dreams", [])
             if dream.get("thread_id") == thread_id),
            None
        )

        if not dream_data:
            logger.warning(f"Could not find dream with thread_id {thread_id} in result")
            raise HTTPException(
                status_code=404,
                detail=f"Dream with thread_id {thread_id} not found"
            )

        milestone = next(
            (m for m in dream_data.get("roadmap", {}).get("milestones", [])
             if m.get("id") == milestone_id),
            None
        )

        if not milestone:
            logger.warning(f"Milestone {milestone_id} not found in dream {thread_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Milestone with ID {milestone_id} not found in dream {thread_id}"
            )

        logger.info(f"Successfully updated milestone {milestone_id} to status: {update_data.status}")

        return {
            "success": True,
            "message": f"Milestone {milestone_id} status updated to {update_data.status}",
            "milestone": milestone
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating milestone {milestone_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update milestone: {str(e)}"
        )
