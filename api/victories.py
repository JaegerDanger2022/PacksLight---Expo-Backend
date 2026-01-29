"""
Victory Cards API endpoints for community features
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from core.database import get_db
from models.community import (
    CreateVictoryRequest,
    CreateVictoryResponse,
    VictoryCardResponse,
    VictoriesListResponse,
    VictoryCardDB,
    CourageBoostDB,
    BoostVictoryResponse,
    PaginationInfo,
    generate_victory_id,
    generate_boost_id,
    get_current_iso_timestamp,
    DREAM_CATEGORIES,
    IMPACT_LEVELS
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ====================
# HELPER FUNCTIONS
# ====================

def calculate_timeframe_filter(timeframe: Optional[str]) -> dict:
    """Calculate date filter based on timeframe parameter"""
    if not timeframe or timeframe == "all":
        return {}

    now = datetime.now(timezone.utc)

    if timeframe == "week":
        start_date = now - timedelta(days=7)
    elif timeframe == "month":
        start_date = now - timedelta(days=30)
    else:
        return {}

    return {"createdAt": {"$gte": start_date.isoformat()}}


def parse_categories_filter(categories: Optional[str]) -> dict:
    """Parse comma-separated categories into MongoDB filter"""
    if not categories:
        return {}

    category_list = [cat.strip() for cat in categories.split(",")]
    # Validate categories
    valid_categories = [cat for cat in category_list if cat in DREAM_CATEGORIES]

    if not valid_categories:
        return {}

    return {"dreamCategory": {"$in": valid_categories}}


# ====================
# VICTORY CARD ENDPOINTS
# ====================

@router.get("", response_model=VictoriesListResponse, tags=["victories"])
async def get_victories(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Cards per page"),
    categories: Optional[str] = Query(None, description="Comma-separated list of dream categories"),
    timeframe: Optional[str] = Query(None, description="Filter by time - 'week', 'month', or omit for 'all'")
):
    """
    Fetch victory cards with filtering and pagination

    Query Parameters:
    - page: Page number (default: 1)
    - limit: Cards per page (default: 20, max: 100)
    - categories: Comma-separated dream categories
    - timeframe: 'week', 'month', or omit for 'all'
    """
    try:
        db = get_db()

        # Build query filter
        query_filter = {}

        # Add category filter
        category_filter = parse_categories_filter(categories)
        if category_filter:
            query_filter.update(category_filter)

        # Add timeframe filter
        timeframe_filter = calculate_timeframe_filter(timeframe)
        if timeframe_filter:
            query_filter.update(timeframe_filter)

        # Calculate pagination
        skip = (page - 1) * limit

        # Get total count
        total_count = await db.victory_cards.count_documents(query_filter)
        total_pages = (total_count + limit - 1) // limit  # Ceiling division

        # Fetch victories, sorted by creation date (newest first)
        victories_cursor = db.victory_cards.find(query_filter).sort("createdAt", -1).skip(skip).limit(limit)
        victories_list = await victories_cursor.to_list(length=limit)

        # Convert to response models
        victories = [
            VictoryCardResponse(**victory) for victory in victories_list
        ]

        pagination = PaginationInfo(
            page=page,
            limit=limit,
            totalPages=total_pages,
            totalCount=total_count
        )

        return VictoriesListResponse(victories=victories, pagination=pagination)

    except Exception as e:
        logger.error(f"Error fetching victories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=CreateVictoryResponse, status_code=201, tags=["victories"])
async def create_victory(victory_data: CreateVictoryRequest):
    """
    Create a new victory card from a completed milestone

    Business Logic:
    1. Validate milestone exists and is completed
    2. Pull milestone data (title, XP, impact, status)
    3. Pull dream data (title, category)
    4. Pull user data (name, age, location) unless isAnonymous is true
    5. Create VictoryCard document in database
    6. Award +5 courage points to user
    7. Update user's couragePoints balance
    """
    try:
        db = get_db()

        # 1. Find the milestone in the user's dreams
        # We need to search through all users to find the milestone
        user_with_milestone = await db.users.find_one({
            "dreams.roadmap.milestones.id": victory_data.milestoneId
        })

        if not user_with_milestone:
            raise HTTPException(status_code=404, detail="Milestone not found")

        # 2. Extract milestone and dream data
        milestone = None
        dream = None

        for dream_item in user_with_milestone.get("dreams", []):
            roadmap = dream_item.get("roadmap", {})
            milestones = roadmap.get("milestones", [])

            for m in milestones:
                if m.get("id") == victory_data.milestoneId:
                    milestone = m
                    dream = dream_item
                    break

            if milestone:
                break

        if not milestone or not dream:
            raise HTTPException(status_code=404, detail="Milestone not found in user's dreams")

        # 3. Validate milestone is completed
        if milestone.get("status") != "completed":
            raise HTTPException(status_code=400, detail="Milestone must be completed to create a victory")

        # 4. Check if victory already exists for this milestone
        existing_victory = await db.victory_cards.find_one({"milestoneId": victory_data.milestoneId})
        if existing_victory:
            raise HTTPException(status_code=409, detail="Victory already exists for this milestone")

        # 5. Extract user data
        user_id = user_with_milestone["user_id"]
        user_display_name = "Anonymous"
        user_location = None
        user_age = None

        if not victory_data.isAnonymous:
            user_display_name = user_with_milestone.get("firstname", "Anonymous")
            community_profile = user_with_milestone.get("communityProfile", {})
            user_location = community_profile.get("location")
            user_age = community_profile.get("age")

        # 6. Determine impact level
        impact_level = victory_data.impact or milestone.get("impact", "high")
        if impact_level not in IMPACT_LEVELS:
            impact_level = "high"

        # 7. Create victory card document
        victory_id = generate_victory_id()
        victory_card = VictoryCardDB(
            id=victory_id,
            userId=user_id,
            userDisplayName=user_display_name,
            userLocation=user_location,
            userAge=user_age,
            milestoneId=victory_data.milestoneId,
            milestoneTitle=milestone.get("title", "Untitled Milestone"),
            dreamId=dream.get("thread_id", ""),
            dreamTitle=dream.get("title", "Untitled Dream"),
            dreamCategory=dream.get("category", "achievement_goals"),
            evidenceSnippet=victory_data.evidenceSnippet,
            confidenceBoost=milestone.get("xp_points", 0),
            impactLevel=impact_level,
            completedDate=milestone.get("completedDate", get_current_iso_timestamp()),
            createdAt=get_current_iso_timestamp(),
            courageBoosts=0,
            hasUserBoosted={},
            isAnonymous=victory_data.isAnonymous
        )

        # 8. Insert into database
        await db.victory_cards.insert_one(victory_card.model_dump())

        # 9. Award +5 courage points to user
        courage_points_awarded = 5

        # Initialize couragePoints if it doesn't exist
        if "couragePoints" not in user_with_milestone:
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"couragePoints": 0}}
            )

        # Update user's courage points
        await db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"couragePoints": courage_points_awarded}}
        )

        logger.info(f"Victory card created: {victory_id} for user {user_id}")

        return CreateVictoryResponse(
            success=True,
            victoryId=victory_id,
            couragePointsAwarded=courage_points_awarded
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating victory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{victoryId}", response_model=VictoryCardResponse, tags=["victories"])
async def get_victory(victoryId: str):
    """
    Fetch a single victory card
    """
    try:
        db = get_db()

        victory = await db.victory_cards.find_one({"id": victoryId})

        if not victory:
            raise HTTPException(status_code=404, detail="Victory card not found")

        return VictoryCardResponse(**victory)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching victory {victoryId}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ====================
# COURAGE BOOST ENDPOINTS
# ====================

@router.post("/{victoryId}/boost", response_model=BoostVictoryResponse, tags=["victories"])
async def boost_victory(victoryId: str, giver_user_id: str = Query(..., description="User ID of the person giving the boost")):
    """
    Give a courage boost to a victory card

    Note: In production, giver_user_id should be derived from authentication context (Bearer token)
    For now, it's passed as a query parameter for testing purposes

    Business Logic:
    1. Get authenticated user ID from token (currently from query param)
    2. Check if user has already boosted this victory
    3. If yes, return error (HTTP 409)
    4. Create CourageBoost document
    5. Increment victory card's courageBoosts count
    6. Award +1 courage point to victory card creator
    7. Return new boost count
    """
    try:
        db = get_db()

        # 1. Validate victory card exists
        victory = await db.victory_cards.find_one({"id": victoryId})

        if not victory:
            raise HTTPException(status_code=404, detail="Victory card not found")

        # 2. Check if user has already boosted this victory
        existing_boost = await db.courage_boosts.find_one({
            "victoryCardId": victoryId,
            "giverId": giver_user_id
        })

        if existing_boost:
            raise HTTPException(status_code=409, detail="User has already boosted this victory")

        # 3. Prevent users from boosting their own victories
        if victory["userId"] == giver_user_id:
            raise HTTPException(status_code=400, detail="Cannot boost your own victory")

        # 4. Create courage boost document
        boost_id = generate_boost_id()
        courage_boost = CourageBoostDB(
            id=boost_id,
            victoryCardId=victoryId,
            giverId=giver_user_id,
            receiverId=victory["userId"],
            createdAt=get_current_iso_timestamp()
        )

        # 5. Insert boost into database
        await db.courage_boosts.insert_one(courage_boost.model_dump())

        # 6. Increment victory card's boost count and update hasUserBoosted
        result = await db.victory_cards.find_one_and_update(
            {"id": victoryId},
            {
                "$inc": {"courageBoosts": 1},
                "$set": {f"hasUserBoosted.{giver_user_id}": True}
            },
            return_document=True
        )

        new_boost_count = result["courageBoosts"]

        # 7. Award +1 courage point to victory card creator
        courage_points_awarded = 1

        # Initialize couragePoints if it doesn't exist
        receiver = await db.users.find_one({"user_id": victory["userId"]})
        if receiver and "couragePoints" not in receiver:
            await db.users.update_one(
                {"user_id": victory["userId"]},
                {"$set": {"couragePoints": 0}}
            )

        # Update receiver's courage points
        await db.users.update_one(
            {"user_id": victory["userId"]},
            {"$inc": {"couragePoints": courage_points_awarded}}
        )

        logger.info(f"Courage boost given: {boost_id} from {giver_user_id} to victory {victoryId}")

        return BoostVictoryResponse(
            success=True,
            newBoostCount=new_boost_count,
            couragePointsAwarded=courage_points_awarded
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error boosting victory {victoryId}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
