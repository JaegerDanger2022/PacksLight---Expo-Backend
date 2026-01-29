"""
Community API endpoints for user stats and profile
"""

import logging
from fastapi import APIRouter, HTTPException
from core.database import get_db
from models.community import (
    CommunityStatsResponse,
    UpdateCommunityProfileRequest,
    UpdateCommunityProfileResponse,
    CommunityProfile
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ====================
# COMMUNITY STATS ENDPOINTS
# ====================

@router.get("/users/{userId}/community-stats", response_model=CommunityStatsResponse, tags=["community"])
async def get_community_stats(userId: str):
    """
    Get user's community engagement statistics

    Calculation Logic:
    - victoriesShared: Count of VictoryCard documents where userId matches
    - boostsReceived: Count of CourageBoost documents where receiverId matches
    - boostsGiven: Count of CourageBoost documents where giverId matches
    - couragePoints: Value from user document's couragePoints field
    """
    try:
        db = get_db()

        # Validate user exists
        user = await db.users.find_one({"user_id": userId})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Count victories shared
        victories_shared = await db.victory_cards.count_documents({"userId": userId})

        # Count boosts received
        boosts_received = await db.courage_boosts.count_documents({"receiverId": userId})

        # Count boosts given
        boosts_given = await db.courage_boosts.count_documents({"giverId": userId})

        # Count permissions received
        permissions_received = await db.permission_slips.count_documents({"receiverId": userId})

        # Count permissions given
        permissions_given = await db.permission_slips.count_documents({"giverId": userId})

        # Get courage points from user document
        courage_points = user.get("couragePoints", 0)

        logger.info(f"Community stats fetched for user {userId}")

        return CommunityStatsResponse(
            victoriesShared=victories_shared,
            boostsReceived=boosts_received,
            boostsGiven=boosts_given,
            permissionsReceived=permissions_received,
            permissionsGiven=permissions_given,
            couragePoints=courage_points
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching community stats for {userId}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ====================
# COMMUNITY PROFILE ENDPOINTS
# ====================

@router.put("/users/{userId}/community-profile", response_model=UpdateCommunityProfileResponse, tags=["community"])
async def update_community_profile(userId: str, profile_data: UpdateCommunityProfileRequest):
    """
    Update user's community profile settings

    Request Fields (all optional):
    - location: User's location
    - age: User's age (positive integer)
    - shareAnonymousByDefault: Default sharing preference
    """
    try:
        db = get_db()

        # Validate user exists
        user = await db.users.find_one({"user_id": userId})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Build update document
        update_data = {}

        if profile_data.location is not None:
            update_data["communityProfile.location"] = profile_data.location

        if profile_data.age is not None:
            # Pydantic validation already ensures age is between 1 and 120
            update_data["communityProfile.age"] = profile_data.age

        if profile_data.shareAnonymousByDefault is not None:
            update_data["communityProfile.shareAnonymousByDefault"] = profile_data.shareAnonymousByDefault

        # If no fields to update, return current profile
        if not update_data:
            current_profile = user.get("communityProfile", {})
            return UpdateCommunityProfileResponse(
                success=True,
                message="No changes made",
                communityProfile=CommunityProfile(
                    location=current_profile.get("location"),
                    age=current_profile.get("age"),
                    shareAnonymousByDefault=current_profile.get("shareAnonymousByDefault", False)
                )
            )

        # Update user document
        await db.users.update_one(
            {"user_id": userId},
            {"$set": update_data}
        )

        # Fetch updated user
        updated_user = await db.users.find_one({"user_id": userId})
        updated_profile = updated_user.get("communityProfile", {})

        logger.info(f"Community profile updated for user {userId}")

        return UpdateCommunityProfileResponse(
            success=True,
            message="Community profile updated",
            communityProfile=CommunityProfile(
                location=updated_profile.get("location"),
                age=updated_profile.get("age"),
                shareAnonymousByDefault=updated_profile.get("shareAnonymousByDefault", False)
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating community profile for {userId}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
