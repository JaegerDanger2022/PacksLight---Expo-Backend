# Victory Wall (Community Feature) - Backend Endpoints Specification

This document specifies all backend API endpoints required for Phase 1 implementation of the Victory Wall community feature.

## Overview

The Victory Wall allows users to share completed milestones as Victory Cards and interact through Courage Boosts. Users earn separate "courage points" for sharing and receiving boosts.

## Base URL

```
{API_BASE_URL}/api
```

Example: `http://localhost:5000/api`

---

## 1. Victory Cards Endpoints

### 1.1 GET /api/victories

**Purpose:** Fetch victory cards with filtering and pagination

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `limit` (integer, optional): Cards per page (default: 20)
- `categories` (string, optional): Comma-separated list of dream categories (e.g., "career_professional,travel_exploration")
- `timeframe` (string, optional): Filter by time - values: "week", "month", or omit for "all"

**Example Request:**
```
GET /api/victories?page=1&limit=20&categories=career_professional,travel_exploration&timeframe=week
```

**Response (200 OK):**
```json
{
  "victories": [
    {
      "id": "vic_123",
      "userId": "user_456",
      "userDisplayName": "Sarah",
      "userLocation": "Chicago, IL",
      "userAge": 32,
      "milestoneId": "milestone_789",
      "milestoneTitle": "Booked my Bali flight",
      "dreamId": "dream_456",
      "dreamTitle": "Solo Trip to Bali",
      "dreamCategory": "travel_exploration",
      "evidenceSnippet": "Paid $847. It's refundable but IT'S REAL.",
      "confidenceBoost": 35,
      "impactLevel": "critical",
      "completedDate": "2026-01-28T10:30:00Z",
      "createdAt": "2026-01-28T11:00:00Z",
      "courageBoosts": 12,
      "isAnonymous": false
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "totalPages": 5,
    "totalCount": 94
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid query parameters
- `500 Internal Server Error`: Server error

---

### 1.2 POST /api/victories

**Purpose:** Create a new victory card from a completed milestone

**Request Body:**
```json
{
  "milestoneId": "milestone_789",
  "evidenceSnippet": "Custom proof text (max 200 chars)",
  "isAnonymous": false,
  "impact": "high"
}
```

**Request Fields:**
- `milestoneId` (string, required): ID of the completed milestone
- `evidenceSnippet` (string, required): User's proof text, max 200 characters
- `isAnonymous` (boolean, required): Whether to hide user identity
- `impact` (string, optional): Impact level - "critical", "high", "medium", or "low" (if not provided, use milestone's impact or default to "high")

**Response (201 Created):**
```json
{
  "success": true,
  "victoryId": "vic_123",
  "couragePointsAwarded": 5
}
```

**Business Logic:**
1. Validate milestone exists and is completed
2. Pull milestone data (title, XP, impact, status)
3. Pull dream data (title, category)
4. Pull user data (name, age, location) unless `isAnonymous` is true
5. Create VictoryCard document in database
6. Award +5 courage points to user
7. Update user's `couragePoints` balance

**Error Responses:**
- `400 Bad Request`: Missing required fields or invalid data
- `404 Not Found`: Milestone not found
- `409 Conflict`: Victory already exists for this milestone
- `500 Internal Server Error`: Server error

---

### 1.3 GET /api/victories/:victoryId

**Purpose:** Fetch a single victory card

**URL Parameters:**
- `victoryId` (string, required): ID of the victory card

**Response (200 OK):**
```json
{
  "id": "vic_123",
  "userId": "user_456",
  "userDisplayName": "Sarah",
  "userLocation": "Chicago, IL",
  "userAge": 32,
  "milestoneId": "milestone_789",
  "milestoneTitle": "Booked my Bali flight",
  "dreamId": "dream_456",
  "dreamTitle": "Solo Trip to Bali",
  "dreamCategory": "travel_exploration",
  "evidenceSnippet": "Paid $847. It's refundable but IT'S REAL.",
  "confidenceBoost": 35,
  "impactLevel": "critical",
  "completedDate": "2026-01-28T10:30:00Z",
  "createdAt": "2026-01-28T11:00:00Z",
  "courageBoosts": 12,
  "isAnonymous": false
}
```

**Error Responses:**
- `404 Not Found`: Victory card not found
- `500 Internal Server Error`: Server error

---

## 2. Courage Boost Endpoints

### 2.1 POST /api/victories/:victoryId/boost

**Purpose:** Give a courage boost to a victory card

**URL Parameters:**
- `victoryId` (string, required): ID of the victory card to boost

**Request Body:**
```json
{}
```

Note: User ID is derived from authentication context (Bearer token)

**Response (200 OK):**
```json
{
  "success": true,
  "newBoostCount": 13,
  "couragePointsAwarded": 1
}
```

**Business Logic:**
1. Get authenticated user ID from token
2. Check if user has already boosted this victory
3. If yes, return error (HTTP 409)
4. Create CourageBoost document with:
   - `victoryCardId`: victoryId
   - `giverId`: authenticated user ID
   - `receiverId`: victory card creator's user ID
   - `createdAt`: current timestamp
5. Increment victory card's `courageBoosts` count
6. Award +1 courage point to victory card creator
7. Update victory card creator's `couragePoints` balance
8. Return new boost count

**Error Responses:**
- `400 Bad Request`: Invalid victory ID
- `404 Not Found`: Victory card not found
- `409 Conflict`: User has already boosted this victory
- `401 Unauthorized`: User not authenticated
- `500 Internal Server Error`: Server error

---

## 3. Community Stats Endpoints

### 3.1 GET /api/users/:userId/community-stats

**Purpose:** Get user's community engagement statistics

**URL Parameters:**
- `userId` (string, required): User ID

**Response (200 OK):**
```json
{
  "victoriesShared": 12,
  "boostsReceived": 347,
  "boostsGiven": 89,
  "couragePoints": 450
}
```

**Calculation Logic:**
- `victoriesShared`: Count of VictoryCard documents where userId matches
- `boostsReceived`: Count of CourageBoost documents where receiverId matches
- `boostsGiven`: Count of CourageBoost documents where giverId matches
- `couragePoints`: Value from user document's `couragePoints` field

**Error Responses:**
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server error

---

## 4. Enhanced Milestone Endpoints

### 4.1 PUT /api/milestone/update-status/:userId/:threadId/:milestoneId

**Purpose:** Update milestone status (enhanced to support community features)

**URL Parameters:**
- `userId` (string, required): User ID
- `threadId` (string, required): Dream thread ID
- `milestoneId` (string, required): Milestone ID

**Request Body:**
```json
{
  "status": "completed",
  "evidence": "User's proof text (optional, max 200 chars)",
  "impact": "high"
}
```

**Request Fields:**
- `status` (string, required): New status - "pending", "in_progress", or "completed"
- `evidence` (string, optional): Evidence/proof text, max 200 characters
- `impact` (string, optional): Impact level - "critical", "high", "medium", or "low"

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Milestone updated",
  "milestone": {
    "id": "milestone_789",
    "title": "Booked my Bali flight",
    "status": "completed",
    "evidence": "User's proof text",
    "impact": "high",
    "completedDate": "2026-01-28T10:30:00Z",
    "xp_points": 35,
    "challenge_type": "power_move",
    "streak_eligible": true
  },
  "isComplete": true
}
```

**Business Logic:**
1. Validate milestone exists
2. Update milestone status
3. If `evidence` provided, store it in milestone (or update `evidenceAddedDate`)
4. If `impact` provided, update milestone impact level
5. If status is "completed", set `completedDate` to current timestamp
6. Return updated milestone data

**Error Responses:**
- `400 Bad Request`: Invalid status or other validation errors
- `404 Not Found`: Milestone or dream not found
- `500 Internal Server Error`: Server error

---

## 5. User Profile Endpoints

### 5.1 GET /api/users/:userId

**Purpose:** Fetch user data (enhanced to include community fields)

**URL Parameters:**
- `userId` (string, required): User ID

**Response (200 OK):**
```json
{
  "user_id": "user_456",
  "firstname": "Sarah",
  "lastname": "Smith",
  "email": "sarah@example.com",
  "created_at": "2025-11-15T10:00:00Z",
  "couragePoints": 450,
  "communityProfile": {
    "location": "Chicago, IL",
    "age": 32,
    "shareAnonymousByDefault": false
  },
  "up_next": {...},
  "streak": {...},
  "recents": [...],
  "dreams": [...]
}
```

**New/Enhanced Fields:**
- `couragePoints` (integer): Total courage points earned (default: 0)
- `communityProfile` (object):
  - `location` (string, optional): User's location
  - `age` (integer, optional): User's age
  - `shareAnonymousByDefault` (boolean): User preference for anonymity

**Error Responses:**
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server error

---

### 5.2 PUT /api/users/:userId/community-profile

**Purpose:** Update user's community profile settings

**URL Parameters:**
- `userId` (string, required): User ID

**Request Body:**
```json
{
  "location": "Chicago, IL",
  "age": 32,
  "shareAnonymousByDefault": false
}
```

**Request Fields (all optional):**
- `location` (string, optional): User's location
- `age` (integer, optional): User's age (positive integer)
- `shareAnonymousByDefault` (boolean, optional): Default sharing preference

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Community profile updated",
  "communityProfile": {
    "location": "Chicago, IL",
    "age": 32,
    "shareAnonymousByDefault": false
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid data (e.g., negative age)
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server error

---

## 6. Data Models

### VictoryCard Collection

```typescript
{
  _id: ObjectId,
  id: string,  // Unique ID
  userId: string,
  userDisplayName: string,  // "Sarah" or "Anonymous"
  userLocation?: string,
  userAge?: number,

  milestoneId: string,
  milestoneTitle: string,
  dreamId: string,
  dreamTitle: string,
  dreamCategory: string,

  evidenceSnippet: string,  // Max 200 chars
  confidenceBoost: number,  // From milestone XP
  impactLevel: 'critical' | 'high' | 'medium' | 'low',

  completedDate: string,  // ISO date (from milestone)
  createdAt: string,  // ISO date (when posted to wall)

  courageBoosts: number,  // Count
  hasUserBoosted: {  // Map for quick lookup
    [userId: string]: boolean
  },

  isAnonymous: boolean
}
```

**Indexes:**
```sql
CREATE INDEX idx_victories_category ON victory_cards(dream_category);
CREATE INDEX idx_victories_completed_date ON victory_cards(completed_date);
CREATE INDEX idx_victories_created_at ON victory_cards(created_at);
CREATE INDEX idx_victories_user ON victory_cards(userId);
```

### CourageBoost Collection

```typescript
{
  _id: ObjectId,
  id: string,  // Unique ID
  victoryCardId: string,
  giverId: string,
  receiverId: string,
  createdAt: string  // ISO date
}
```

**Indexes:**
```sql
CREATE INDEX idx_boosts_victory ON courage_boosts(victory_card_id);
CREATE INDEX idx_boosts_giver ON courage_boosts(giver_id);
CREATE INDEX idx_boosts_receiver ON courage_boosts(receiver_id);
```

### User Model Updates

Add these fields to User document:

```typescript
{
  // Existing fields...

  couragePoints: number,  // Default: 0
  communityProfile: {
    location?: string,
    age?: number,
    shareAnonymousByDefault: boolean  // Default: false
  }
}
```

---

## 7. Authentication

All endpoints (except public victory feed) require authentication via Bearer token:

```
Authorization: Bearer {idToken}
```

The token is extracted to get the authenticated user ID for:
- Creating victories
- Giving boosts
- Fetching personal stats

---

## 8. Error Handling

All endpoints should return errors in this format:

```json
{
  "success": false,
  "message": "Human-readable error message",
  "detail": "Optional additional details"
}
```

**Standard HTTP Status Codes:**
- `200 OK`: Successful GET or PUT
- `201 Created`: Successful POST creating a resource
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Missing or invalid authentication
- `404 Not Found`: Resource not found
- `409 Conflict`: Duplicate boost, victory already exists
- `500 Internal Server Error`: Server error

---

## 9. Response Headers

All responses should include:

```
Content-Type: application/json
Access-Control-Allow-Origin: * (or specify frontend origin)
```

---

## 10. Pagination

List endpoints (e.g., GET /api/victories) return:

```json
{
  "victories": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "totalPages": 5,
    "totalCount": 94
  }
}
```

---

## 11. Rate Limiting (Recommended)

Consider implementing rate limiting for mutation endpoints:

- **POST /api/victories**: 50 requests per user per day
- **POST /api/victories/:id/boost**: 100 requests per user per day

This prevents abuse while allowing normal usage.

---

## 12. Implementation Notes

### For Backend Developer:

1. **Dream Categories:** Must match frontend enum:
   - career_professional
   - personal_development
   - health_wellness
   - creative_expression
   - relationships_community
   - travel_exploration
   - finance_security
   - lifestyle_hobbies
   - courage_challenges
   - achievement_goals

2. **Impact Levels:** Validation required for:
   - critical
   - high
   - medium
   - low

3. **Courage Points System:**
   - +5 points when creating a victory
   - +1 point when receiving a boost
   - Store cumulative total in user's `couragePoints` field

4. **Duplicate Prevention:**
   - One boost per user per victory card
   - Check `hasUserBoosted` map or query CourageBoost collection

5. **Date Handling:**
   - All dates in ISO 8601 format
   - Store in UTC timezone
   - Use consistent timezone across endpoints

6. **Field Validation:**
   - evidenceSnippet: max 200 characters, required, non-empty
   - userAge: positive integer if provided
   - userLocation: string if provided, optional

---

## 13. Testing Checklist

- [ ] GET /api/victories with no filters
- [ ] GET /api/victories with category filter
- [ ] GET /api/victories with timeframe filter
- [ ] GET /api/victories with pagination (page 2, 3)
- [ ] POST /api/victories (creates victory)
- [ ] POST /api/victories with isAnonymous=true (hides user info)
- [ ] POST /api/victories/:id/boost (first boost)
- [ ] POST /api/victories/:id/boost (duplicate boost - should error)
- [ ] GET /api/users/:userId/community-stats
- [ ] PUT /api/users/:userId/community-profile
- [ ] Courage points increment correctly after create/boost
- [ ] Victory cards appear in feed after creation
- [ ] Filtering returns correct subset of victories
- [ ] Pagination works correctly (totalPages, totalCount)

---

## 14. Example Integration Flow

### User Creates and Shares Victory:

1. Frontend: POST /api/milestone/update-status (complete milestone with evidence)
2. Backend: Updates milestone, returns isComplete=true
3. Frontend: Shows victory share modal with milestone data
4. User enters evidence and clicks "Post to Victory Wall"
5. Frontend: POST /api/victories with milestoneId, evidenceSnippet, isAnonymous
6. Backend: Creates VictoryCard, awards +5 courage points
7. Frontend: Shows success, updates local courage points
8. User views victory in feed within seconds

### User Boosts Victory:

1. Frontend: User views VictoryCard in feed, taps boost button
2. Frontend: Optimistic update - increment boost count, animate button
3. Frontend: POST /api/victories/:victoryId/boost
4. Backend: Check duplicate, create CourageBoost, award +1 points to creator
5. Frontend: Success toast, update courage points
6. Creator receives notification of boost (Phase 2+)

---

This specification should provide the backend team with all necessary details to implement Phase 1 of the Victory Wall feature.
