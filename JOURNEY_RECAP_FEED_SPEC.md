# Journey Recap Feed Integration Specification

## Overview

Update the `/api/victories` endpoint to return a **combined feed** of both Victory Cards and Journey Recaps, sorted by creation date. This allows users to see complete dream journeys alongside individual milestone victories in the community feed.

---

## 1. Update GET /api/victories Endpoint

**Current Endpoint:** `GET /api/victories`
**Updated Behavior:** Return both victory cards AND journey recaps in a unified feed

### Query Parameters (unchanged)
- `page` (int): Page number (default: 1)
- `limit` (int): Items per page (default: 20, max: 100)
- `categories` (string): Comma-separated dream categories filter
- `timeframe` (string): 'week', 'month', or omit for 'all'

### Updated Response

```json
{
  "feed": [
    {
      "type": "journey_recap",
      "id": "67a1b2c3d4e5f6g7h8i9j0k1",
      "userId": "user_123",
      "userDisplayName": "Sarah",
      "userLocation": "Chicago, IL",
      "userAge": 28,
      "dreamId": "dream_789",
      "dreamTitle": "Solo Trip to Bali",
      "dreamCategory": "travel_exploration",
      "journeyStory": "This dream taught me that I'm capable of more than I thought...",
      "totalMilestones": 8,
      "durationDays": 45,
      "keyMoment": "The day I booked my flight despite my fears",
      "completedDate": "2026-01-30T10:00:00Z",
      "createdAt": "2026-01-30T11:00:00Z",
      "courageBoosts": 15,
      "hasUserBoosted": false,
      "permissionsCount": 3,
      "meTooCount": 12,
      "hasUserMeTooed": true,
      "isAnonymous": false
    },
    {
      "type": "victory_card",
      "id": "victory_456",
      "userId": "user_789",
      "userDisplayName": "Mike",
      "dreamId": "dream_123",
      "dreamTitle": "Run a Marathon",
      "dreamCategory": "health_wellness",
      "milestoneTitle": "Completed first 10K run",
      "evidenceSnippet": "Ran my first 10K today!",
      "impact": "medium",
      "completedDate": "2026-01-29T15:00:00Z",
      "createdAt": "2026-01-29T16:00:00Z",
      "courageBoosts": 8,
      "hasUserBoosted": false,
      "permissionsCount": 2,
      "meTooCount": 5,
      "hasUserMeTooed": false,
      "isAnonymous": false
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "totalPages": 5,
    "totalCount": 89
  }
}
```

### Implementation Steps

1. **Query Both Collections**
   ```python
   # Query victory_cards collection
   victory_query = {**category_filter, **timeframe_filter}
   victories = await db.victory_cards.find(victory_query).to_list(length=None)

   # Query journey_recaps collection
   journey_query = {**category_filter, **timeframe_filter}
   journeys = await db.journey_recaps.find(journey_query).to_list(length=None)
   ```

2. **Transform to Unified Format**
   ```python
   # Add type field to each item
   victory_items = [
       {"type": "victory_card", **victory}
       for victory in victories
   ]

   journey_items = [
       {"type": "journey_recap", **journey}
       for journey in journeys
   ]
   ```

3. **Merge and Sort by createdAt**
   ```python
   combined_feed = victory_items + journey_items
   combined_feed.sort(key=lambda x: x["createdAt"], reverse=True)
   ```

4. **Apply Pagination**
   ```python
   start_index = (page - 1) * limit
   end_index = start_index + limit
   paginated_feed = combined_feed[start_index:end_index]

   total_count = len(combined_feed)
   total_pages = (total_count + limit - 1) // limit
   ```

5. **Check User Interactions** (for `hasUserBoosted`, `hasUserMeTooed`)
   - For each item in feed, check if requesting user has boosted/me-too'd
   - This requires the `user_id` query parameter to be added (optional)

### Updated Endpoint Signature

```python
@router.get("", response_model=VictoriesListResponse, tags=["victories"])
async def get_victories(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    categories: Optional[str] = Query(None, description="Comma-separated list of dream categories"),
    timeframe: Optional[str] = Query(None, description="Filter by time - 'week', 'month', or omit for 'all'"),
    user_id: Optional[str] = Query(None, description="User ID for personalized hasUserBoosted/hasUserMeTooed flags")
):
```

---

## 2. Add Journey Recap Boost Endpoint

**Endpoint:** `POST /api/journey-recaps/{journey_recap_id}/boost`

**Description:** Give a courage boost to a journey recap (same mechanics as victory boost)

### Query Parameters
- `giver_user_id` (required): ID of user giving the boost

### Request
No body required

### Response (200 OK)
```json
{
  "success": true,
  "newBoostCount": 16,
  "couragePointsAwarded": 1
}
```

### Error Responses
- `400` - Invalid journey recap ID or user already boosted
- `404` - Journey recap not found
- `500` - Server error

### Implementation
```python
@router.post("/{journey_recap_id}/boost", tags=["journey-recap"])
async def boost_journey_recap(
    journey_recap_id: str,
    giver_user_id: str = Query(..., description="ID of user giving the boost")
):
    db = get_db()

    # 1. Check if journey recap exists
    journey = await db.journey_recaps.find_one({"_id": ObjectId(journey_recap_id)})
    if not journey:
        raise HTTPException(status_code=404, detail="Journey recap not found")

    # 2. Check for duplicate boost
    existing_boost = await db.courage_boosts.find_one({
        "itemId": journey_recap_id,
        "itemType": "journey_recap",
        "giverUserId": giver_user_id
    })

    if existing_boost:
        raise HTTPException(status_code=400, detail="You already boosted this journey")

    # 3. Create boost record
    boost = {
        "itemId": journey_recap_id,
        "itemType": "journey_recap",
        "giverUserId": giver_user_id,
        "receiverUserId": journey["userId"],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.courage_boosts.insert_one(boost)

    # 4. Increment boost count on journey recap
    result = await db.journey_recaps.update_one(
        {"_id": ObjectId(journey_recap_id)},
        {"$inc": {"courageBoosts": 1}}
    )

    # 5. Award courage point to receiver
    await db.users.update_one(
        {"user_id": journey["userId"]},
        {"$inc": {"couragePoints": 1}}
    )

    # 6. Get new count
    updated = await db.journey_recaps.find_one({"_id": ObjectId(journey_recap_id)})

    return {
        "success": True,
        "newBoostCount": updated["courageBoosts"],
        "couragePointsAwarded": 1
    }
```

---

## 3. Add Journey Recap Permission Endpoint

**Endpoint:** `POST /api/journey-recaps/{journey_recap_id}/permission`

**Description:** Grant a permission slip to a journey recap

### Query Parameters
- `giver_user_id` (required): ID of user giving permission

### Request Body
```json
{
  "permissionType": 4
}
```

### Response (200 OK)
```json
{
  "success": true,
  "permissionId": "perm_123",
  "permissionText": "Permission to keep showing up"
}
```

### Implementation
Same mechanics as victory card permissions, but for `journey_recaps` collection and `itemType: "journey_recap"`.

---

## 4. Add Journey Recap Me Too Endpoint

**Endpoint:** `POST /api/journey-recaps/{journey_recap_id}/metoo`

**Description:** Toggle "Me Too" on a journey recap

### Query Parameters
- `user_id` (required): ID of user toggling Me Too

### Response (200 OK)
```json
{
  "success": true,
  "newCount": 13,
  "added": true
}
```

### Implementation
Same mechanics as victory card Me Too, but for `journey_recaps` collection and `itemType: "journey_recap"`.

---

## 5. Add Get Journey Recap Permissions Endpoint

**Endpoint:** `GET /api/journey-recaps/{journey_recap_id}/permissions`

**Description:** Fetch all permissions granted to a journey recap

### Response (200 OK)
```json
{
  "permissions": [
    {
      "id": "perm_123",
      "giverUserId": "user_456",
      "giverDisplayName": "Sarah",
      "permissionType": 4,
      "permissionText": "Permission to keep showing up",
      "createdAt": "2026-01-30T12:00:00Z"
    }
  ]
}
```

### Implementation
Same mechanics as victory card permissions list, but query with `itemType: "journey_recap"`.

---

## Database Updates

### New Indexes

Add indexes to `journey_recaps` collection for efficient querying:

```python
# For feed queries (category + time filtering)
db.journey_recaps.create_index([
    ("dreamCategory", 1),
    ("createdAt", -1)
])

# For user's own journey recaps
db.journey_recaps.create_index([
    ("userId", 1),
    ("createdAt", -1)
])

# For sorting by creation date
db.journey_recaps.create_index([
    ("createdAt", -1)
])
```

### Update courage_boosts Collection

Ensure `itemType` field supports both values:
- `"victory_card"` (existing)
- `"journey_recap"` (new)

### Update permission_slips Collection

Ensure `itemType` field supports both values:
- `"victory_card"` (existing)
- `"journey_recap"` (new)

### Update metoo Collection

Ensure `itemType` field supports both values:
- `"victory_card"` (existing)
- `"journey_recap"` (new)

---

## Testing Checklist

- [ ] GET /api/victories returns mixed feed of victories and journey recaps
- [ ] Feed is sorted by createdAt (newest first)
- [ ] Category filter works for both victory cards and journey recaps
- [ ] Timeframe filter works for both types
- [ ] Pagination works correctly with combined results
- [ ] POST boost endpoint works for journey recaps
- [ ] POST permission endpoint works for journey recaps
- [ ] POST metoo endpoint works for journey recaps
- [ ] GET permissions endpoint works for journey recaps
- [ ] User cannot boost/permission/metoo the same journey recap twice
- [ ] Courage points are awarded correctly

---

## Frontend Impact

Once backend is updated, frontend will:
1. Update `fetchVictories` API call response type to include `type` field
2. Render `JourneyRecapCard` component when `type === "journey_recap"`
3. Render `VictoryCard` component when `type === "victory_card"`
4. Support boost/permission/metoo on both card types

---

## Migration Notes

**Breaking Change:** The `/api/victories` response structure changes from:
```json
{ "victories": [...], "pagination": {...} }
```

To:
```json
{ "feed": [...], "pagination": {...} }
```

**Migration Steps:**
1. Update backend to return `feed` field instead of `victories`
2. Update frontend to read from `response.feed` instead of `response.victories`
3. Ensure frontend handles both `type: "victory_card"` and `type: "journey_recap"`

Alternatively, keep backwards compatibility by returning both fields during transition period.
