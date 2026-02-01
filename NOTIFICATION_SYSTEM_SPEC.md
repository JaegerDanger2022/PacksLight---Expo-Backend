# Notification System Backend Implementation Spec

## Overview

This specification details the backend implementation needed for the PacksLight notification system. The frontend client is already implemented and ready to integrate.

## 1. Database Schema Updates

### 1.1 Users Collection - Add New Fields

Add the following fields to the `users` collection in MongoDB:

```python
# Add to existing users collection
{
  "user_id": str,
  "email": str,
  "firstname": str,
  "lastname": str,

  # NEW NOTIFICATION FIELDS
  "push_token": str | None,  # Expo Push Token format: "ExponentPushToken[xxxxxx]"
  "last_activity": str | None,  # ISO 8601 timestamp
  "last_login": str | None,  # ISO 8601 timestamp

  "notification_preferences": {
    "daily_check_in": bool,  # Default: True
    "comeback_alert": bool,  # Default: True
    "preferred_time": str,  # Format: "09:00" (24-hour time)
  },

  "notification_metadata": {
    "last_daily_check_in_sent": str | None,  # ISO 8601 timestamp
    "last_comeback_alert_sent": str | None,  # ISO 8601 timestamp
    "daily_check_in_count": int,  # Default: 0
    "comeback_alert_count": int,  # Default: 0
  },

  # Existing fields...
  "created_at": datetime,
  "couragePoints": int,
  "dreams": list,
  # ... etc
}
```

### 1.2 Default Values for New Users

When creating new users in `POST /api/users/register`, initialize:

```python
"push_token": None,
"last_activity": None,
"last_login": datetime.now(timezone.utc).isoformat(),
"notification_preferences": {
    "daily_check_in": True,
    "comeback_alert": True,
    "preferred_time": "09:00",
},
"notification_metadata": {
    "last_daily_check_in_sent": None,
    "last_comeback_alert_sent": None,
    "daily_check_in_count": 0,
    "comeback_alert_count": 0,
}
```

---

## 2. API Endpoints

### 2.1 POST `/api/users/{user_id}/push-token`

**Purpose:** Save/update the user's Expo Push Token for sending push notifications.

**Request Body:**
```python
class SavePushTokenRequest(BaseModel):
    push_token: str = Field(..., description="Expo Push Token (format: ExponentPushToken[...])")
```

**Response:**
```python
{
    "success": bool,
    "message": str,
    "push_token": str
}
```

**Implementation:**
```python
@router.post("/{user_id}/push-token", status_code=200, tags=["users"])
async def save_push_token(user_id: str, data: SavePushTokenRequest):
    """
    Save or update the user's Expo Push Token.

    Args:
        user_id: User's Firebase UID
        data: Request containing push_token

    Returns:
        Success status and saved token

    Raises:
        404: User not found
        500: Database error
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Find user
        user = await db.users.find_one({"user_id": user_id})
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Update push token
        await db.users.find_one_and_update(
            {"user_id": user_id},
            {
                "$set": {
                    "push_token": data.push_token,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        logger.info(f"Saved push token for user {user_id}")

        return {
            "success": True,
            "message": "Push token saved successfully",
            "push_token": data.push_token
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving push token: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

### 2.2 PUT `/api/users/{user_id}/activity`

**Purpose:** Update the user's last activity timestamp (called when user completes milestones).

**Request Body:**
```python
class UpdateActivityRequest(BaseModel):
    last_activity: str = Field(..., description="ISO 8601 timestamp")
```

**Response:**
```python
{
    "success": bool,
    "message": str,
    "last_activity": str
}
```

**Implementation:**
```python
@router.put("/{user_id}/activity", status_code=200, tags=["users"])
async def update_last_activity(user_id: str, data: UpdateActivityRequest):
    """
    Update the user's last activity timestamp.

    Called automatically when user completes milestones to track engagement.

    Args:
        user_id: User's Firebase UID
        data: Request containing last_activity timestamp

    Returns:
        Success status and updated timestamp

    Raises:
        404: User not found
        500: Database error
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Find user
        user = await db.users.find_one({"user_id": user_id})
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Update last activity
        await db.users.find_one_and_update(
            {"user_id": user_id},
            {
                "$set": {
                    "last_activity": data.last_activity,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        logger.info(f"Updated last activity for user {user_id}")

        return {
            "success": True,
            "message": "Last activity updated successfully",
            "last_activity": data.last_activity
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating last activity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

### 2.3 PUT `/api/users/{user_id}/notification-preferences`

**Purpose:** Update user's notification preferences (enable/disable notifications, set preferred time).

**Request Body:**
```python
class NotificationPreferencesRequest(BaseModel):
    daily_check_in: bool = Field(..., description="Enable daily check-in reminders")
    comeback_alert: bool = Field(..., description="Enable comeback alerts after inactivity")
    preferred_time: str = Field(..., description="Preferred notification time (HH:MM format)")
```

**Response:**
```python
{
    "success": bool,
    "message": str,
    "notification_preferences": dict
}
```

**Implementation:**
```python
@router.put("/{user_id}/notification-preferences", status_code=200, tags=["users"])
async def update_notification_preferences(user_id: str, data: NotificationPreferencesRequest):
    """
    Update the user's notification preferences.

    Args:
        user_id: User's Firebase UID
        data: Notification preferences

    Returns:
        Success status and updated preferences

    Raises:
        400: Invalid preferred_time format
        404: User not found
        500: Database error
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Validate preferred_time format (HH:MM)
        import re
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', data.preferred_time):
            raise HTTPException(
                status_code=400,
                detail="Invalid preferred_time format. Expected HH:MM (24-hour format)"
            )

        # Find user
        user = await db.users.find_one({"user_id": user_id})
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        preferences = {
            "daily_check_in": data.daily_check_in,
            "comeback_alert": data.comeback_alert,
            "preferred_time": data.preferred_time,
        }

        # Update preferences
        await db.users.find_one_and_update(
            {"user_id": user_id},
            {
                "$set": {
                    "notification_preferences": preferences,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        logger.info(f"Updated notification preferences for user {user_id}")

        return {
            "success": True,
            "message": "Notification preferences updated successfully",
            "notification_preferences": preferences
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 3. Notification Service

Create a new service file: `services/notification_service.py`

### 3.1 Send Expo Push Notification

```python
"""
Notification service for sending push notifications via Expo Push API
"""

import logging
import httpx
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push_notification(
    push_token: str,
    title: str,
    body: str,
    data: Dict[str, Any] = None,
    badge: int = 1,
    sound: str = "default",
    priority: str = "high"
) -> Dict[str, Any]:
    """
    Send a push notification via Expo Push API.

    Args:
        push_token: Expo Push Token (format: ExponentPushToken[...])
        title: Notification title
        body: Notification body text
        data: Optional custom data payload
        badge: Badge count (iOS)
        sound: Sound to play ("default" or null)
        priority: "high" or "normal"

    Returns:
        Response from Expo Push API

    Raises:
        Exception: If API call fails
    """
    if not push_token or not push_token.startswith("ExponentPushToken["):
        logger.warning(f"Invalid push token format: {push_token}")
        return {"status": "error", "message": "Invalid push token format"}

    payload = {
        "to": push_token,
        "title": title,
        "body": body,
        "sound": sound,
        "badge": badge,
        "priority": priority,
        "data": data or {},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            response.raise_for_status()
            result = response.json()

            logger.info(f"Push notification sent successfully to {push_token[:20]}...")
            return result

    except httpx.HTTPError as e:
        logger.error(f"Failed to send push notification: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending push notification: {e}", exc_info=True)
        raise


async def send_batch_push_notifications(
    notifications: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Send multiple push notifications in a batch.

    Args:
        notifications: List of notification payloads (same format as send_push_notification)

    Returns:
        List of responses from Expo Push API
    """
    if not notifications:
        return []

    # Expo supports up to 100 notifications per batch
    batch_size = 100
    results = []

    for i in range(0, len(notifications), batch_size):
        batch = notifications[i:i + batch_size]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    EXPO_PUSH_URL,
                    json=batch,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                response.raise_for_status()
                batch_results = response.json()
                results.extend(batch_results.get("data", []))

                logger.info(f"Batch push notifications sent: {len(batch)} notifications")

        except Exception as e:
            logger.error(f"Failed to send batch notifications: {e}", exc_info=True)
            # Continue with next batch even if this one fails

    return results
```

---

## 4. Schedulers (Optional - For Automated Notifications)

### 4.1 Daily Check-In Scheduler

Create: `schedulers/daily_check_in_scheduler.py`

**Purpose:** Send notifications to users who have active streaks but haven't completed today's milestone.

**Logic:**
- Run every hour
- Find users where:
  - `notification_preferences.daily_check_in == True`
  - `streak.current_streak > 0` (active streak)
  - Last completion was yesterday (haven't completed today)
  - Current time is >= `notification_preferences.preferred_time + 2 hours`
  - No notification sent today (`notification_metadata.last_daily_check_in_sent` is not today)
- Send notification: "🔥 Keep your streak alive! You haven't completed today's milestone yet."

```python
"""
Daily check-in scheduler - Send reminders to maintain streaks
"""

import logging
from datetime import datetime, timezone, timedelta
from core.database import get_db
from services.notification_service import send_push_notification

logger = logging.getLogger(__name__)


async def run_daily_check_in_scheduler():
    """
    Find users with active streaks who haven't completed today's milestone
    and send them a reminder notification.
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        return

    try:
        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()

        logger.info(f"[DailyCheckIn] Running scheduler at {now_utc.isoformat()}")

        # Find eligible users
        users = await db.users.find({
            "notification_preferences.daily_check_in": True,
            "push_token": {"$ne": None},
            "streak.current_streak": {"$gt": 0}
        }).to_list(length=None)

        notifications_sent = 0

        for user in users:
            user_id = user.get("user_id")
            push_token = user.get("push_token")
            streak = user.get("streak", {})
            prefs = user.get("notification_preferences", {})
            metadata = user.get("notification_metadata", {})

            # Check if last completion was yesterday (not today)
            last_completion = streak.get("last_completion_date")
            if last_completion:
                last_date = datetime.fromisoformat(last_completion.replace('Z', '+00:00')).date()
                if last_date >= today:
                    # Already completed today, skip
                    continue

            # Check if we already sent a notification today
            last_sent = metadata.get("last_daily_check_in_sent")
            if last_sent:
                last_sent_date = datetime.fromisoformat(last_sent.replace('Z', '+00:00')).date()
                if last_sent_date >= today:
                    # Already sent today, skip
                    continue

            # Check if current time is past preferred_time + 2 hours
            preferred_time = prefs.get("preferred_time", "09:00")
            hour, minute = map(int, preferred_time.split(":"))
            preferred_dt = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
            notification_time = preferred_dt + timedelta(hours=2)

            if now_utc < notification_time:
                # Too early, skip
                continue

            # Send notification
            try:
                current_streak = streak.get("current_streak", 0)

                await send_push_notification(
                    push_token=push_token,
                    title="🔥 Keep your streak alive!",
                    body=f"You're on a {current_streak}-day streak! Don't break it - complete a milestone today.",
                    data={
                        "type": "daily_check_in",
                        "screen": "Home",
                        "streak_count": current_streak
                    }
                )

                # Update metadata
                await db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "notification_metadata.last_daily_check_in_sent": now_utc.isoformat(),
                        },
                        "$inc": {
                            "notification_metadata.daily_check_in_count": 1
                        }
                    }
                )

                notifications_sent += 1
                logger.info(f"[DailyCheckIn] Sent notification to user {user_id}")

            except Exception as e:
                logger.error(f"[DailyCheckIn] Failed to send to user {user_id}: {e}")

        logger.info(f"[DailyCheckIn] Scheduler complete. Sent {notifications_sent} notifications")

    except Exception as e:
        logger.error(f"[DailyCheckIn] Scheduler error: {e}", exc_info=True)
```

---

### 4.2 Comeback Alert Scheduler

Create: `schedulers/comeback_alert_scheduler.py`

**Purpose:** Send notifications to users who haven't been active for 3+ days.

**Logic:**
- Run daily at 10 AM
- Find users where:
  - `notification_preferences.comeback_alert == True`
  - `last_activity` is >= 3 days ago
  - No comeback alert sent in the last 7 days
- Send notification: "👋 We miss you! Your goals are waiting."

```python
"""
Comeback alert scheduler - Re-engage inactive users
"""

import logging
from datetime import datetime, timezone, timedelta
from core.database import get_db
from services.notification_service import send_push_notification

logger = logging.getLogger(__name__)


async def run_comeback_alert_scheduler():
    """
    Find users who have been inactive for 3+ days and send them
    a comeback notification (max once per week).
    """
    db = get_db()
    if db is None:
        logger.error("Database not connected")
        return

    try:
        now_utc = datetime.now(timezone.utc)
        three_days_ago = now_utc - timedelta(days=3)
        seven_days_ago = now_utc - timedelta(days=7)

        logger.info(f"[ComebackAlert] Running scheduler at {now_utc.isoformat()}")

        # Find eligible users
        users = await db.users.find({
            "notification_preferences.comeback_alert": True,
            "push_token": {"$ne": None},
            "last_activity": {"$lt": three_days_ago.isoformat()}
        }).to_list(length=None)

        notifications_sent = 0

        for user in users:
            user_id = user.get("user_id")
            push_token = user.get("push_token")
            metadata = user.get("notification_metadata", {})

            # Check if we already sent a comeback alert in the last 7 days
            last_sent = metadata.get("last_comeback_alert_sent")
            if last_sent:
                last_sent_dt = datetime.fromisoformat(last_sent.replace('Z', '+00:00'))
                if last_sent_dt > seven_days_ago:
                    # Sent too recently, skip
                    continue

            # Send notification
            try:
                await send_push_notification(
                    push_token=push_token,
                    title="👋 We miss you!",
                    body="Your goals are waiting. Come back and complete a milestone today!",
                    data={
                        "type": "comeback_alert",
                        "screen": "Home"
                    }
                )

                # Update metadata
                await db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "notification_metadata.last_comeback_alert_sent": now_utc.isoformat(),
                        },
                        "$inc": {
                            "notification_metadata.comeback_alert_count": 1
                        }
                    }
                )

                notifications_sent += 1
                logger.info(f"[ComebackAlert] Sent notification to user {user_id}")

            except Exception as e:
                logger.error(f"[ComebackAlert] Failed to send to user {user_id}: {e}")

        logger.info(f"[ComebackAlert] Scheduler complete. Sent {notifications_sent} notifications")

    except Exception as e:
        logger.error(f"[ComebackAlert] Scheduler error: {e}", exc_info=True)
```

---

## 5. Running Schedulers

### 5.1 Using APScheduler (Recommended)

Install: `pip install apscheduler`

Update `main.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from schedulers.daily_check_in_scheduler import run_daily_check_in_scheduler
from schedulers.comeback_alert_scheduler import run_comeback_alert_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    await connect_db()

    # Initialize scheduler
    scheduler = AsyncIOScheduler()

    # Daily check-in: Run every hour
    scheduler.add_job(run_daily_check_in_scheduler, 'interval', hours=1)

    # Comeback alert: Run daily at 10 AM UTC
    scheduler.add_job(run_comeback_alert_scheduler, 'cron', hour=10, minute=0)

    scheduler.start()
    logger.info("Schedulers started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()
    await close_db()
```

### 5.2 Using Cron Jobs (Alternative)

Create standalone scripts that can be run via cron:

```bash
# Run daily check-in every hour
0 * * * * cd /path/to/backend && python -m schedulers.daily_check_in_scheduler

# Run comeback alert daily at 10 AM
0 10 * * * cd /path/to/backend && python -m schedulers.comeback_alert_scheduler
```

---

## 6. Dependencies

Add to `requirements.txt`:

```
httpx>=0.25.0  # For Expo Push API calls
apscheduler>=3.10.0  # For scheduled tasks (optional)
```

---

## 7. Environment Variables

No additional environment variables needed. All configuration is in the database.

---

## 8. Testing the Implementation

### 8.1 Test Push Token Endpoint

```bash
curl -X POST http://localhost:8001/api/users/{user_id}/push-token \
  -H "Content-Type: application/json" \
  -d '{
    "push_token": "ExponentPushToken[xxxxxx]"
  }'
```

### 8.2 Test Activity Update

```bash
curl -X PUT http://localhost:8001/api/users/{user_id}/activity \
  -H "Content-Type: application/json" \
  -d '{
    "last_activity": "2026-01-31T10:30:00Z"
  }'
```

### 8.3 Test Notification Preferences

```bash
curl -X PUT http://localhost:8001/api/users/{user_id}/notification-preferences \
  -H "Content-Type: application/json" \
  -d '{
    "daily_check_in": true,
    "comeback_alert": true,
    "preferred_time": "09:00"
  }'
```

### 8.4 Test Sending Push Notification

```python
# In Python REPL or test script
import asyncio
from services.notification_service import send_push_notification

async def test():
    result = await send_push_notification(
        push_token="ExponentPushToken[your-token-here]",
        title="Test Notification",
        body="This is a test!",
        data={"type": "test"}
    )
    print(result)

asyncio.run(test())
```

---

## 9. Implementation Checklist

### Phase 1: Core Endpoints (Required)
- [ ] Update MongoDB users schema with new fields
- [ ] Implement POST `/api/users/{user_id}/push-token`
- [ ] Implement PUT `/api/users/{user_id}/activity`
- [ ] Implement PUT `/api/users/{user_id}/notification-preferences`
- [ ] Update POST `/api/users/register` to include default notification fields

### Phase 2: Notification Service (Required)
- [ ] Create `services/notification_service.py`
- [ ] Implement `send_push_notification()` function
- [ ] Implement `send_batch_push_notifications()` function
- [ ] Test with Expo Push Tool: https://expo.dev/notifications

### Phase 3: Schedulers (Optional - For Automated Notifications)
- [ ] Create `schedulers/daily_check_in_scheduler.py`
- [ ] Create `schedulers/comeback_alert_scheduler.py`
- [ ] Install APScheduler
- [ ] Update `main.py` to run schedulers
- [ ] Test schedulers in development

### Phase 4: Testing & Deployment
- [ ] Test all endpoints with frontend integration
- [ ] Test push notifications on physical devices
- [ ] Deploy to production
- [ ] Monitor Expo Push API responses for errors

---

## 10. Frontend Integration Status

✅ **Frontend is ready!** The client-side implementation includes:
- Push token registration
- Activity tracking
- Notification handlers
- Local notification testing

Once you implement the backend endpoints, the frontend will automatically:
1. Save push tokens to backend on login
2. Update activity on milestone completions
3. Receive and display push notifications
4. Handle notification taps for navigation

---

## 11. Notes

### Security Considerations
- Push tokens are not sensitive secrets, but should only be accessible to authenticated users
- Validate all user inputs (especially `preferred_time` format)
- Rate limit notification endpoints to prevent abuse

### Expo Push API Limits
- Free tier: 600,000 notifications/month
- Batch size: Max 100 notifications per request
- Rate limit: 600 requests/minute

### Best Practices
- Always check `push_token` is not null before sending
- Handle Expo API errors gracefully (invalid tokens, device unreachable, etc.)
- Log all notification sends for debugging
- Monitor notification metadata counts for analytics

---

## 12. Support & Resources

- **Expo Push Notifications Docs:** https://docs.expo.dev/push-notifications/overview/
- **Expo Push Tool (Testing):** https://expo.dev/notifications
- **Expo Push API Spec:** https://docs.expo.dev/push-notifications/sending-notifications/
- **APScheduler Docs:** https://apscheduler.readthedocs.io/

---

**Questions?** Refer to the frontend implementation in:
- `src/services/notificationService.ts`
- `src/store/notificationStore.ts`
- `NOTIFICATION_IMPLEMENTATION_STATUS.md`
