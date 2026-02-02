# Dreams Collection API Endpoints

Complete API specification for the new dreams collection endpoints.

---

## Base URL

```
/api/dreams
```

---

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dreams?user_id={userId}` | Get all dreams for a user |
| GET | `/dreams?user_id={userId}&status={status}` | Get dreams by status |
| GET | `/dreams/{thread_id}` | Get single dream by thread_id |
| PUT | `/dreams/{thread_id}` | Update dream (status, roadmap, etc.) |
| DELETE | `/dreams/{thread_id}` | Delete dream |
| GET | `/dreams/{thread_id}/milestones` | Get all milestones for a dream |
| GET | `/dreams/{thread_id}/milestones/{milestone_id}` | Get single milestone |

---

## 1. Get User's Dreams

### `GET /api/dreams?user_id={userId}`

Fetch all dreams for a specific user from the dreams collection.

**Query Parameters:**
- `user_id` (required): Firebase user ID
- `status` (optional): Filter by status ("active", "completed")
- `page` (optional): Page number for pagination (default: 1)
- `limit` (optional): Items per page (default: 10)
- `summary` (optional): If true, returns lightweight summary without full roadmaps

**Response:**

```json
{
  "dreams": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "user_id": "ABC123",
      "thread_id": "uuid-xyz",
      "dream": "Launch a profitable side business",
      "status": "active",
      "dream_image_bytes": "<base64 string>",
      "roadmap": {
        "milestones": [
          {
            "id": "m_0",
            "title": "Brainstorm business ideas",
            "status": "completed",
            "description": "...",
            "xp_points": 30
          }
        ]
      },
      "created_at": "2026-01-15T10:30:00Z",
      "updated_at": "2026-01-20T15:45:00Z",
      "category": "career",
      "isComplete": false
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 5,
    "totalPages": 1
  }
}
```

**Implementation:**

```python
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import base64

router = APIRouter()

@router.get("", tags=["dreams"])
async def get_user_dreams(
    user_id: str = Query(..., description="User ID to fetch dreams for"),
    status: Optional[str] = Query(None, description="Filter by status (active, completed)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    summary: bool = Query(False, description="Return summary without full roadmaps")
):
    """
    Get all dreams for a user from the dreams collection.

    Args:
        user_id: Firebase UID
        status: Optional status filter
        page: Page number for pagination
        limit: Number of items per page
        summary: If true, exclude full roadmaps

    Returns:
        List of dreams with pagination info
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Build query
        query = {"user_id": user_id}
        if status:
            query["status"] = status

        # Get total count
        total = await db.dreams.count_documents(query)

        # Calculate skip
        skip = (page - 1) * limit

        # Projection for summary mode
        projection = None
        if summary:
            projection = {
                "_id": 1,
                "user_id": 1,
                "thread_id": 1,
                "dream": 1,
                "status": 1,
                "created_at": 1,
                "updated_at": 1,
                "category": 1,
                "isComplete": 1,
                "dream_image_bytes": 1,
                # Exclude roadmap
                "roadmap": 0
            }

        # Fetch dreams
        cursor = db.dreams.find(query, projection).sort("updated_at", -1).skip(skip).limit(limit)
        dreams = await cursor.to_list(length=limit)

        # Convert ObjectId and binary image to base64
        for dream in dreams:
            if "_id" in dream:
                dream["_id"] = str(dream["_id"])

            if "dream_image_bytes" in dream and isinstance(dream["dream_image_bytes"], bytes):
                dream["dream_image_bytes"] = base64.b64encode(dream["dream_image_bytes"]).decode('utf-8')

            # Calculate milestone counts for summary
            if summary and "roadmap" not in dream:
                # Fetch just milestone count
                full_dream = await db.dreams.find_one(
                    {"thread_id": dream["thread_id"]},
                    {"roadmap.milestones": 1}
                )
                if full_dream and "roadmap" in full_dream:
                    milestones = full_dream["roadmap"].get("milestones", [])
                    dream["milestones_count"] = len(milestones)
                    dream["completed_milestones_count"] = sum(
                        1 for m in milestones if m.get("status") == "completed"
                    )

        return {
            "dreams": dreams,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "totalPages": (total + limit - 1) // limit
            }
        }

    except Exception as e:
        logger.error(f"Error fetching dreams for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 2. Get Single Dream

### `GET /api/dreams/{thread_id}`

Fetch a single dream by its thread_id.

**Path Parameters:**
- `thread_id` (required): Unique thread identifier

**Response:**

```json
{
  "_id": "507f1f77bcf86cd799439011",
  "user_id": "ABC123",
  "thread_id": "uuid-xyz",
  "dream": "Launch a profitable side business",
  "status": "active",
  "dream_image_bytes": "<base64 string>",
  "roadmap": {
    "milestones": [...]
  },
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-01-20T15:45:00Z"
}
```

**Implementation:**

```python
@router.get("/{thread_id}", tags=["dreams"])
async def get_dream_by_id(thread_id: str):
    """
    Get a single dream by thread_id.

    Args:
        thread_id: Unique thread identifier

    Returns:
        Complete dream document with full roadmap
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        dream = await db.dreams.find_one({"thread_id": thread_id})

        if dream is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dream with thread_id '{thread_id}' not found"
            )

        # Convert ObjectId and binary image
        if "_id" in dream:
            dream["_id"] = str(dream["_id"])

        if "dream_image_bytes" in dream and isinstance(dream["dream_image_bytes"], bytes):
            dream["dream_image_bytes"] = base64.b64encode(dream["dream_image_bytes"]).decode('utf-8')

        return dream

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dream {thread_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 3. Update Dream

### `PUT /api/dreams/{thread_id}`

Update dream fields (status, roadmap, milestones, etc.).

**Path Parameters:**
- `thread_id` (required): Unique thread identifier

**Request Body:**

```json
{
  "status": "completed",
  "isComplete": true,
  "roadmap": {
    "milestones": [...]
  }
}
```

**Response:**

```json
{
  "success": true,
  "message": "Dream updated successfully",
  "dream": {
    "thread_id": "uuid-xyz",
    "status": "completed",
    "updated_at": "2026-02-02T20:00:00Z"
  }
}
```

**Implementation:**

```python
from pydantic import BaseModel
from typing import Optional, Any

class UpdateDreamRequest(BaseModel):
    status: Optional[str] = None
    isComplete: Optional[bool] = None
    roadmap: Optional[dict] = None

@router.put("/{thread_id}", tags=["dreams"])
async def update_dream(thread_id: str, update_data: UpdateDreamRequest):
    """
    Update dream fields.

    Args:
        thread_id: Unique thread identifier
        update_data: Fields to update

    Returns:
        Success status and updated dream
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Check if dream exists
        dream = await db.dreams.find_one({"thread_id": thread_id})
        if dream is None:
            raise HTTPException(status_code=404, detail="Dream not found")

        # Build update document
        update_doc = {"updated_at": datetime.now(timezone.utc)}

        if update_data.status is not None:
            update_doc["status"] = update_data.status

        if update_data.isComplete is not None:
            update_doc["isComplete"] = update_data.isComplete

        if update_data.roadmap is not None:
            update_doc["roadmap"] = update_data.roadmap

        # Update dreams collection
        result = await db.dreams.update_one(
            {"thread_id": thread_id},
            {"$set": update_doc}
        )

        # Update dreams_summary in user document
        if update_data.status or update_data.isComplete:
            summary_update = {
                "dreams_summary.$.updated_at": datetime.now(timezone.utc).isoformat()
            }

            if update_data.status:
                summary_update["dreams_summary.$.status"] = update_data.status

            if update_data.isComplete:
                summary_update["dreams_summary.$.isComplete"] = update_data.isComplete

            await db.users.update_one(
                {"user_id": dream["user_id"], "dreams_summary.thread_id": thread_id},
                {"$set": summary_update}
            )

        return {
            "success": True,
            "message": "Dream updated successfully",
            "dream": {
                "thread_id": thread_id,
                "updated_at": update_doc["updated_at"].isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dream {thread_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 4. Delete Dream

### `DELETE /api/dreams/{thread_id}`

Delete a dream from both dreams collection and user's dreams_summary.

**Path Parameters:**
- `thread_id` (required): Unique thread identifier

**Response:**

```json
{
  "success": true,
  "message": "Dream deleted successfully"
}
```

**Implementation:**

```python
@router.delete("/{thread_id}", tags=["dreams"])
async def delete_dream(thread_id: str):
    """
    Delete a dream.

    Removes dream from:
    1. dreams collection
    2. User's dreams_summary array

    Args:
        thread_id: Unique thread identifier

    Returns:
        Success status
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Get dream to find user_id
        dream = await db.dreams.find_one({"thread_id": thread_id})

        if dream is None:
            raise HTTPException(status_code=404, detail="Dream not found")

        user_id = dream["user_id"]

        # Delete from dreams collection
        await db.dreams.delete_one({"thread_id": thread_id})

        # Remove from user's dreams_summary
        await db.users.update_one(
            {"user_id": user_id},
            {"$pull": {"dreams_summary": {"thread_id": thread_id}}}
        )

        return {
            "success": True,
            "message": "Dream deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dream {thread_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 5. Get Dream Milestones

### `GET /api/dreams/{thread_id}/milestones`

Get all milestones for a specific dream.

**Path Parameters:**
- `thread_id` (required): Unique thread identifier

**Response:**

```json
{
  "thread_id": "uuid-xyz",
  "milestones": [
    {
      "id": "m_0",
      "title": "Brainstorm business ideas",
      "status": "completed",
      "description": "...",
      "xp_points": 30
    }
  ]
}
```

**Implementation:**

```python
@router.get("/{thread_id}/milestones", tags=["dreams"])
async def get_dream_milestones(thread_id: str):
    """
    Get all milestones for a dream.

    Args:
        thread_id: Unique thread identifier

    Returns:
        List of milestones
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        dream = await db.dreams.find_one(
            {"thread_id": thread_id},
            {"roadmap.milestones": 1}
        )

        if dream is None:
            raise HTTPException(status_code=404, detail="Dream not found")

        milestones = dream.get("roadmap", {}).get("milestones", [])

        return {
            "thread_id": thread_id,
            "milestones": milestones
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching milestones for dream {thread_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## File Structure

**New File**: `api/dreams_crud.py`

```python
"""
Dreams CRUD API endpoints for the dreams collection.
Handles fetching, updating, and deleting dreams.
"""

import logging
import base64
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# ... (all endpoint implementations above)
```

**Update**: `main.py`

```python
from api import dreams_crud

# Add to routers
app.include_router(dreams_crud.router, prefix="/api/dreams", tags=["dreams"])
```

---

## Integration Notes

### Sync Between Collections

When updating dreams, ALWAYS update both:

1. **dreams collection** - Full data
2. **users.dreams_summary** - Lightweight summary

Example pattern:

```python
# Update dreams collection
await db.dreams.update_one(
    {"thread_id": thread_id},
    {"$set": {"status": "completed"}}
)

# Update dreams_summary in user doc
await db.users.update_one(
    {"user_id": user_id, "dreams_summary.thread_id": thread_id},
    {"$set": {"dreams_summary.$.status": "completed"}}
)
```

### Error Handling

If either update fails, consider implementing a transaction or retry logic to maintain consistency.

---

## Testing

### Postman Collection

```json
{
  "info": {
    "name": "Dreams API",
    "_postman_id": "..."
  },
  "item": [
    {
      "name": "Get User Dreams",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/api/dreams?user_id=ABC123"
      }
    },
    {
      "name": "Get Single Dream",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/api/dreams/thread-id-xyz"
      }
    }
  ]
}
```

### cURL Examples

```bash
# Get all dreams for a user
curl http://localhost:5000/api/dreams?user_id=ABC123

# Get single dream
curl http://localhost:5000/api/dreams/thread-id-xyz

# Update dream status
curl -X PUT http://localhost:5000/api/dreams/thread-id-xyz \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "isComplete": true}'

# Delete dream
curl -X DELETE http://localhost:5000/api/dreams/thread-id-xyz
```

---

## Performance Considerations

1. **Indexes**: Ensure indexes on `user_id`, `thread_id`, and `(user_id, status)` are created
2. **Pagination**: Always use pagination for listing dreams
3. **Caching**: Consider caching frequently accessed dreams
4. **Image Handling**: Images are stored as binary in dreams collection, converted to base64 on retrieval

---

## Future Enhancements

- [ ] Bulk operations for dreams
- [ ] Search/filter dreams by keywords
- [ ] Dream analytics endpoints
- [ ] Export dreams data
- [ ] Dream sharing features
