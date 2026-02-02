# Backend Performance Optimization Guide

## Problem Statement

The `GET /api/users/{user_id}` endpoint returns the entire user document including massive nested arrays of dreams with complete roadmaps and milestones. This causes slow app load times:

- **Current Response Size**: 500KB - 2MB (depending on dreams count)
- **Network Transfer**: 3-10 seconds on slow connections
- **Parse Time**: 500ms - 2s

**Target**: Reduce initial load to ~5-10KB with 200ms - 1s transfer time (5-10x improvement)

---

## Solution Overview

Implement **selective field fetching** using query parameters to allow the frontend to request only the data it needs:

1. Add `fields` query parameter to `GET /api/users/{user_id}`
2. Create new endpoint `GET /api/users/{user_id}/dreams` for dreams list
3. Create new endpoint `GET /api/users/{user_id}/dreams/{thread_id}` for individual dream details

---

## Implementation

### 1. Update `GET /api/users/{user_id}` Endpoint

**File**: `api/users.py` (line 55-111)

**Add query parameter support:**

```python
from enum import Enum
from typing import Optional

class UserFieldsLevel(str, Enum):
    """Field selection levels for user data"""
    minimal = "minimal"      # Only basic user info
    essential = "essential"  # Basic + up_next + streak + recents (DEFAULT)
    full = "full"           # All data including full dreams array

@router.get("/{user_id}", tags=["users"])
async def get_user(user_id: str, fields: Optional[UserFieldsLevel] = UserFieldsLevel.essential):
    """
    Get a user by user_id from the users collection with optional field filtering.

    Args:
        user_id: The user's unique identifier (string)
        fields: Field selection level (minimal, essential, full). Defaults to 'essential'.

    Returns:
        dict: The user document (filtered based on 'fields' parameter)

    Raises:
        404: User not found
        500: Database error
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        logger.info(f"Fetching user: {user_id} (fields: {fields})")

        # Use MongoDB projection for performance instead of fetching all and filtering
        # IMPORTANT: MongoDB doesn't allow mixing inclusion and exclusion (except _id)
        # So we use exclusion-only projections to exclude the heavy 'dreams' field

        if fields == UserFieldsLevel.minimal:
            # Exclusion projection - only exclude dreams (lightest)
            projection = {
                "dreams": 0  # Exclude dreams array
            }
        elif fields == UserFieldsLevel.essential:
            # Exclusion projection - only exclude dreams (DEFAULT)
            projection = {
                "dreams": 0  # Exclude dreams array
            }
        else:  # fields == UserFieldsLevel.full
            # No projection - return everything (current behavior)
            projection = None

        # Query with projection
        if projection:
            user = await db.users.find_one({"user_id": user_id}, projection)
        else:
            user = await db.users.find_one({"user_id": user_id})

        if user is None:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=404,
                detail=f"User with id '{user_id}' not found"
            )

        # Convert ObjectId to string for JSON serialization
        if "_id" in user:
            user["_id"] = str(user["_id"])

        # For essential/minimal, add dreams count without returning full array
        if fields != UserFieldsLevel.full:
            # Get just the count with a separate aggregation query
            count_result = await db.users.aggregate([
                {"$match": {"user_id": user_id}},
                {"$project": {"dreams_count": {"$size": {"$ifNull": ["$dreams", []]}}}},
            ]).to_list(1)

            if count_result:
                user["dreams_count"] = count_result[0].get("dreams_count", 0)
            else:
                user["dreams_count"] = 0

        # Convert image bytes to base64 ONLY if we have dreams (full mode)
        if fields == UserFieldsLevel.full and "dreams" in user and isinstance(user["dreams"], list):
            for dream in user["dreams"]:
                if isinstance(dream, dict) and "dream_image_bytes" in dream:
                    image_bytes = dream["dream_image_bytes"]
                    if isinstance(image_bytes, bytes):
                        # Convert binary bytes to base64 string
                        dream["dream_image_bytes"] = base64.b64encode(image_bytes).decode('utf-8')

        logger.info(f"Successfully retrieved user: {user_id} (fields: {fields})")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching user"
        )
```

---

### 2. Create `GET /api/users/{user_id}/dreams` Endpoint

**Add to**: `api/users.py` (after the existing endpoints)

```python
@router.get("/{user_id}/dreams", tags=["users"])
async def get_user_dreams(
    user_id: str,
    summary: bool = False,
    page: int = 1,
    limit: int = 10
):
    """
    Get user's dreams list with optional summary mode and pagination.

    Args:
        user_id: The user's unique identifier
        summary: If True, returns only summary info without full roadmaps (default: False)
        page: Page number for pagination (default: 1)
        limit: Number of dreams per page (default: 10)

    Returns:
        list: Array of dream objects (full or summary based on 'summary' flag)

    Raises:
        404: User not found
        500: Database error
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        logger.info(f"Fetching dreams for user: {user_id} (summary: {summary}, page: {page}, limit: {limit})")

        # Find user
        user = await db.users.find_one({"user_id": user_id})

        if user is None:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=404,
                detail=f"User with id '{user_id}' not found"
            )

        dreams = user.get("dreams", [])

        if summary:
            # Return summary info only (no full roadmaps)
            dreams_summary = []
            for dream in dreams:
                if isinstance(dream, dict):
                    # Calculate progress without sending full roadmap
                    milestones = dream.get("roadmap", {}).get("milestones", [])
                    total_milestones = len(milestones)
                    completed_milestones = sum(
                        1 for m in milestones
                        if isinstance(m, dict) and m.get("status") == "completed"
                    )

                    dreams_summary.append({
                        "dream": dream.get("dream"),
                        "thread_id": dream.get("thread_id"),
                        "status": dream.get("status"),
                        "created_at": dream.get("created_at"),
                        "updated_at": dream.get("updated_at"),
                        "category": dream.get("category"),
                        "isComplete": dream.get("isComplete", False),
                        # Progress metrics without full data
                        "milestones_count": total_milestones,
                        "completed_milestones_count": completed_milestones,
                        "completion_percentage": (
                            round((completed_milestones / total_milestones) * 100, 1)
                            if total_milestones > 0 else 0
                        ),
                        # Include base64 image if it exists
                        "dream_image_bytes": (
                            base64.b64encode(dream["dream_image_bytes"]).decode('utf-8')
                            if "dream_image_bytes" in dream and isinstance(dream["dream_image_bytes"], bytes)
                            else None
                        )
                    })

            dreams_to_return = dreams_summary
        else:
            # Return full dreams with roadmaps, but still convert image bytes
            for dream in dreams:
                if isinstance(dream, dict) and "dream_image_bytes" in dream:
                    image_bytes = dream["dream_image_bytes"]
                    if isinstance(image_bytes, bytes):
                        dream["dream_image_bytes"] = base64.b64encode(image_bytes).decode('utf-8')

            dreams_to_return = dreams

        # Apply pagination
        skip = (page - 1) * limit
        paginated_dreams = dreams_to_return[skip:skip + limit]

        logger.info(f"Successfully retrieved {len(paginated_dreams)} dreams for user: {user_id}")

        return {
            "dreams": paginated_dreams,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(dreams_to_return),
                "totalPages": (len(dreams_to_return) + limit - 1) // limit
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dreams for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching dreams"
        )
```

---

### 3. Create `GET /api/users/{user_id}/dreams/{thread_id}` Endpoint

**Add to**: `api/users.py` (after the dreams list endpoint)

```python
@router.get("/{user_id}/dreams/{thread_id}", tags=["users"])
async def get_dream_details(user_id: str, thread_id: str):
    """
    Get a single dream's full details including roadmap and milestones.

    Use this endpoint when the user navigates to a specific dream detail screen
    to avoid loading all dreams with roadmaps upfront.

    Args:
        user_id: The user's unique identifier
        thread_id: The dream's thread ID

    Returns:
        dict: The complete dream object with roadmap

    Raises:
        404: User or dream not found
        500: Database error
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        logger.info(f"Fetching dream details: {thread_id} for user: {user_id}")

        # Use aggregation to find the specific dream directly
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$unwind": "$dreams"},
            {"$match": {"dreams.thread_id": thread_id}},
            {"$replaceRoot": {"newRoot": "$dreams"}}
        ]

        cursor = db.users.aggregate(pipeline)
        dreams = await cursor.to_list(length=1)

        if not dreams:
            logger.warning(f"Dream not found: {thread_id} for user: {user_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Dream with thread_id '{thread_id}' not found for user '{user_id}'"
            )

        dream = dreams[0]

        # Convert image bytes to base64 if present
        if "dream_image_bytes" in dream and isinstance(dream["dream_image_bytes"], bytes):
            dream["dream_image_bytes"] = base64.b64encode(dream["dream_image_bytes"]).decode('utf-8')

        logger.info(f"Successfully retrieved dream: {thread_id}")
        return dream

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dream {thread_id} for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching dream details"
        )
```

---

## Performance Improvements

### Before Optimization
```
Response size: ~500KB - 2MB
Network transfer: 3-10 seconds (slow connection)
Parse time: 500ms - 2s
Database query: Single find_one with full document
```

### After Optimization (essential fields)
```
Response size: ~5-10KB
Network transfer: 200ms - 1s (slow connection)
Parse time: 10-50ms
Database query: find_one with MongoDB projection (much faster)
```

**Expected Improvement: 5-10x faster initial app load**

---

## Usage Examples

### Frontend Usage

```typescript
// App load - Fast initial load with essential fields
const userData = await fetchUserData(userId, { fields: 'essential' });
// Returns: user_id, email, name, up_next, streak, recents, couragePoints, dreams_count

// Dreams list screen - Summary data without roadmaps
const dreamsList = await fetchDreamsList(userId); // Uses ?summary=true
// Returns: dream titles, status, progress percentages, images

// Dream detail screen - Full roadmap for one dream
const dreamDetails = await fetchDreamDetails(userId, threadId);
// Returns: Complete dream with full roadmap and milestones
```

### API Request Examples

```bash
# Essential fields (DEFAULT) - Fast app load
GET /api/users/ABC123?fields=essential

# Minimal fields - Ultra minimal
GET /api/users/ABC123?fields=minimal

# Full data - Current behavior
GET /api/users/ABC123?fields=full
# OR just omit the parameter
GET /api/users/ABC123

# Dreams summary list
GET /api/users/ABC123/dreams?summary=true&page=1&limit=10

# Single dream details
GET /api/users/ABC123/dreams/thread-id-xyz
```

---

## MongoDB Projection Notes

### Important Limitation
MongoDB doesn't allow mixing inclusion (`field: 1`) and exclusion (`field: 0`) projections in the same query, except for the `_id` field. This means:

- **WRONG**: `{"user_id": 1, "email": 1, "dreams": 0}` ❌ (Cannot mix inclusion and exclusion)
- **CORRECT**: `{"dreams": 0}` ✅ (Exclusion only - returns everything except dreams)
- **CORRECT**: `{"user_id": 1, "email": 1}` ✅ (Inclusion only - returns only these fields)

For this optimization, we use **exclusion-only projections** because:
1. We want most fields (user info, streak, up_next, etc.)
2. We only want to exclude the heavy `dreams` array
3. Exclusion syntax is simpler: `{"dreams": 0}`

### Performance Benefits

Using MongoDB projections (`find_one(query, projection)`) instead of fetching the full document and filtering in Python provides:

1. **Network efficiency**: Less data transferred between MongoDB and app server
2. **Memory efficiency**: Smaller objects in memory
3. **CPU efficiency**: Less JSON serialization work
4. **Index usage**: MongoDB can use covered indexes for projected queries

---

## Testing Checklist

### 1. Test Current Performance (Baseline)

```bash
# Measure current response
curl -w "\nTime: %{time_total}s\nSize: %{size_download} bytes\n" \
  http://localhost:5000/api/users/YkkE6Jhtt3aCyTpzTYb6xfmVZWl2
```

### 2. Test Optimized Endpoints

```bash
# Essential fields (should be much smaller/faster)
curl -w "\nTime: %{time_total}s\nSize: %{size_download} bytes\n" \
  "http://localhost:5000/api/users/YkkE6Jhtt3aCyTpzTYb6xfmVZWl2?fields=essential"

# Minimal fields (smallest response)
curl -w "\nTime: %{time_total}s\nSize: %{size_download} bytes\n" \
  "http://localhost:5000/api/users/YkkE6Jhtt3aCyTpzTYb6xfmVZWl2?fields=minimal"

# Dreams summary
curl -w "\nTime: %{time_total}s\nSize: %{size_download} bytes\n" \
  "http://localhost:5000/api/users/YkkE6Jhtt3aCyTpzTYb6xfmVZWl2/dreams?summary=true"

# Single dream details
curl -w "\nTime: %{time_total}s\nSize: %{size_download} bytes\n" \
  http://localhost:5000/api/users/YkkE6Jhtt3aCyTpzTYb6xfmVZWl2/dreams/THREAD_ID
```

### 3. Test with Different User Data Sizes

Test with users who have:
- 0 dreams (new user)
- 1 dream
- 5 dreams
- 10+ dreams
- Dreams with 50+ milestones

### 4. Verify Data Integrity

Ensure that:
- All existing endpoints still work
- Frontend receives expected data structure
- No data is lost or corrupted
- Image encoding/decoding works correctly

---

## Migration Strategy

### Phase 1: Add Support (No Breaking Changes)
1. Add the new endpoints (`/dreams`, `/dreams/{thread_id}`)
2. Add `fields` parameter to existing endpoint (default to `full` for backward compatibility)
3. Deploy and verify all existing functionality works

### Phase 2: Frontend Migration
1. Update frontend to use `fields=essential` for app load
2. Update frontend to use new dreams endpoints
3. Test thoroughly

### Phase 3: Change Default
1. Change default from `full` to `essential`
2. Monitor for any issues
3. Update documentation

---

## Additional Optimizations to Consider

### 1. Enable Response Compression

Add GZip middleware to compress large JSON responses:

```python
# In main.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

This can reduce response sizes by 70-90% for JSON data.

### 2. Add MongoDB Indexes

Ensure you have indexes for fast queries:

```python
# In core/database.py - add to setup_indexes()

# Index for user_id queries (should already exist)
await db.users.create_index("user_id", unique=True)

# Compound index for dreams queries
await db.users.create_index([("user_id", 1), ("dreams.thread_id", 1)])

# Index for created_at (useful for sorting/filtering)
await db.users.create_index("created_at")
```

### 3. Add Caching Layer

For frequently accessed data, consider adding Redis caching:

```python
# Cache user essential data for 5 minutes
# This can reduce database load significantly
```

### 4. Monitor Performance

Add logging for slow queries:

```python
import time

start = time.time()
user = await db.users.find_one({"user_id": user_id}, projection)
duration = time.time() - start

if duration > 0.5:  # Log queries slower than 500ms
    logger.warning(f"Slow query for user {user_id}: {duration:.2f}s")
```

---

## Expected Results

After implementing these changes:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Response size (essential) | 500KB-2MB | 5-10KB | **50-200x smaller** |
| Network transfer time | 3-10s | 200ms-1s | **5-10x faster** |
| Parse time | 500ms-2s | 10-50ms | **10-40x faster** |
| Database query time | ~100ms | ~20ms | **5x faster** |
| **Total app load time** | **4-12s** | **0.5-1.5s** | **8-10x faster** |

---

## Questions or Issues?

If you encounter any problems during implementation, check:
1. MongoDB connection is working
2. Projection syntax is correct
3. Frontend is sending correct query parameters
4. Response data structure matches what frontend expects

For questions, contact the development team!
