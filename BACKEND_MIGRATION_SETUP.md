# Backend Migration Setup Instructions

## Overview

This guide explains how to set up the temporary migration endpoints to migrate user dreams from embedded arrays to a separate dreams collection.

**⚠️ IMPORTANT: These are TEMPORARY endpoints. Delete them after migration is complete.**

---

## Step 1: Add Migration Router to main.py

### Location
File: `main.py`

### What to Add

1. **Add import** (with other router imports, around line 10-20):
```python
from api import migration_temp
```

2. **Add router registration** (with other routers, around line 40-60):
```python
app.include_router(migration_temp.router, prefix="/api/migration", tags=["migration-temp"])
```

### Complete Example

```python
# ... other imports ...
from api import users, dreams, milestone, victories, community, journey_recap
from api import migration_temp  # ← ADD THIS

# ... app initialization ...

# Routers
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(dreams.router, prefix="/api/dreams", tags=["dreams"])
app.include_router(milestone.router, prefix="/api/milestone", tags=["milestone"])
app.include_router(victories.router, prefix="/api/victories", tags=["victories"])
app.include_router(community.router, prefix="/api", tags=["community"])
app.include_router(journey_recap.router, prefix="/api/journey-recaps", tags=["journey-recap"])
app.include_router(migration_temp.router, prefix="/api/migration", tags=["migration-temp"])  # ← ADD THIS
```

---

## Step 2: Add Database Indexes

### Location
File: `core/database.py`

### What to Add

Add these indexes to the `setup_indexes()` function:

```python
async def setup_indexes():
    # ... existing indexes ...

    # ============= DREAMS COLLECTION INDEXES (NEW) =============
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

### Why These Indexes?

1. **dreams.user_id** - Fast lookup of all dreams for a user
2. **dreams.thread_id (unique)** - Ensures no duplicate dreams, fast thread lookup
3. **dreams (user_id, status)** - Efficient filtering by user and status (active/archived)
4. **dreams (user_id, updated_at)** - Fast sorting by most recently updated dreams

---

## Step 3: Deploy Backend

### Option 1: Railway
```bash
railway up
```

### Option 2: Git Push (if auto-deploy enabled)
```bash
git add .
git commit -m "Add temporary migration endpoints"
git push
```

### Verify Deployment

Check Railway logs for:
```
[DB] Creating index: dreams.user_id
[DB] Index created: dreams.user_id
[DB] Creating index: dreams.thread_id (unique)
[DB] Index created: dreams.thread_id
```

---

## Step 4: Test Migration Endpoints

### Test 1: Check Migration Status
```bash
curl http://localhost:5000/api/migration/migration-status/YOUR_USER_ID
```

**Expected Response:**
```json
{
  "user_id": "YOUR_USER_ID",
  "has_old_dreams_array": true,
  "old_dreams_count": 5,
  "has_dreams_summary": false,
  "dreams_summary_count": 0,
  "dreams_in_collection": 0,
  "migration_complete": false,
  "needs_migration": true
}
```

### Test 2: Migrate Single User (Testing)
```bash
curl -X POST http://localhost:5000/api/migration/migrate-user/YOUR_USER_ID
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Migration completed successfully",
  "user_id": "YOUR_USER_ID",
  "dreams_migrated": 5,
  "already_migrated": 0,
  "total_dreams": 5,
  "dreams_summary_created": 5
}
```

---

## Step 5: Run Frontend Migration Script

After backend is deployed and tested, run the frontend migration script:

```bash
# From frontend directory
npx ts-node scripts/migrate-user-data.ts migrate-all
```

See [MIGRATION_SCRIPT_USAGE.md](../PacksLight---Expo-Frontend/MIGRATION_SCRIPT_USAGE.md) for detailed instructions.

---

## Step 6: After Migration is Complete

### Delete These Files

1. **Backend:**
   ```bash
   rm api/migration_temp.py
   ```

2. **Remove from main.py:**
   ```python
   # DELETE THIS LINE:
   from api import migration_temp

   # DELETE THIS LINE:
   app.include_router(migration_temp.router, prefix="/api/migration", tags=["migration-temp"])
   ```

3. **Frontend:**
   ```bash
   rm scripts/migrate-user-data.ts
   ```

### Optional: Remove Old Dreams Array

After verifying migration worked correctly for 1-2 weeks, you can remove the old dreams array from all users:

```python
# Run this in MongoDB shell or via script
await db.users.update_many(
    {"dreams": {"$exists": True}},
    {"$unset": {"dreams": ""}}
)
```

---

## Troubleshooting

### Issue: "Database connection failed"
**Solution:** Check MongoDB connection string in Railway environment variables

### Issue: Index creation fails
**Solution:** Check if indexes already exist:
```python
await db.dreams.index_information()
```

### Issue: Migration endpoint not found (404)
**Solution:** Verify:
1. `api/migration_temp.py` file exists
2. Router is added to `main.py`
3. Backend is deployed and restarted

### Issue: Duplicate key error on thread_id
**Solution:** Dream already exists in collection (safe to ignore, migration skips duplicates)

---

## Safety Notes

1. **Backup First**: Always backup your database before running migration
   ```bash
   mongodump --uri="YOUR_MONGODB_URI" --out=/backup/before-migration
   ```

2. **Test on Staging**: Run migration on staging environment first

3. **Single User Test**: Always test with a single user before migrating all users

4. **Monitor Logs**: Watch Railway logs during migration for errors

5. **Verify Data**: Check a few users manually after migration to ensure data integrity

---

## What the Migration Does

### Before Migration
```json
{
  "user_id": "ABC123",
  "dreams": [
    {
      "thread_id": "xyz",
      "dream": "Launch a business",
      "roadmap": {
        "milestones": [/* 50+ milestone objects */]
      },
      "dream_image_bytes": "<binary data>"
    }
  ]
}
```
**Size**: 500KB - 2MB per user

### After Migration

**users collection:**
```json
{
  "user_id": "ABC123",
  "dreams_summary": [
    {
      "thread_id": "xyz",
      "dream": "Launch a business",
      "status": "active",
      "dream_image_bytes": "<base64 string>",
      "milestones_count": 25,
      "completed_milestones_count": 5
    }
  ]
}
```
**Size**: 50-60KB per user (8-10x smaller)

**dreams collection (new):**
```json
{
  "user_id": "ABC123",
  "thread_id": "xyz",
  "dream": "Launch a business",
  "status": "active",
  "dream_image_bytes": "<binary data>",
  "roadmap": {
    "milestones": [/* 50+ milestone objects */]
  },
  "created_at": "2025-01-15T...",
  "updated_at": "2025-01-20T..."
}
```
**Fetched separately when needed**

---

## Expected Performance Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| User fetch size | 500KB-2MB | 50-60KB | **8-10x smaller** |
| App load time | 3-10s | 0.5-1s | **6-10x faster** |
| Initial render | Slow | Instant | **Immediate** |

---

## Questions?

See:
- [QUICK_SETUP.md](./QUICK_SETUP.md) - Quick reference
- [MIGRATION_SUMMARY.md](./MIGRATION_SUMMARY.md) - Complete overview
- [DREAMS_COLLECTION_MIGRATION.md](./DREAMS_COLLECTION_MIGRATION.md) - Detailed migration plan
- [MIGRATION_SCRIPT_USAGE.md](../PacksLight---Expo-Frontend/MIGRATION_SCRIPT_USAGE.md) - Frontend script usage

---

That's it! Follow these steps in order and you'll have a successful migration. 🚀
