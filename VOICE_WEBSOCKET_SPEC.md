# Voice WebSocket API Specification
## LangGraph + Eleven Labs Implementation

**Date:** 2026-02-01
**Status:** Specification
**Replaces:** Gemini Live API (deprecated)

---

## Overview

WebSocket endpoint for voice-based dream creation using:
- **OpenAI Whisper** - Speech-to-text transcription
- **LangGraph voice node** - Conversational AI (via HTTP to LangGraph platform)
- **Eleven Labs** - Text-to-speech synthesis

---

## Endpoint

```
WebSocket: wss://<backend>/api/voice/ws/{user_id}
```

---

## Dependencies

### Python Packages

Add to `requirements.txt`:

```txt
openai>=1.12.0
elevenlabs>=1.0.0
```

### Environment Variables

Add to `.env` and Railway:

```bash
# OpenAI (Whisper STT)
OPENAI_API_KEY=sk-...

# Eleven Labs (TTS)
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel (or choose another)

# Existing
LANGGRAPH_AGENT_URL=https://your-langgraph-deployment.com
LANGGRAPH_API_KEY=...
LANGGRAPH_ASSISTANT_ID=...
```

---

## Message Protocol

### Client → Server

#### 1. Audio Data
```json
{
  "type": "audio",
  "data": "base64_encoded_wav_audio"
}
```

**Format:**
- 16-bit PCM WAV
- 16kHz sample rate
- Mono (1 channel)
- Base64 encoded

---

### Server → Client

#### 1. Audio Response
```json
{
  "type": "audio",
  "data": "base64_encoded_mp3_audio"
}
```

**Format:**
- MP3 from Eleven Labs
- Base64 encoded
- Directly playable in React Native

#### 2. Text Transcript
```json
{
  "type": "text",
  "text": "AI's spoken message"
}
```

Used for displaying conversation history.

#### 3. Turn Complete
```json
{
  "type": "turn_complete"
}
```

Signals that the AI has finished its response (all audio sent).

#### 4. Workflow Starting
```json
{
  "type": "workflow_starting",
  "thread_id": "dream_user123_xyz",
  "user_request": "I want to learn guitar"
}
```

Sent when dream context is extracted and roadmap generation begins.

#### 5. Workflow Complete
```json
{
  "type": "workflow_complete",
  "thread_id": "dream_user123_xyz",
  "user_request": "I want to learn guitar",
  "enriched_context": {
    "user_dream": "I want to learn guitar",
    "timeline_preference": "few_months",
    "experience_level": "complete_beginner",
    "primary_motivation": "always wanted to play music",
    "specific_focus": "acoustic guitar",
    "concerns": ["don't know where to start", "worried about time"],
    "conversation_summary": "User wants to learn acoustic guitar...",
    "user_engaged": true
  }
}
```

#### 6. Error
```json
{
  "type": "error",
  "message": "Error description"
}
```

---

## Flow Diagram

```
Client                    Backend                   LangGraph
  |                          |                          |
  |--- Connect ------------->|                          |
  |                          |--- GET /threads -------->|
  |                          |<-- thread_id ------------|
  |                          |                          |
  |                          |--- POST greeting ------->|
  |                          |<-- AI greeting ----------|
  |                          |                          |
  |                          |-- TTS (Eleven Labs) ---->|
  |<-- audio (greeting) -----|                          |
  |<-- text (transcript) ----|                          |
  |<-- turn_complete --------|                          |
  |                          |                          |
  |--- audio (user) -------->|                          |
  |                          |-- STT (Whisper) -------->|
  |                          |                          |
  |                          |--- POST user message --->|
  |                          |<-- AI response ----------|
  |                          |                          |
  |                          |-- TTS (Eleven Labs) ---->|
  |<-- audio (AI) -----------|                          |
  |<-- text (transcript) ----|                          |
  |<-- turn_complete --------|                          |
  |                          |                          |
  |... (2-3 exchanges) ...   |                          |
  |                          |                          |
  |                          |<-- context_extracted ----|
  |<-- workflow_starting ----|                          |
  |                          |                          |
  |                          |--- POST /runs/wait ----->|
  |                          |    (architect node)      |
  |                          |<-- roadmap complete -----|
  |<-- workflow_complete ----|                          |
  |                          |                          |
  |--- Disconnect ---------->|                          |
```

---

## Implementation

### File Structure

```
PacksLight---Expo-Backend/
├── api/
│   └── voice.py           # WebSocket endpoint (UPDATE)
├── requirements.txt       # Add openai, elevenlabs
├── .env                   # Add API keys
└── VOICE_WEBSOCKET_SPEC.md (this file)
```

### Core Functions

#### 1. Speech-to-Text

```python
from openai import AsyncOpenAI
import io

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribe audio using OpenAI Whisper.

    Args:
        audio_bytes: WAV audio data (16kHz, 16-bit, mono)

    Returns:
        Transcribed text
    """
    try:
        # Create file-like object
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        # Transcribe
        response = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en"  # Optional: specify language
        )

        return response.text

    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        raise
```

**Cost:** $0.006 per minute of audio (~$0.02 per 3-minute conversation)

#### 2. Text-to-Speech

```python
from elevenlabs import AsyncElevenLabs, VoiceSettings

elevenlabs_client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

async def text_to_speech(text: str) -> bytes:
    """
    Convert text to speech using Eleven Labs.

    Args:
        text: Text to convert

    Returns:
        MP3 audio bytes
    """
    try:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

        # Generate audio
        audio_generator = await elevenlabs_client.generate(
            text=text,
            voice=voice_id,
            model="eleven_multilingual_v2",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75
            )
        )

        # Collect chunks
        audio_bytes = b""
        async for chunk in audio_generator:
            if chunk:
                audio_bytes += chunk

        return audio_bytes

    except Exception as e:
        logger.error(f"Eleven Labs TTS error: {e}")
        raise
```

**Cost:** $0.30 per 1K characters (~$0.10 per conversation)

**Voice Options:**
- `21m00Tcm4TlvDq8ikWAM` - Rachel (warm, friendly)
- `EXAVITQu4vr4xnSDxMaL` - Bella (soft, young)
- `ErXwobaYiN019PkySvjV` - Antoni (calm, well-rounded)

Browse more: https://elevenlabs.io/voice-library

#### 3. LangGraph Conversation

```python
async def call_langgraph_voice_node(
    thread_id: str,
    user_message: Optional[str] = None
) -> dict:
    """
    Call LangGraph voice conversation node.

    Args:
        thread_id: LangGraph thread ID
        user_message: User's message (None for initial greeting)

    Returns:
        {
            "ai_response": "AI's text response",
            "context_extracted": bool,
            "enriched_context": dict or None
        }
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Prepare payload
        payload = {
            "input": {
                "user_message": user_message,
                "extract_context": False  # LLM decides when to extract
            },
            "config": {
                "configurable": {
                    "thread_id": thread_id
                }
            }
        }

        # Call LangGraph
        response = await client.post(
            f"{LANGGRAPH_AGENT_URL}/voice/invoke",
            headers={"x-api-key": LANGGRAPH_API_KEY},
            json=payload
        )
        response.raise_for_status()

        result = response.json()

        return {
            "ai_response": result.get("output", {}).get("message", ""),
            "context_extracted": result.get("output", {}).get("context_extracted", False),
            "enriched_context": result.get("output", {}).get("enriched_context")
        }
```

---

## WebSocket Handler (Updated)

### Main Handler

```python
@router.websocket("/ws/{user_id}")
async def voice_assistant_websocket(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for voice conversation with LangGraph.

    Flow:
    1. Create LangGraph thread
    2. Get AI greeting → TTS → send to client
    3. Receive user audio → STT → send to LangGraph
    4. Get AI response → TTS → send to client
    5. Repeat until context extracted
    6. Trigger roadmap workflow
    7. Close connection
    """
    await websocket.accept()
    logger.info(f"🎤 Voice session started: {user_id}")

    # Verify user
    db = get_db()
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        await websocket.send_json({"type": "error", "message": "User not found"})
        await websocket.close()
        return

    try:
        # Create LangGraph thread
        thread_id = await create_langgraph_thread(user_id)
        logger.info(f"📝 Thread created: {thread_id}")

        # Get AI greeting
        greeting_result = await call_langgraph_voice_node(thread_id, user_message=None)
        ai_greeting = greeting_result["ai_response"]

        # Convert to speech
        greeting_audio = await text_to_speech(ai_greeting)
        greeting_base64 = base64.b64encode(greeting_audio).decode('utf-8')

        # Send greeting
        await websocket.send_json({"type": "audio", "data": greeting_base64})
        await websocket.send_json({"type": "text", "text": ai_greeting})
        await websocket.send_json({"type": "turn_complete"})
        logger.info(f"🔊 Sent greeting: {ai_greeting[:50]}...")

        # Conversation loop
        while True:
            # Receive user audio
            message = await websocket.receive_json()

            if message.get("type") != "audio":
                logger.warning(f"Unexpected message type: {message.get('type')}")
                continue

            # Decode and transcribe
            audio_data = base64.b64decode(message.get("data", ""))
            user_text = await transcribe_audio(audio_data)
            logger.info(f"📝 User said: {user_text}")

            # Call LangGraph
            response_result = await call_langgraph_voice_node(thread_id, user_message=user_text)

            # Check if context extracted
            if response_result["context_extracted"]:
                enriched_context = response_result["enriched_context"]
                user_request = enriched_context["user_dream"]

                logger.info(f"✅ Context extracted: {user_request}")

                # Trigger roadmap workflow
                await trigger_roadmap_workflow(
                    websocket=websocket,
                    user_id=user_id,
                    user_request=user_request,
                    enriched_context=enriched_context,
                    user_profile={"traits": user.get("traits", {}), "preferences": user.get("preferences", {})}
                )

                break

            # Get AI response
            ai_response = response_result["ai_response"]

            # Convert to speech
            response_audio = await text_to_speech(ai_response)
            response_base64 = base64.b64encode(response_audio).decode('utf-8')

            # Send response
            await websocket.send_json({"type": "audio", "data": response_base64})
            await websocket.send_json({"type": "text", "text": ai_response})
            await websocket.send_json({"type": "turn_complete"})
            logger.info(f"🔊 Sent response: {ai_response[:50]}...")

    except WebSocketDisconnect:
        logger.info(f"🔌 Client disconnected: {user_id}")
    except Exception as e:
        logger.error(f"❌ Voice session error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
        logger.info(f"🔒 Voice session closed: {user_id}")
```

### Helper Functions

```python
async def create_langgraph_thread(user_id: str) -> str:
    """Create LangGraph thread for voice conversation."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{LANGGRAPH_AGENT_URL}/threads",
            headers={"x-api-key": LANGGRAPH_API_KEY},
            json={"metadata": {"user_id": user_id, "type": "voice"}}
        )
        response.raise_for_status()
        return response.json()["thread_id"]


async def trigger_roadmap_workflow(
    websocket: WebSocket,
    user_id: str,
    user_request: str,
    enriched_context: dict,
    user_profile: dict
):
    """Trigger LangGraph roadmap generation workflow."""

    # Notify client
    await websocket.send_json({
        "type": "workflow_starting",
        "thread_id": f"dream_{user_id}_{uuid.uuid4().hex[:8]}",
        "user_request": user_request
    })

    # Create roadmap thread
    async with httpx.AsyncClient(timeout=120.0) as client:
        thread_response = await client.post(
            f"{LANGGRAPH_AGENT_URL}/threads",
            headers={"x-api-key": LANGGRAPH_API_KEY},
            json={"metadata": {"user_id": user_id}}
        )
        thread_response.raise_for_status()
        thread_id = thread_response.json()["thread_id"]

        # Start roadmap workflow
        run_payload = {
            "assistant_id": LANGGRAPH_ASSISTANT_ID,
            "input": {
                "user_id": user_id,
                "user_request": user_request,
                "enriched_context": enriched_context,
                "user_profile": user_profile,
                "status": "planning",
                "thread_id": thread_id
            }
        }

        run_response = await client.post(
            f"{LANGGRAPH_AGENT_URL}/threads/{thread_id}/runs/wait",
            headers={"x-api-key": LANGGRAPH_API_KEY},
            json=run_payload
        )
        run_response.raise_for_status()

        # Send completion
        await websocket.send_json({
            "type": "workflow_complete",
            "thread_id": thread_id,
            "user_request": user_request,
            "enriched_context": enriched_context
        })
```

---

## Error Handling

### 1. Whisper Transcription Errors

```python
try:
    user_text = await transcribe_audio(audio_data)
except Exception as e:
    await websocket.send_json({
        "type": "error",
        "message": "Could not understand audio. Please try again."
    })
    continue
```

### 2. Eleven Labs TTS Errors

```python
try:
    audio_bytes = await text_to_speech(text)
except Exception as e:
    # Fallback: send text only
    await websocket.send_json({
        "type": "text",
        "text": ai_response
    })
    await websocket.send_json({
        "type": "turn_complete"
    })
```

### 3. LangGraph Timeout

```python
try:
    response = await call_langgraph_voice_node(thread_id, user_text)
except httpx.TimeoutException:
    await websocket.send_json({
        "type": "error",
        "message": "AI is taking too long. Please try again."
    })
```

---

## Testing

### 1. Health Check

**Endpoint:** `GET /api/voice/health`

```python
@router.get("/health")
async def voice_health_check():
    """Check if all voice services are configured."""

    openai_ok = bool(os.getenv("OPENAI_API_KEY"))
    elevenlabs_ok = bool(os.getenv("ELEVENLABS_API_KEY"))
    langgraph_ok = bool(LANGGRAPH_AGENT_URL and LANGGRAPH_API_KEY)

    status = "healthy" if (openai_ok and elevenlabs_ok and langgraph_ok) else "degraded"

    return {
        "status": status,
        "services": {
            "whisper_stt": openai_ok,
            "elevenlabs_tts": elevenlabs_ok,
            "langgraph": langgraph_ok
        },
        "message": "Voice services ready" if status == "healthy" else "Missing API keys"
    }
```

### 2. Manual WebSocket Test

Use a WebSocket client (e.g., Postman, wscat):

```bash
# Connect
wscat -c "wss://your-backend.railway.app/api/voice/ws/test_user_123"

# You should receive:
# 1. {"type": "audio", "data": "..."}  (AI greeting)
# 2. {"type": "text", "text": "Hi! I'm here..."}
# 3. {"type": "turn_complete"}
```

---

## Cost Analysis

### Per Conversation (3 minutes, 3-4 turns)

| Service | Usage | Cost |
|---------|-------|------|
| Whisper STT | 3 min audio | $0.018 |
| Claude 3.5 Sonnet (LangGraph) | ~5K tokens | $0.025 |
| Eleven Labs TTS | ~300 chars | $0.09 |
| **Total** | | **$0.133** |

### Monthly (1000 conversations)

- **Total**: $133/month
- **Per user**: $0.13/conversation

**Trade-offs:**
- Higher cost than Gemini Live ($0.0002/conv)
- But: More reliable, better quality, easier to maintain

---

## Deployment Checklist

- [ ] Add `openai` and `elevenlabs` to `requirements.txt`
- [ ] Add API keys to Railway environment variables
- [ ] Update `api/voice.py` with new implementation
- [ ] Deploy to Railway
- [ ] Test health check endpoint
- [ ] Test WebSocket connection
- [ ] Verify audio quality
- [ ] Monitor costs

---

## Next Steps

1. Get API keys:
   - OpenAI: https://platform.openai.com/api-keys
   - Eleven Labs: https://elevenlabs.io/app/settings/api-keys

2. Implement LangGraph voice node (see `VOICE_CONVERSATION_PLAN.md` in LangGraph repo)

3. Update backend `api/voice.py`

4. Test locally

5. Deploy to Railway

6. Test end-to-end with mobile app

---

**Status:** Ready for implementation
**Risk:** Low
**Estimated effort:** 3-4 hours
