# Backend API Specification: Me Too Feature (Phase 2)

## Overview

The Me Too feature is a low-effort solidarity button that allows users to indicate they're working on a similar dream. It's designed to be low-pressure (no notification sent) and provides value by saving victories to the user's "Inspirations" list.

---

## Database Schema

### New Collection: `me_toos`

```javascript
{
  _id: ObjectId,
  victoryCardId: ObjectId,          // Reference to victory_cards collection
  userId: ObjectId,                 // User who clicked Me Too
  createdAt: Date,

  // Indexes
  index: { victoryCardId: 1, userId: 1 },  // Unique index to prevent duplicates
  index: { userId: 1, createdAt: -1 }      // For user's inspiration list
}
```

### Updates to Existing Collections

**`victory_cards` collection - add field:**
```javascript
{
  // ... existing fields ...
  meTooCount: Number,               // Count of Me Too clicks (default: 0)
}
```

**`users` collection - optional enhancement:**
```javascript
{
  // ... existing fields ...
  // No additional fields needed - inspirations are queried from me_toos collection
}
```

---

## API Endpoints

### 1. Toggle Me Too

**Endpoint:** `POST /api/victories/:victoryId/metoo`

**Description:** Toggle Me Too for a victory card (add if not exists, remove if exists).

**Request Body:**
```json
{}  // Empty body - user ID comes from authentication
```

**Success Response (200):**
```json
{
  "success": true,
  "newMeTooCount": 24,
  "added": true  // true if added, false if removed (toggle)
}
```

**Error Responses:**
- `400` - Invalid victoryId
- `401` - User not authenticated
- `404` - Victory card not found
- `500` - Server error

**Business Logic:**
1. Validate victory card exists
2. Check if user already has Me Too for this victory
   - If exists: Remove Me Too document
   - If not exists: Create Me Too document
3. Update `meTooCount` on victory card:
   - If added: increment by 1
   - If removed: decrement by 1
4. Return updated count and whether it was added or removed
5. **No notification sent** (this is intentional - low-pressure feature)

**Important Notes:**
- This is a toggle endpoint - calling it twice removes the Me Too
- Users CAN give Me Too to their own victories (unlike permissions)
- No courage points awarded (unlike boosts/permissions)
- No notification sent to victory owner

---

### 2. Get User's Inspirations (Optional)

**Endpoint:** `GET /api/users/:userId/inspirations`

**Description:** Get list of victories the user has clicked "Me Too" on.

**Query Parameters:**
- `limit` (optional): Number of victories to return (default: 20)
- `offset` (optional): Pagination offset (default: 0)

**Success Response (200):**
```json
{
  "inspirations": [
    {
      "id": "victory_123",
      "milestoneTitle": "Booked my Bali flight",
      "dreamTitle": "Solo Trip to Bali",
      "dreamCategory": "travel_exploration",
      "userDisplayName": "Sarah",
      "createdAt": "2026-01-28T10:30:00Z",
      "meTooDate": "2026-01-28T14:00:00Z"
    }
  ],
  "total": 15
}
```

**Error Responses:**
- `401` - User not authenticated
- `404` - User not found
- `500` - Server error

**Business Logic:**
1. Query `me_toos` collection for user's entries
2. Join with `victory_cards` to get full victory details
3. Sort by `meTooDate` descending (most recent first)
4. Apply pagination
5. Return list with total count

---

### 3. Update Victory Card Response (Enhancement)

**Endpoint:** `GET /api/victories`

**Description:** Include `meTooCount` and `hasUserMeTooed` in victory card responses.

**Updated Victory Card Object:**
```json
{
  "id": "victory_123",
  "userId": "user_456",
  "userDisplayName": "Sarah",
  "milestoneTitle": "Booked my Bali flight",
  "dreamTitle": "Solo Trip to Bali",
  "dreamCategory": "travel_exploration",
  "evidenceSnippet": "Just clicked 'confirm' on the booking!",
  "confidenceBoost": 15,
  "impactLevel": "high",
  "completedDate": "2026-01-28T10:00:00Z",
  "createdAt": "2026-01-28T10:30:00Z",
  "courageBoosts": 23,
  "permissionsCount": 5,
  "meTooCount": 89,              // NEW FIELD
  "hasUserMeTooed": true,        // NEW FIELD (for current authenticated user)
  "isAnonymous": false
}
```

**Implementation Note:**
- `hasUserMeTooed` should be calculated based on the current authenticated user
- Query `me_toos` collection to check if a record exists for this user + victory
- This can be done efficiently with a JOIN or separate query

---

## Validation Rules

1. **Toggle Behavior**: Same user + same victory = toggle (add/remove)

2. **Self Me Too**: Users CAN give Me Too to their own victories (allowed, unlike permissions)

3. **Count Accuracy**: Always recalculate count from `me_toos` collection to prevent drift

---

## Points System

- **No courage points awarded** (Me Too is a low-pressure, low-reward feature)
- The value is in organizing the user's inspiration list

---

## Notifications

**NO notifications sent** when receiving a Me Too. This is intentional to keep it low-pressure.

---

## Performance Considerations

1. **Indexing**:
   - Compound unique index on `{ victoryCardId, userId }` prevents duplicate Me Toos
   - Index on `userId` for fast inspiration list queries
   - Index on `victoryCardId` for count calculations

2. **Counting Strategy**:
   - Option 1: Store denormalized count on victory card (faster reads, requires update logic)
   - Option 2: COUNT query on me_toos collection (slower, always accurate)
   - **Recommendation**: Use denormalized count with atomic increment/decrement

3. **Caching**: Consider caching Me Too counts on victory cards

---

## Use Cases

### Use Case 1: User finds relatable victory
1. User sees victory: "Quit my corporate job to freelance"
2. User clicks "Me Too" button
3. Victory saved to user's inspiration list
4. Victory owner sees count go up but receives no notification

### Use Case 2: User changes mind
1. User previously clicked Me Too
2. User clicks button again (toggle off)
3. Victory removed from inspiration list
4. Count decrements

### Use Case 3: User browses inspirations
1. User goes to profile → Inspirations tab
2. Sees list of all victories they Me Too'd
3. Can click to view full victory details
4. Acts as a personal vision board

---

## Testing Checklist

- [ ] Can toggle Me Too on/off successfully
- [ ] Me Too count increments/decrements correctly
- [ ] Cannot create duplicate Me Too (unique constraint works)
- [ ] hasUserMeTooed reflects current user's state
- [ ] Can Me Too own victory (allowed)
- [ ] Inspirations list returns correct victories
- [ ] Pagination works for inspirations
- [ ] Toggle works multiple times (on/off/on)
- [ ] No notification sent when receiving Me Too
- [ ] Count remains accurate after multiple toggles

---

## Example Flow

1. User completes milestone → shares to Victory Wall
2. Another user views victory → clicks "Me Too" button (👥)
3. Button state changes to "Me Too ✓"
4. Victory is saved to their Inspirations list
5. Count increments: "24 → 25 Me Too"
6. Victory owner sees updated count (but no notification)
7. User can later click again to remove from inspirations

---

## Notes

- Me Too is intentionally minimal - no notifications, no points
- The value proposition is organizing inspirations, not validation
- This prevents notification spam while still providing engagement
- Future enhancement: Filter feed by "People like me" using Me Too data
- Future enhancement: Show "89 women are on this journey with you" on poster's dashboard
