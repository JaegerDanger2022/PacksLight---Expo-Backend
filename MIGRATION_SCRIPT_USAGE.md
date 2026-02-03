# Migration Script Usage Guide

Quick guide for using the temporary migration endpoints and scripts.

---

## Setup (5 minutes)

### 1. Backend: Add Temporary Router

**File**: `main.py`

Add this line with your other router imports:

```python
from api import migration_temp

# Add with other routers
app.include_router(migration_temp.router, prefix="/api/migration", tags=["migration-temp"])
```

### 2. Backend: Create Dreams Collection Indexes

Make sure you've added the dreams collection indexes to `core/database.py`:

```python
# In setup_indexes() function
await db.dreams.create_index("user_id")
await db.dreams.create_index("thread_id", unique=True)
await db.dreams.create_index([("user_id", 1), ("status", 1)])
```

### 3. Deploy Backend

```bash
# Deploy to Railway or your hosting
railway up
# OR
git push
```

---

## Migration Steps

### Step 1: Check Status (Optional but Recommended)

Check if a user needs migration:

```bash
cd PacksLight---Expo-Frontend
npx ts-node scripts/migrate-user-data.ts status <user_id>
```

**Example:**
```bash
npx ts-node scripts/migrate-user-data.ts status YkkE6Jhtt3aCyTpzTYb6xfmVZWl2
```

**Output:**
```
📊 Checking migration status for user: YkkE6Jhtt3aCyTpzTYb6xfmVZWl2
Status: {
  Old dreams: 3,
  Dreams summary: 0,
  Dreams in collection: 0,
  Migration complete: ❌,
  Needs migration: ⚠️  YES
}
```

---

### Step 2: Migrate Single User (Testing)

Migrate ONE user first to test:

```bash
npx ts-node scripts/migrate-user-data.ts migrate <user_id>
```

**Example:**
```bash
npx ts-node scripts/migrate-user-data.ts migrate YkkE6Jhtt3aCyTpzTYb6xfmVZWl2
```

**Output:**
```
🚀 Starting migration for user: YkkE6Jhtt3aCyTpzTYb6xfmVZWl2

✅ Migration completed!
Results: {
  Dreams migrated: 3,
  Already migrated: 0,
  Total dreams: 3,
  Dreams summary created: 3
}
```

---

### Step 3: Verify Migration

Check the migrated user again:

```bash
npx ts-node scripts/migrate-user-data.ts status YkkE6Jhtt3aCyTpzTYb6xfmVZWl2
```

**Output should show:**
```
Status: {
  Old dreams: 3,
  Dreams summary: 3,
  Dreams in collection: 3,
  Migration complete: ✅,
  Needs migration: ✅ NO
}
```

**Test in app:**
1. Log in as the migrated user
2. Check HomeScreen displays dreams
3. Check AllDreamsScreen works
4. Open a dream detail page
5. Verify milestones load

---

### Step 4: Migrate ALL Users

Once you've verified one user works:

```bash
npx ts-node scripts/migrate-user-data.ts migrate-all
```

**This will:**
- Process all users with dreams
- Skip users already migrated
- Show progress and errors

**Output:**
```
🚀 Starting migration for ALL users...
⚠️  This may take a while depending on the number of users!

[Processing users...]

✅ All users migration completed!
Results: {
  Total users: 150,
  Users migrated: 150,
  Users skipped: 5,
  Total dreams migrated: 487,
  Errors: 0
}
```

---

### Step 5: Cleanup (Optional - After 2 Weeks)

After verifying everything works for 2 weeks, remove old dreams array:

```bash
# ONLY do this after thorough testing!
npx ts-node scripts/migrate-user-data.ts cleanup <user_id>
```

---

## Alternative: Use API Endpoints Directly

You can also call the endpoints directly with cURL or Postman:

### Check Status
```bash
curl http://localhost:5000/api/migration/migration-status/USER_ID
```

### Migrate Single User
```bash
curl -X POST http://localhost:5000/api/migration/migrate-user/USER_ID
```

### Migrate All Users
```bash
curl -X POST http://localhost:5000/api/migration/migrate-all-users
```

### Cleanup Old Dreams
```bash
curl -X DELETE http://localhost:5000/api/migration/cleanup-old-dreams/USER_ID
```

---

## Troubleshooting

### Error: "Cannot connect to API server"

**Solution**: Make sure backend is running and `EXPO_PUBLIC_API_URL` is set correctly:

```bash
# Check .env file
cat .env

# Should have:
EXPO_PUBLIC_API_URL=https://your-backend-url.com

# Or for local testing:
EXPO_PUBLIC_API_URL=http://localhost:5000
```

### Error: "Migration not complete. Cannot cleanup old dreams array"

**Solution**: Run migration first before cleanup:

```bash
npx ts-node scripts/migrate-user-data.ts migrate USER_ID
```

### Dreams not showing in app after migration

**Solution**: Make sure you've added the backward compatibility helper to `authStore.ts`:

```typescript
const mapDreamsSummaryToDreams = (userData: UserData): UserData => {
  if (userData.dreams_summary && !userData.dreams) {
    userData.dreams = userData.dreams_summary.map(/* ... */);
  }
  return userData;
};
```

---

## Cleanup After Migration

### 1. Delete Temporary Files

After migration is complete and verified (2+ weeks):

**Backend:**
```bash
rm api/migration_temp.py
```

**Frontend:**
```bash
rm scripts/migrate-user-data.ts
```

### 2. Remove Temporary Router

**File**: `main.py`

Remove this line:
```python
app.include_router(migration_temp.router, prefix="/api/migration", tags=["migration-temp"])
```

### 3. (Optional) Remove Old Dreams Array

After 2 weeks of stable operation, cleanup old dreams arrays:

```bash
# For all users
npx ts-node scripts/migrate-user-data.ts cleanup USER_ID
```

Or in MongoDB directly:
```javascript
db.users.updateMany(
  { "dreams": { "$exists": true } },
  { "$unset": { "dreams": "" } }
)
```

---

## Safety Notes

✅ **Safe to run multiple times** - Script checks if dreams already migrated
✅ **Non-destructive** - Original dreams array remains until you explicitly cleanup
✅ **Rollback possible** - Can revert using the rollback script if needed
⚠️ **Test first** - Always migrate one user first before migrate-all
⚠️ **Backup database** - Always backup before major migrations

---

## Migration Checklist

- [ ] Backup MongoDB database
- [ ] Add temporary router to main.py
- [ ] Deploy backend with temporary endpoints
- [ ] Test migrate ONE user
- [ ] Verify user data in app
- [ ] Run migrate-all for all users
- [ ] Monitor for errors
- [ ] Verify app works for all users
- [ ] Wait 2 weeks
- [ ] Optional: Cleanup old dreams arrays
- [ ] Delete temporary migration files
- [ ] Remove temporary router from main.py

---

## Questions?

Refer to:
- [DREAMS_COLLECTION_MIGRATION.md](./DREAMS_COLLECTION_MIGRATION.md) - Full migration plan
- [MIGRATION_SUMMARY.md](./MIGRATION_SUMMARY.md) - Quick reference

Good luck! 🚀
