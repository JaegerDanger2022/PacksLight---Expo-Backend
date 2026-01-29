# Inspiration/Saved Victories Endpoint Specification

## Overview
Users can save victories to their inspiration collection by clicking "Me Too" on victory cards. This endpoint retrieves all victories that a user has saved to their inspiration collection.

## Endpoint Details

### GET `/api/users/{user_id}/inspiration`

Retrieves all victory cards that the user has saved by clicking "Me Too".

#### URL Parameters
- `user_id` (string, required): Firebase UID of the user

#### Query Parameters
- `page` (integer, optional): Page number for pagination (default: 1)
- `limit` (integer, optional): Number of items per page (default: 10, max: 50)

#### Success Response (200 OK)

```json
{
  "victories": [
    {
      "id": "victory_123",
      "userId": "user_456",
      "userDisplayName": "Sarah",
      "userLocation": "San Francisco, CA",
      "userAge": 28,
      "milestoneId": "milestone_789",
      "milestoneTitle": "Completed First Marathon",
      "dreamId": "dream_101",
      "dreamTitle": "Run a Marathon",
      "dreamCategory": "health_wellness",
      "evidenceSnippet": "I crossed the finish line in 4 hours and 30 minutes! It was the hardest thing I've ever done, but so worth it.",
      "confidenceBoost": 50,
      "impactLevel": "critical",
      "completedDate": "2026-01-25T10:30:00Z",
      "createdAt": "2026-01-25T11:00:00Z",
      "courageBoosts": 42,
      "hasUserBoosted": false,
      "permissionsCount": 8,
      "meTooCount": 156,
      "hasUserMeTooed": true,
      "isAnonymous": false
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "totalPages": 5,
    "totalCount": 47
  }
}
```

#### Response Fields

**Victory Object:**
- `id`: Unique identifier for the victory card
- `userId`: Firebase UID of the victory creator
- `userDisplayName`: Display name (first name or "Anonymous")
- `userLocation`: Optional user location string
- `userAge`: Optional user age
- `milestoneId`: Associated milestone ID
- `milestoneTitle`: Title of the milestone
- `dreamId`: Associated dream/goal ID
- `dreamTitle`: Title of the dream/goal
- `dreamCategory`: Category enum (see categories below)
- `evidenceSnippet`: User's evidence/story text
- `confidenceBoost`: XP points earned (integer)
- `impactLevel`: Impact level enum: "critical", "high", "medium", "low"
- `completedDate`: ISO 8601 timestamp when milestone was completed
- `createdAt`: ISO 8601 timestamp when victory was created
- `courageBoosts`: Count of courage boosts received
- `hasUserBoosted`: Boolean indicating if requesting user has boosted (should be calculated per request)
- `permissionsCount`: Count of permission slips given
- `meTooCount`: Count of "Me Too" clicks
- `hasUserMeTooed`: Boolean - should always be `true` for this endpoint since user saved it
- `isAnonymous`: Boolean indicating if posted anonymously

**Pagination Object:**
- `page`: Current page number
- `limit`: Items per page
- `totalPages`: Total number of pages
- `totalCount`: Total number of saved victories

#### Dream Categories
```
career_professional
personal_development
health_wellness
creative_expression
relationships_community
travel_exploration
finance_security
lifestyle_hobbies
courage_challenges
achievement_goals
```

#### Error Responses

**400 Bad Request**
```json
{
  "detail": "Invalid user_id parameter"
}
```

**404 Not Found**
```json
{
  "detail": "User not found"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Internal server error"
}
```

## Implementation Notes

### Database Schema Considerations

The existing `me_too` collection/table should already track which users have clicked "Me Too" on which victories:
```
me_too:
  - id (primary key)
  - victory_card_id (foreign key to victory_cards)
  - user_id (foreign key to users)
  - created_at (timestamp)
```

### Query Logic

To retrieve inspiration victories for a user:

1. Query the `me_too` collection/table for all records where `user_id` matches the requesting user
2. Join with the `victory_cards` collection/table to get full victory details
3. Join with `users` collection/table to get victory creator info (respecting anonymity)
4. Calculate `hasUserBoosted` by checking if user has a record in `courage_boosts` for each victory
5. Set `hasUserMeTooed` to `true` for all results (since they're from the user's Me Too list)
6. Order by `me_too.created_at` DESC (most recently saved first)
7. Apply pagination

### Performance Considerations

- Index on `me_too.user_id` for fast lookup
- Index on `me_too.created_at` for efficient sorting
- Consider caching user's inspiration count
- Limit max page size to 50 to prevent performance issues

### Related Endpoints

This endpoint complements the existing Me Too functionality:
- `POST /api/victories/{victory_id}/metoo?user_id={user_id}` - Toggle Me Too (adds/removes from inspiration)
- The toggle endpoint should already be saving records to enable this GET endpoint

## Frontend Integration

The frontend is already prepared to consume this endpoint:
- API function: `fetchInspirationVictories(userId)` in `src/config/api.ts`
- UI: HomeScreen inspiration tab displays saved victories
- Gracefully handles 404 until endpoint is implemented (shows empty state)

## Testing

### Test Cases

1. **Empty inspiration list**: User who hasn't clicked Me Too on any victories should return empty array
2. **Populated list**: User with saved victories should receive all their saved victories
3. **Pagination**: Test with user who has >10 saved victories to verify pagination works
4. **Anonymous victories**: Ensure anonymous victories show "Anonymous" instead of real names
5. **hasUserBoosted calculation**: Verify this field correctly reflects if user has boosted each victory
6. **Ordering**: Verify victories are ordered by most recently saved first (me_too.created_at DESC)
7. **Victory removed**: If a victory is deleted, it should not appear in inspiration list
8. **Me Too removed**: If user un-clicks Me Too, victory should no longer appear in their inspiration

### Sample cURL Request

```bash
curl -X GET "https://api.yourdomain.com/api/users/JFb4M3pHTbWwg9iUZnEHXcHVTNg1/inspiration?page=1&limit=10" \
  -H "Content-Type: application/json"
```

## Priority

**Priority: High**

This endpoint is required for the inspiration feature on the HomeScreen. Users currently see an empty state when they click the inspiration tab, even after saving victories via Me Too.
