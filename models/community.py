"""
Database models for Victory Wall community features
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Literal
from pydantic import BaseModel, Field, field_validator


# ====================
# REQUEST MODELS
# ====================

class CreateVictoryRequest(BaseModel):
    """Request model for creating a victory card"""
    milestoneId: str = Field(..., description="ID of the completed milestone")
    evidenceSnippet: str = Field(..., min_length=1, max_length=200, description="User's proof text, max 200 characters")
    isAnonymous: bool = Field(..., description="Whether to hide user identity")
    impact: Optional[Literal["critical", "high", "medium", "low"]] = Field(None, description="Impact level")


class UpdateCommunityProfileRequest(BaseModel):
    """Request model for updating user's community profile"""
    location: Optional[str] = Field(None, description="User's location")
    age: Optional[int] = Field(None, ge=1, le=120, description="User's age (positive integer)")
    shareAnonymousByDefault: Optional[bool] = Field(None, description="Default sharing preference")


# ====================
# RESPONSE MODELS
# ====================

class VictoryCardResponse(BaseModel):
    """Response model for a single victory card"""
    id: str
    userId: str
    userDisplayName: str
    userLocation: Optional[str] = None
    userAge: Optional[int] = None

    milestoneId: str
    milestoneTitle: str
    dreamId: str
    dreamTitle: str
    dreamCategory: str

    evidenceSnippet: str
    confidenceBoost: int  # From milestone XP
    impactLevel: str

    completedDate: str  # ISO date
    createdAt: str  # ISO date

    courageBoosts: int
    isAnonymous: bool


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    page: int
    limit: int
    totalPages: int
    totalCount: int


class VictoriesListResponse(BaseModel):
    """Response model for victory cards list"""
    victories: list[VictoryCardResponse]
    pagination: PaginationInfo


class CreateVictoryResponse(BaseModel):
    """Response for creating a victory"""
    success: bool
    victoryId: str
    couragePointsAwarded: int


class BoostVictoryResponse(BaseModel):
    """Response for boosting a victory"""
    success: bool
    newBoostCount: int
    couragePointsAwarded: int


class CommunityStatsResponse(BaseModel):
    """Response for user's community stats"""
    victoriesShared: int
    boostsReceived: int
    boostsGiven: int
    couragePoints: int


class CommunityProfile(BaseModel):
    """User's community profile"""
    location: Optional[str] = None
    age: Optional[int] = None
    shareAnonymousByDefault: bool = False


class UpdateCommunityProfileResponse(BaseModel):
    """Response for updating community profile"""
    success: bool
    message: str
    communityProfile: CommunityProfile


# ====================
# DATABASE MODELS
# ====================

class VictoryCardDB(BaseModel):
    """Victory Card database document"""
    id: str
    userId: str
    userDisplayName: str
    userLocation: Optional[str] = None
    userAge: Optional[int] = None

    milestoneId: str
    milestoneTitle: str
    dreamId: str
    dreamTitle: str
    dreamCategory: str

    evidenceSnippet: str
    confidenceBoost: int
    impactLevel: str

    completedDate: str  # ISO date
    createdAt: str  # ISO date

    courageBoosts: int = 0
    hasUserBoosted: Dict[str, bool] = Field(default_factory=dict)  # Map for quick lookup

    isAnonymous: bool

    def to_response(self) -> VictoryCardResponse:
        """Convert database model to response model"""
        return VictoryCardResponse(
            id=self.id,
            userId=self.userId,
            userDisplayName=self.userDisplayName,
            userLocation=self.userLocation,
            userAge=self.userAge,
            milestoneId=self.milestoneId,
            milestoneTitle=self.milestoneTitle,
            dreamId=self.dreamId,
            dreamTitle=self.dreamTitle,
            dreamCategory=self.dreamCategory,
            evidenceSnippet=self.evidenceSnippet,
            confidenceBoost=self.confidenceBoost,
            impactLevel=self.impactLevel,
            completedDate=self.completedDate,
            createdAt=self.createdAt,
            courageBoosts=self.courageBoosts,
            isAnonymous=self.isAnonymous
        )


class CourageBoostDB(BaseModel):
    """Courage Boost database document"""
    id: str
    victoryCardId: str
    giverId: str
    receiverId: str
    createdAt: str  # ISO date


# ====================
# UTILITY FUNCTIONS
# ====================

def generate_victory_id() -> str:
    """Generate a unique victory card ID"""
    import uuid
    return f"vic_{uuid.uuid4().hex[:12]}"


def generate_boost_id() -> str:
    """Generate a unique courage boost ID"""
    import uuid
    return f"boost_{uuid.uuid4().hex[:12]}"


def get_current_iso_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now(timezone.utc).isoformat()


# Dream categories validation list
DREAM_CATEGORIES = [
    "career_professional",
    "personal_development",
    "health_wellness",
    "creative_expression",
    "relationships_community",
    "travel_exploration",
    "finance_security",
    "lifestyle_hobbies",
    "courage_challenges",
    "achievement_goals"
]

# Impact levels validation list
IMPACT_LEVELS = ["critical", "high", "medium", "low"]
