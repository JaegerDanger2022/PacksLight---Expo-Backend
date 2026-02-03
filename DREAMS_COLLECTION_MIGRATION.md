# Dreams Collection Migration Plan

## Overview

Migrate from **embedded dreams array** in users collection to a **separate dreams collection** with a hybrid approach that maintains lightweight summaries in the user document.

**Goal**: 5-10x faster app load while maintaining existing Zustand structure (minimal frontend changes).

---

## Architecture

### Before (Current)
```
users collection:
  - user_id: "ABC123"
  - email: "user@example.com"
  - dreams: [
      {
        thread_id: "xyz",
        dream: "Launch a business",
        status: "active",
        dream_image_bytes: <500KB binary>,
        roadmap: {
          milestones: [ {...}, {...}, ... ]  // 50+ milestones
        }
      },
      // ... more dreams (can be 500KB-2MB total)
    ]
```

### After (Hybrid - Option 2)
```
users collection:
  - user_id: "ABC123"
  - email: "user@example.com"
  - dreams_summary: [  // Lightweight summary only
      {
        thread_id: "xyz",
        dream: "Launch a business",
        status: "active",
        dream_image_bytes: <base64 string>,  // Include image
        created_at: "2026-01-15T...",
        updated_at: "2026-01-20T...",
        milestones_count: 25,
        completed_milestones_count: 5
      },
      // ... (~50KB total for 10 dreams)
    ]

dreams collection:  // NEW - Full dream data
  - _id: ObjectId
  - user_id: "ABC123"  // Indexed
  - thread_id: "xyz"   // Unique indexed
  - dream: "Launch a business"
  - status: "active"
  - dream_image_bytes: <binary>
  - roadmap: {
      milestones: [ {...}, {...}, ... ]  // Full data
    }
  - created_at: datetime
  - updated_at: datetime
```

---

## Benefits

✅ **Fast App Load**: User + dreams_summary = ~50-60KB (vs 500KB-2MB)
✅ **Minimal Frontend Changes**: Zustand structure remains the same
✅ **Scalability**: No 16MB document limit
✅ **Flexible Queries**: Can query dreams independently
✅ **Cost**: Only ~$0.01-0.04/month more per 1,000 users

---

## Phase 1: Database Setup

### 1.1 Create Dreams Collection and Indexes

**File**: `core/database.py`

Add to `setup_indexes()` function:

```python
async def setup_indexes():
    # ... existing indexes ...

    # ============= DREAMS COLLECTION INDEXES =============
    logger.info("[DB] Creating index: dreams.user_id")
    await db.dreams.create_index("user_id")
    logger.info("[DB] Index created: dreams.user_id")

    logger.info("[DB] Creating index: dreams.thread_id (unique)")
    await db.dreams.create_index("thread_id", unique=True)
    logger.info("[DB] Index created: dreams.thread_id")

    logger.info("[DB] Creating compound index: dreams (user_id, status)")
    await db.dreams.create_index([("user_id", 1), ("status", 1)])
    logger.info("[DB] Index created: dreams (user_id, status)")

    logger.info("[DB] Creating compound index: dreams (user_id, updated_at)")
    await db.dreams.create_index([("user_id", 1), ("updated_at", -1)])
    logger.info("[DB] Index created: dreams (user_id, updated_at)")
```

### 1.2 Dreams Collection Schema

```python
{
  "_id": ObjectId,
  "user_id": str,              # Firebase UID
  "thread_id": str,            # Unique identifier from LangGraph
  "dream": str,                # Dream title/description
  "status": str,               # "active" | "completed"
  "dream_image_bytes": bytes,  # Binary image data
  "roadmap": {                 # Full roadmap with all milestones
    "milestones": [
      {
        "id": str,
        "title": str,
        "status": str,
        "description": str,
        "xp_points": int,
        # ... all other milestone fields
      }
    ]
  },
  "created_at": datetime,
  "updated_at": datetime,
  "category": str,             # Optional: dream category
  "isComplete": bool           # Whether all milestones are done
}
```

---

## Phase 2: Data Migration

### 2.1 Create Migration Script

**New File**: `scripts/migrate_dreams_to_collection.py`

```python
"""
Migration script to move dreams from users.dreams array to separate dreams collection.
This creates a dreams_summary in users collection for fast loading.
"""

import asyncio
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
import os
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dream_to_do")

async def migrate_dreams():
    """Migrate dreams from embedded array to separate collection"""

    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    logger.info("Starting dreams migration...")

    # Get all users with dreams
    users = await db.users.find({"dreams": {"$exists": True, "$ne": []}}).to_list(None)
    logger.info(f"Found {len(users)} users with dreams")

    total_dreams_migrated = 0
    users_updated = 0
    errors = []

    for user in users:
        try:
            user_id = user["user_id"]
            dreams = user.get("dreams", [])

            if not dreams:
                continue

            logger.info(f"Processing user {user_id} with {len(dreams)} dreams")

            # Prepare dreams for insertion into dreams collection
            dreams_to_insert = []
            dreams_summary = []

            for dream in dreams:
                thread_id = dream.get("thread_id")

                if not thread_id:
                    logger.warning(f"Skipping dream without thread_id for user {user_id}")
                    continue

                # Check if dream already exists in dreams collection
                existing_dream = await db.dreams.find_one({"thread_id": thread_id})

                if existing_dream:
                    logger.info(f"Dream {thread_id} already exists in dreams collection, skipping")
                else:
                    # Prepare full dream document for dreams collection
                    dream_doc = {
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "dream": dream.get("dream", ""),
                        "status": dream.get("status", "active"),
                        "dream_image_bytes": dream.get("dream_image_bytes"),  # Keep as binary
                        "roadmap": dream.get("roadmap", {}),
                        "created_at": dream.get("created_at", datetime.now(timezone.utc)),
                        "updated_at": dream.get("updated_at", datetime.now(timezone.utc)),
                        "category": dream.get("category"),
                        "isComplete": dream.get("isComplete", False)
                    }

                    dreams_to_insert.append(dream_doc)

                # Create lightweight summary for user document
                # Calculate milestone counts
                milestones = dream.get("roadmap", {}).get("milestones", [])
                total_milestones = len(milestones)
                completed_milestones = sum(
                    1 for m in milestones
                    if isinstance(m, dict) and m.get("status") == "completed"
                )

                # Convert image bytes to base64 for summary
                image_base64 = None
                if "dream_image_bytes" in dream and isinstance(dream["dream_image_bytes"], bytes):
                    image_base64 = base64.b64encode(dream["dream_image_bytes"]).decode('utf-8')

                summary = {
                    "thread_id": thread_id,
                    "dream": dream.get("dream", ""),
                    "status": dream.get("status", "active"),
                    "dream_image_bytes": image_base64,  # Base64 string for JSON
                    "created_at": dream.get("created_at"),
                    "updated_at": dream.get("updated_at"),
                    "milestones_count": total_milestones,
                    "completed_milestones_count": completed_milestones,
                    "isComplete": dream.get("isComplete", False)
                }

                dreams_summary.append(summary)

            # Insert dreams into dreams collection
            if dreams_to_insert:
                try:
                    await db.dreams.insert_many(dreams_to_insert, ordered=False)
                    total_dreams_migrated += len(dreams_to_insert)
                    logger.info(f"Inserted {len(dreams_to_insert)} dreams for user {user_id}")
                except Exception as e:
                    logger.error(f"Error inserting dreams for user {user_id}: {e}")
                    errors.append(f"User {user_id}: {str(e)}")
                    continue

            # Update user document with dreams_summary
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "dreams_summary": dreams_summary,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            users_updated += 1
            logger.info(f"Updated user {user_id} with dreams_summary")

        except Exception as e:
            logger.error(f"Error processing user {user.get('user_id', 'unknown')}: {e}")
            errors.append(f"User {user.get('user_id', 'unknown')}: {str(e)}")

    # Summary
    logger.info("=" * 60)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total users processed: {len(users)}")
    logger.info(f"Users updated: {users_updated}")
    logger.info(f"Total dreams migrated: {total_dreams_migrated}")
    logger.info(f"Errors: {len(errors)}")

    if errors:
        logger.error("Errors encountered:")
        for error in errors:
            logger.error(f"  - {error}")

    logger.info("=" * 60)
    logger.info("Migration completed!")
    logger.info("=" * 60)

    # Close connection
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_dreams())
```

### 2.2 Run Migration

```bash
# Test on staging first!
python scripts/migrate_dreams_to_collection.py

# Verify data integrity
# - Check dreams collection has all dreams
# - Check users have dreams_summary
# - Verify image data is intact
```

### 2.3 Rollback Plan (If Needed)

**File**: `scripts/rollback_dreams_migration.py`

```python
"""
Rollback script to restore dreams array in users collection from dreams collection.
Only use if migration fails or needs to be reversed.
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dream_to_do")

async def rollback_migration():
    """Restore dreams array from dreams collection back to users"""

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    logger.info("Starting rollback...")

    # Get all users
    users = await db.users.find({}).to_list(None)

    for user in users:
        user_id = user["user_id"]

        # Fetch user's dreams from dreams collection
        dreams = await db.dreams.find({"user_id": user_id}).to_list(None)

        if dreams:
            # Convert back to embedded format
            dreams_array = []
            for dream in dreams:
                dream_doc = dream.copy()
                dream_doc.pop("_id", None)
                dream_doc.pop("user_id", None)
                dreams_array.append(dream_doc)

            # Restore dreams array in user document
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"dreams": dreams_array}}
            )

            logger.info(f"Restored {len(dreams_array)} dreams for user {user_id}")

    logger.info("Rollback completed!")
    client.close()

if __name__ == "__main__":
    asyncio.run(rollback_migration())
```

---

## Phase 3: Backend API Updates

### 3.1 New Dreams API Endpoints

**New File**: `api/dreams_crud.py`

See `DREAMS_API_ENDPOINTS.md` for full implementation.

Key endpoints:
- `GET /api/dreams?user_id={userId}` - Get all dreams for a user
- `GET /api/dreams/{thread_id}` - Get single dream by thread_id
- `PUT /api/dreams/{thread_id}` - Update dream
- `DELETE /api/dreams/{thread_id}` - Delete dream

### 3.2 Update Existing Endpoints

#### Update `GET /api/users/{user_id}`

**File**: `api/users.py`

```python
@router.get("/{user_id}", tags=["users"])
async def get_user(user_id: str):
    """
    Get user with dreams_summary (not full dreams array).

    Returns user with:
    - All user fields
    - dreams_summary array (lightweight, ~50KB)
    - NOT the old dreams array (deprecated)
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        logger.info(f"Fetching user: {user_id}")

        # Exclude old dreams array, include dreams_summary
        projection = {
            "dreams": 0  # Exclude old embedded dreams array
        }

        user = await db.users.find_one({"user_id": user_id}, projection)

        if user is None:
            raise HTTPException(status_code=404, detail=f"User with id '{user_id}' not found")

        # Convert ObjectId to string
        if "_id" in user:
            user["_id"] = str(user["_id"])

        # dreams_summary already has base64 images from migration

        logger.info(f"Successfully retrieved user: {user_id}")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

#### Update Dream Creation

**File**: `api/dreams.py`

Modify the `create_dream` endpoint to:
1. Create dream in dreams collection
2. Add summary to user's dreams_summary array

```python
# After creating dream via LangGraph...

# Insert into dreams collection
dream_doc = {
    "user_id": user_id,
    "thread_id": thread_id,
    "dream": dream_title,
    "status": "active",
    "dream_image_bytes": image_bytes,
    "roadmap": roadmap,
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc)
}

await db.dreams.insert_one(dream_doc)

# Add to user's dreams_summary
summary = {
    "thread_id": thread_id,
    "dream": dream_title,
    "status": "active",
    "dream_image_bytes": base64.b64encode(image_bytes).decode('utf-8'),
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "milestones_count": len(roadmap.get("milestones", [])),
    "completed_milestones_count": 0
}

await db.users.update_one(
    {"user_id": user_id},
    {"$push": {"dreams_summary": summary}}
)
```

#### Update Milestone Status

**File**: `api/milestone.py`

When updating milestone status, update BOTH:
1. Dreams collection (full data)
2. User's dreams_summary (milestone counts)

```python
# Update milestone in dreams collection
await db.dreams.update_one(
    {"thread_id": thread_id, "roadmap.milestones.id": milestone_id},
    {"$set": {
        "roadmap.milestones.$.status": status,
        "updated_at": datetime.now(timezone.utc)
    }}
)

# Recalculate milestone counts
dream = await db.dreams.find_one({"thread_id": thread_id})
milestones = dream["roadmap"]["milestones"]
completed_count = sum(1 for m in milestones if m["status"] == "completed")

# Update dreams_summary in user document
await db.users.update_one(
    {"user_id": user_id, "dreams_summary.thread_id": thread_id},
    {"$set": {
        "dreams_summary.$.completed_milestones_count": completed_count,
        "dreams_summary.$.updated_at": datetime.now(timezone.utc).isoformat()
    }}
)
```

---

## Phase 4: Frontend Updates (Minimal!)

### 4.1 Update fetchUserData to Handle dreams_summary

**File**: `src/config/api.ts`

The current `fetchUserData` already works! Just ensure the response includes `dreams_summary`:

```typescript
// No changes needed - backend now returns dreams_summary instead of dreams
// Frontend will receive dreams_summary in userData.dreams_summary
```

### 4.2 Update Zustand Store to Map dreams_summary → dreams

**File**: `src/store/authStore.ts`

Add a helper to map `dreams_summary` to `dreams` format for backward compatibility:

```typescript
// Helper function to maintain backward compatibility
const mapDreamsSummaryToDreams = (userData: UserData): UserData => {
  if (userData.dreams_summary && !userData.dreams) {
    // Map dreams_summary to dreams format for existing code
    userData.dreams = userData.dreams_summary.map((summary: any) => ({
      thread_id: summary.thread_id,
      dream: summary.dream,
      status: summary.status,
      dream_image_bytes: summary.dream_image_bytes,
      created_at: summary.created_at,
      updated_at: summary.updated_at,
      // Add placeholder roadmap with milestone counts
      roadmap: {
        milestones: Array(summary.milestones_count).fill({})
      },
      isComplete: summary.isComplete
    }));
  }
  return userData;
};

// Use in initializeAuth, signUp, login, etc.
const userData = await fetchUserData(user.uid, { fields: 'essential' });
if (userData) {
  const mappedData = mapDreamsSummaryToDreams(userData);
  set({ userData: mappedData, loading: false });
}
```

### 4.3 Add Function to Fetch Full Dream Data

**File**: `src/config/api.ts`

Update `fetchDreamDetails` to use the new endpoint:

```typescript
export async function fetchDreamDetails(
  userId: string,
  threadId: string
): Promise<any> {
  try {
    console.log(`Fetching dream details for threadId: ${threadId}`);

    // Use new dreams collection endpoint
    const response = await fetch(
      `${API_BASE_URL}/dreams/${threadId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const dreamData = await response.json();
    console.log("Dream details fetched successfully");
    return dreamData;
  } catch (error: any) {
    console.error("Error fetching dream details:", error.message);
    throw error;
  }
}
```

---

## Phase 5: Testing & Validation

### 5.1 Pre-Migration Checklist

- [ ] Backup MongoDB database
- [ ] Test migration script on staging environment
- [ ] Verify all users have dreams migrated correctly
- [ ] Test new API endpoints
- [ ] Verify images are intact (both binary and base64)

### 5.2 Post-Migration Validation

```python
# Validation script
async def validate_migration():
    # 1. Check all dreams have user_id
    dreams_without_user = await db.dreams.count_documents({"user_id": {"$exists": False}})
    assert dreams_without_user == 0, "Some dreams missing user_id"

    # 2. Check all dreams have thread_id
    dreams_without_thread = await db.dreams.count_documents({"thread_id": {"$exists": False}})
    assert dreams_without_thread == 0, "Some dreams missing thread_id"

    # 3. Check users have dreams_summary
    users = await db.users.find({}).to_list(None)
    for user in users:
        old_dreams_count = len(user.get("dreams", []))
        new_summary_count = len(user.get("dreams_summary", []))

        if old_dreams_count > 0:
            assert new_summary_count == old_dreams_count, \
                f"User {user['user_id']}: dreams_summary count mismatch"

    # 4. Check image integrity
    dreams = await db.dreams.find({}).to_list(None)
    for dream in dreams:
        if "dream_image_bytes" in dream:
            assert isinstance(dream["dream_image_bytes"], bytes), \
                f"Dream {dream['thread_id']}: image should be bytes"

    print("✅ All validation checks passed!")
```

### 5.3 Performance Testing

```bash
# Before migration
curl -w "Time: %{time_total}s\nSize: %{size_download} bytes\n" \
  http://localhost:5000/api/users/USER_ID

# After migration
curl -w "Time: %{time_total}s\nSize: %{size_download} bytes\n" \
  http://localhost:5000/api/users/USER_ID

# Should see 5-10x reduction in size and time
```

---

## Phase 6: Cleanup (Optional - After 2 Weeks)

### 6.1 Remove Old dreams Array

Once you've verified everything works for 2+ weeks:

```python
# Remove old dreams array from users collection
async def cleanup_old_dreams_array():
    result = await db.users.update_many(
        {"dreams": {"$exists": True}},
        {"$unset": {"dreams": ""}}
    )
    print(f"Removed dreams array from {result.modified_count} users")
```

---

## Summary Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| 1. Database Setup | 1 hour | Create indexes, test on staging |
| 2. Migration | 2-4 hours | Run migration script, validate data |
| 3. Backend API | 4-6 hours | Update endpoints, test thoroughly |
| 4. Frontend | 2-3 hours | Minimal changes to support new structure |
| 5. Testing | 2-3 hours | Comprehensive testing, validation |
| 6. Deployment | 1 hour | Deploy to production, monitor |

**Total Estimate**: 1-2 days

---

## Expected Results

### Before
- User fetch: 500KB-2MB, 3-10s
- Can't paginate dreams
- Risk of hitting 16MB limit

### After
- User fetch: 50-60KB, 0.5-1s ⚡ **8-10x faster**
- Dreams lazy-loaded when needed
- Unlimited dreams per user
- Better scalability

---

## Support & Questions

If you encounter any issues during migration:
1. Check the validation script output
2. Verify indexes are created correctly
3. Test API endpoints with Postman/curl
4. Review migration logs for errors

Good luck with the migration! 🚀
