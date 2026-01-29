# Backend API Specification: Permission Slips (Phase 2)

## Overview

Permission Slips allow users to give templated, encouraging responses to Victory Cards. This feature adds deeper community engagement beyond simple courage boosts.

---

## Database Schema

### New Collection: `permission_slips`

```javascript
{
  _id: ObjectId,
  victoryCardId: ObjectId,          // Reference to victory_cards collection
  giverId: ObjectId,                // User who gave the permission
  giverDisplayName: String,         // "Sarah" or "Anonymous"
  receiverId: ObjectId,             // Victory card owner
  permissionType: Number,           // 1, 2, 3, or 4
  permissionText: String,           // The actual permission statement
  createdAt: Date,

  // Indexes
  index: { victoryCardId: 1, createdAt: -1 },
  index: { receiverId: 1, createdAt: -1 },
  index: { giverId: 1 }
}
```

### Updates to Existing Collections

**`victory_cards` collection - add field:**
```javascript
{
  // ... existing fields ...
  permissionsCount: Number,         // Count of permissions received (default: 0)
}
```

**`users` collection - add field:**
```javascript
{
  // ... existing fields ...
  communityStats: {
    // ... existing stats ...
    permissionsGiven: Number,       // Total permissions granted to others (default: 0)
    permissionsReceived: Number     // Total permissions received (default: 0)
  }
}
```

---

## API Endpoints

### 1. Give Permission Slip

**Endpoint:** `POST /api/victories/:victoryId/permission`

**Description:** Grant a permission slip to a victory card.

**Request Body:**
```json
{
  "permissionType": 1  // 1, 2, 3, or 4
}
```

**Success Response (200):**
```json
{
  "success": true,
  "permissionText": "Permission granted to keep going",
  "couragePointsAwarded": 5
}
```

**Error Responses:**
- `400` - Invalid permission type or missing victoryId
- `404` - Victory card not found
- `409` - User already gave a permission to this victory (one per user per victory)
- `500` - Server error

**Business Logic:**
1. Validate `permissionType` is 1, 2, 3, or 4
2. Validate victory card exists
3. Check user hasn't already given a permission to this victory (one per user per victory)
4. Get victory card's dream category
5. Generate `permissionText` based on type and category:
   - Type 1: "Permission granted to keep going"
   - Type 2: "Permission granted to be proud of this"
   - Type 3: "Permission granted to inspire the rest of us"
   - Type 4: Dynamic based on category (see mapping below)
6. Create permission slip document
7. Increment `permissionsCount` on victory card (+1)
8. Add +5 courage points to receiver's account
9. Increment `permissionsGiven` stat for giver
10. Increment `permissionsReceived` stat for receiver
11. (Optional) Send push notification to receiver: "Sarah granted you permission! +5 courage points"

**Type 4 Category Mapping:**
```javascript
const categoryPermissions = {
  'career_professional': 'Permission granted to call yourself a leader',
  'personal_development': 'Permission granted to call yourself a learner',
  'health_wellness': 'Permission granted to call yourself an athlete',
  'creative_expression': 'Permission granted to call yourself a creator',
  'relationships_community': 'Permission granted to call yourself a connector',
  'travel_exploration': 'Permission granted to call yourself a traveler',
  'finance_security': 'Permission granted to call yourself financially savvy',
  'lifestyle_hobbies': 'Permission granted to call yourself dedicated',
  'courage_challenges': 'Permission granted to call yourself brave',
  'achievement_goals': 'Permission granted to call yourself a champion'
};
```

---

### 2. Get Victory Permissions

**Endpoint:** `GET /api/victories/:victoryId/permissions`

**Description:** Retrieve all permission slips for a victory card.

**Query Parameters:**
- `limit` (optional): Number of permissions to return (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Success Response (200):**
```json
{
  "permissions": [
    {
      "id": "perm_123",
      "giverDisplayName": "Sarah",
      "permissionText": "Permission granted to call yourself a traveler",
      "createdAt": "2026-01-28T14:30:00Z"
    },
    {
      "id": "perm_124",
      "giverDisplayName": "Anonymous",
      "permissionText": "Permission granted to be proud of this",
      "createdAt": "2026-01-28T12:15:00Z"
    }
  ],
  "count": 5,
  "total": 5
}
```

**Error Responses:**
- `404` - Victory card not found
- `500` - Server error

**Business Logic:**
1. Validate victory card exists
2. Query permission slips by `victoryCardId`
3. Sort by `createdAt` descending (newest first)
4. Apply pagination (limit & offset)
5. Return list with total count

---

### 3. Update Victory Card Response (Enhancement)

**Endpoint:** `GET /api/victories`

**Description:** Include `permissionsCount` in victory card responses.

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
  "permissionsCount": 5,  // NEW FIELD
  "isAnonymous": false
}
```

---

## Validation Rules

1. **One Permission Per User Per Victory**: A user can only give one permission slip to each victory card. If they try again, return 409 error.

2. **Permission Type Validation**: Must be 1, 2, 3, or 4. Any other value returns 400 error.

3. **Anonymous Mode**: If user has anonymous mode enabled, use "Anonymous" as `giverDisplayName`.

4. **Self-Permission Prevention**: Users cannot give permissions to their own victory cards (return 400 error).

---

## Points System

- **Receiver**: +5 courage points per permission received
- **Giver**: No points (pure generosity mechanic)

---

## Notifications (Optional for Phase 2)

When a user receives a permission:
```
Title: "Permission Granted! 💬"
Body: "Sarah granted you permission! +5 courage points"
```

---

## Performance Considerations

1. **Indexing**:
   - Index on `victoryCardId` for fast permission lookups
   - Index on `receiverId` for user stats

2. **Caching**: Consider caching permission counts on victory cards to avoid counting queries.

3. **Rate Limiting**: Limit permission grants to prevent spam (e.g., max 50 permissions per user per day).

---

## Testing Checklist

- [ ] Can give permission type 1, 2, 3, 4 successfully
- [ ] Cannot give permission to own victory
- [ ] Cannot give duplicate permission to same victory
- [ ] Permission count increments on victory card
- [ ] Courage points awarded correctly (+5)
- [ ] User stats update (permissionsGiven, permissionsReceived)
- [ ] Anonymous mode respected for giver name
- [ ] Type 4 generates correct category-specific text
- [ ] Permissions list returns in correct order (newest first)
- [ ] Pagination works correctly

---

## Example Flow

1. User completes milestone → shares to Victory Wall
2. Another user views victory card → clicks "Give Permission" button
3. Modal shows 4 permission options
4. User selects type 4: "Permission granted to call yourself a traveler"
5. Backend creates permission slip, awards +5 courage points
6. Victory card now shows "5 Permissions Granted"
7. User can click to view all permissions in list modal

---

## Notes

- Permission slips are permanent (no delete functionality)
- Permissions are public (anyone can view them)
- Consider adding moderation if spam becomes an issue
- Future: Add ability to "highlight" favorite permissions on profile
