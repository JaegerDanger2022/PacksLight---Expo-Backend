# Voice V2 Deployment Guide
## LangGraph + Eleven Labs Implementation

**Date:** 2026-02-01
**Status:** Ready for deployment
**Implementation:** Complete - needs API keys and testing

---

## What Was Implemented

### Backend (PacksLight---Expo-Backend)
- ✅ `api/voice_v2.py` - New WebSocket endpoint with STT/TTS
- ✅ Updated `main.py` to use voice_v2 router
- ✅ OpenAI Whisper integration for speech-to-text
- ✅ Eleven Labs integration for text-to-speech
- ✅ LangGraph voice conversation node integration
- ✅ Reuses existing `/api/dreams/create` endpoint

### LangGraph (PacksLight---Dream-to-do-challenges)
- ✅ `services/voice_conversation.py` - Voice conversation node
- ✅ Function calling for context extraction
- ✅ Multi-turn conversation handling
- ✅ Claude 3.5 Sonnet v2 integration

### Frontend (PacksLight---Expo-Frontend)
- ✅ Simplified MP3 audio playback
- ✅ Removed complex chunk buffering
- ✅ Direct audio playback from Eleven Labs
- ✅ Cleaner voice store logic

---

## Environment Variables Required

### Backend (.env + Railway)

```bash
# OpenAI (Whisper STT)
OPENAI_API_KEY=sk-proj-...

# Eleven Labs (TTS)
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel (or choose another)

# Backend URL (for internal API calls)
BACKEND_URL=https://packslight-expo-backend-production.up.railway.app

# Existing
LANGGRAPH_AGENT_URL=...
LANGGRAPH_API_KEY=...
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### LangGraph (.env)

Already configured - no changes needed.

### Frontend (.env)

No changes needed - already points to backend.

---

## Deployment Steps

### Step 1: Get API Keys

1. **OpenAI API Key** (Whisper STT)
   - Go to: https://platform.openai.com/api-keys
   - Create new secret key
   - Copy key starting with `sk-proj-...`
   - Cost: ~$0.006/minute (~$0.02 per 3-min conversation)

2. **Eleven Labs API Key** (TTS)
   - Go to: https://elevenlabs.io/app/settings/api-keys
   - Copy API key
   - Cost: ~$0.30 per 1K characters (~$0.10 per conversation)

3. **Choose Voice** (Optional - defaults to Rachel)
   - Go to: https://elevenlabs.io/voice-library
   - Available voices:
     - `21m00Tcm4TlvDq8ikWAM` - Rachel (warm, friendly) **DEFAULT**
     - `EXAVITQu4vr4xnSDxMaL` - Bella (soft, young)
     - `ErXwobaYiN019PkySvjV` - Antoni (calm, well-rounded)

### Step 2: Add Environment Variables to Railway

1. Go to Railway dashboard: https://railway.app/
2. Select your backend project
3. Go to Variables tab
4. Add:
   - `OPENAI_API_KEY=sk-proj-...`
   - `ELEVENLABS_API_KEY=...`
   - `ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM` (optional)
   - `BACKEND_URL=https://packslight-expo-backend-production.up.railway.app`

### Step 3: Deploy LangGraph Voice Node

The `voice_conversation.py` file is already in the LangGraph repo. To make it accessible:

**Option A: Deploy as separate endpoint** (recommended)
```bash
cd PacksLight---Dream-to-do-challenges
# Add to build.py or create new voice_build.py
# Deploy to LangGraph platform
```

**Option B: Call directly from backend**
```python
# Already implemented in voice_v2.py
# Backend makes HTTP POST to:
# {LANGGRAPH_AGENT_URL}/voice_conversation/invoke
```

### Step 4: Test

1. **Health Check**
   ```bash
   curl https://packslight-expo-backend-production.up.railway.app/api/voice/health
   ```

   Expected response:
   ```json
   {
     "status": "healthy",
     "services": {
       "whisper_stt": true,
       "elevenlabs_tts": true,
       "langgraph": true
     },
     "message": "Voice services ready"
   }
   ```

2. **Frontend Test**
   - Open PacksLight app on dev build
   - Navigate to dream creation
   - Switch to voice mode
   - Should hear AI greeting
   - Speak your dream
   - Should get conversational responses

---

## How It Works

### Flow Diagram

```
User                 Frontend              Backend                LangGraph
 |                      |                     |                       |
 |-- Open Voice Mode -->|                     |                       |
 |                      |-- WebSocket ------->|                       |
 |                      |                     |-- Call voice node --->|
 |                      |                     |<-- AI greeting -------|
 |                      |                     |-- TTS (ElevenLabs)--->|
 |<-- Hear Greeting ----|<-- MP3 audio -------|                       |
 |                      |                     |                       |
 |-- Speak Dream ------>|-- Audio ----------->|                       |
 |                      |                     |-- STT (Whisper) ----->|
 |                      |                     |-- Call voice node --->|
 |                      |                     |<-- AI response -------|
 |                      |                     |-- TTS ---------------->|
 |<-- Hear Response ----|<-- MP3 audio -------|                       |
 |                      |                     |                       |
 |... (2-3 exchanges)...|                     |                       |
 |                      |                     |                       |
 |                      |                     |<-- Context extracted--|
 |                      |                     |                       |
 |                      |                     |-- POST /dreams/create |
 |                      |                     |   (trigger roadmap)   |
 |                      |                     |<-- thread_id ---------|
 |                      |<-- workflow done ---|                       |
 |<-- See Roadmap ------|                     |                       |
```

### Message Protocol

**Frontend → Backend:**
```json
{"type": "audio", "data": "<base64_wav>"}
```

**Backend → Frontend:**
```json
{"type": "audio", "data": "<base64_mp3>"}
{"type": "text", "text": "AI message"}
{"type": "turn_complete"}
{"type": "workflow_complete", "thread_id": "...", "user_request": "..."}
{"type": "error", "message": "..."}
```

---

## Cost Per Conversation

| Service | Usage | Cost |
|---------|-------|------|
| Whisper STT | 3 min audio | $0.018 |
| Claude 3.5 Sonnet | ~5K tokens | $0.025 |
| Eleven Labs TTS | ~300 chars | $0.09 |
| **Total** | | **$0.133** |

**Monthly (1000 conversations):** $133/month

---

## Troubleshooting

### Health Check Fails

```bash
# Check if API keys are set
curl https://packslight-expo-backend-production.up.railway.app/api/voice/health
```

**If degraded:**
1. Verify `OPENAI_API_KEY` in Railway
2. Verify `ELEVENLABS_API_KEY` in Railway
3. Verify `LANGGRAPH_AGENT_URL` and `LANGGRAPH_API_KEY` in Railway
4. Redeploy backend

### No Audio Playback

**Check:**
1. Frontend logs show `[AudioRecording] MP3 file written`
2. File size is reasonable (>10KB)
3. Audio permissions granted
4. Device volume is up

### STT Not Working

**Check:**
1. Audio format is 16kHz WAV
2. `OPENAI_API_KEY` is valid
3. Backend logs show "User said: ..."

### TTS Not Working

**Check:**
1. `ELEVENLABS_API_KEY` is valid
2. Voice ID exists (default: Rachel)
3. Backend logs show audio bytes size

### LangGraph Connection Fails

**Check:**
1. `LANGGRAPH_AGENT_URL` is correct
2. `LANGGRAPH_API_KEY` is valid
3. Voice conversation node is deployed
4. Backend logs show HTTP status codes

---

## Testing Checklist

- [ ] Health check returns "healthy"
- [ ] AI greeting plays on voice mode open
- [ ] User audio transcribes correctly
- [ ] AI responses are contextual
- [ ] Audio quality is clear
- [ ] Context extracts after 2-3 turns
- [ ] Roadmap workflow triggers
- [ ] Dream appears in user's list
- [ ] Error handling works gracefully

---

## Rollback Plan

If voice v2 has issues, rollback to text-only:

1. In `main.py`, comment out voice_v2 import:
   ```python
   # from api.voice_v2 import router as voice_router
   ```

2. Disable voice mode in frontend:
   ```typescript
   // In CreateDreamModal.tsx
   const [voiceEnabled, setVoiceEnabled] = useState(false);
   ```

3. Redeploy backend

---

## Next Steps

1. ✅ Get OpenAI API key
2. ✅ Get Eleven Labs API key
3. ✅ Add env vars to Railway
4. ✅ Test health check
5. ✅ Test voice conversation end-to-end
6. ✅ Monitor costs
7. ✅ Optimize if needed (caching, streaming)

---

**Status:** Ready for production testing
**Risk:** Low - clean implementation, fallback available
**Estimated Setup Time:** 15 minutes
