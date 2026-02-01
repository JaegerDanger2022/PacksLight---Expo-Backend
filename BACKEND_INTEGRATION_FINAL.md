# Backend Integration Guide - Voice Conversation

**For:** PacksLight---Expo-Backend
**LangGraph:** Voice conversation node integrated in workflow
**Your Role:** Handle STT/TTS and stream to/from LangGraph

---

## Architecture Overview

```
Frontend (React Native)
    ↓ WebSocket
Backend (You)
    ↓ 1. STT (Whisper): audio → text
    ↓ 2. Call LangGraph with text
    ↓ 3. Get AI response text
    ↓ 4. TTS (Eleven Labs): text → audio
    ↓ WebSocket
Frontend (React Native)
```

The LangGraph workflow now handles the conversation logic. You just handle:
1. **Speech-to-Text** (Whisper)
2. **Text-to-Speech** (Eleven Labs)
3. **Streaming** between frontend and LangGraph

---

## LangGraph Workflow Changes

### New Flow in build.py

```
Entry Point (conditional)
    ↓
    ├─ If user_request → architect (TEXT MODE)
    ├─ If enriched_context → architect (VOICE MODE - context ready)
    └─ If neither → voice_conversation (VOICE MODE - start conversation)
            ↓ (loops 2-3 times)
            enriched_context extracted
            ↓
        architect → gamification → image → persistence
```

The `voice_conversation` node:
- Takes user messages via state
- Returns AI responses via state
- Loops until enriched_context is complete
- Then routes to architect automatically

---

## Backend Implementation

### 1. Install Dependencies

```bash
# Add to requirements.txt
openai>=1.0.0
elevenlabs>=1.0.0
httpx>=0.25.2
```

```bash
pip install openai elevenlabs httpx
```

### 2. Environment Variables

```bash
# Add to .env
OPENAI_API_KEY=sk-proj-your_key_here
ELEVENLABS_API_KEY=sk_your_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel voice

# Existing
LANGGRAPH_AGENT_URL=https://your-langgraph-deployment-url
```

### 3. Create WebSocket Endpoint

**File:** `PacksLight---Expo-Backend/api/voice.py`

```python
"""
Voice Assistant WebSocket Endpoint

Handles STT/TTS and streams to/from LangGraph voice conversation workflow.
"""

import os
import base64
import logging
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI
from elevenlabs import AsyncElevenLabs

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize API clients
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elevenlabs_client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
LANGGRAPH_URL = os.getenv("LANGGRAPH_AGENT_URL")


# ============================================================================
# STT / TTS HELPERS
# ============================================================================

async def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio using OpenAI Whisper"""
    try:
        response = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", audio_bytes, "audio/wav")
        )
        return response.text
    except Exception as e:
        logger.error(f"[STT ERROR] {e}")
        raise


async def text_to_speech(text: str) -> bytes:
    """Convert text to speech using Eleven Labs"""
    try:
        audio_generator = await elevenlabs_client.generate(
            text=text,
            voice=VOICE_ID,
            model="eleven_multilingual_v2"
        )

        audio_bytes = b""
        async for chunk in audio_generator:
            if chunk:
                audio_bytes += chunk

        return audio_bytes
    except Exception as e:
        logger.error(f"[TTS ERROR] {e}")
        raise


# ============================================================================
# LANGGRAPH STREAMING HELPERS
# ============================================================================

async def stream_langgraph_workflow(
    user_id: str,
    thread_id: str = None,
    user_message: str = None
) -> dict:
    """
    Stream workflow updates from LangGraph.

    The workflow will:
    - Start voice_conversation node if no input provided
    - Loop voice_conversation until enriched_context is extracted
    - Then continue to architect → gamification → image → persistence

    Args:
        user_id: User ID
        thread_id: Thread ID for conversation continuity (optional, LangGraph creates if None)
        user_message: User's transcribed message (None for first call to get greeting)

    Returns:
        Last update from workflow (contains AI response or final roadmap)
    """
    async with httpx.AsyncClient() as client:
        # Build initial state
        state = {
            "user_id": user_id,
            "messages": [],
            "user_request": None,  # Voice mode - no text request
            "user_profile": {"traits": {}, "preferences": {}},
            "research_data": {},
            "roadmap": {},
            "status": "planning",
            "enriched_context": None
        }

        # If user_message provided, add to messages
        if user_message:
            from langchain_core.messages import HumanMessage
            state["messages"] = [HumanMessage(content=user_message)]

        # Stream workflow
        url = f"{LANGGRAPH_URL}/stream"
        if thread_id:
            url += f"?thread_id={thread_id}"

        async with client.stream(
            "POST",
            url,
            json={"input": state},
            timeout=120.0
        ) as response:
            response.raise_for_status()

            last_update = None
            async for line in response.aiter_lines():
                if line.strip():
                    # Parse server-sent events
                    if line.startswith("data: "):
                        import json
                        data = json.loads(line[6:])
                        last_update = data

            return last_update


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws/{user_id}")
async def voice_assistant_websocket(websocket: WebSocket, user_id: str):
    """
    Voice conversation WebSocket endpoint.

    Protocol:
    1. Client connects
    2. Server calls LangGraph (gets AI greeting)
    3. Server sends TTS audio to client
    4. Client sends user audio
    5. Server transcribes (STT)
    6. Server calls LangGraph with transcribed text
    7. Server sends AI response audio
    8. Repeat 4-7 until LangGraph extracts enriched_context
    9. LangGraph continues to architect → returns roadmap
    10. Server sends roadmap to client
    """
    await websocket.accept()
    logger.info(f"🎤 Voice session started: {user_id}")

    thread_id = None  # LangGraph will create and return thread_id

    try:
        # ====================================================================
        # STEP 1: Get AI greeting from LangGraph
        # ====================================================================

        logger.info("[1] Getting AI greeting from LangGraph...")
        result = await stream_langgraph_workflow(user_id, thread_id=None, user_message=None)

        # Extract thread_id for conversation continuity
        thread_id = result.get("thread_id")
        logger.info(f"[1] Thread ID: {thread_id}")

        # Get AI response from voice_conversation node
        ai_text = None
        if "voice_conversation" in result:
            messages = result["voice_conversation"].get("messages", [])
            if messages:
                ai_text = messages[-1].content

        if not ai_text:
            raise Exception("No AI greeting received")

        logger.info(f"[1] AI greeting: {ai_text}")

        # Convert to speech
        audio_bytes = await text_to_speech(ai_text)
        audio_base64 = base64.b64encode(audio_bytes).decode()

        # Send to client
        await websocket.send_json({
            "type": "audio",
            "data": audio_base64
        })
        await websocket.send_json({
            "type": "text",
            "text": ai_text
        })
        await websocket.send_json({"type": "turn_complete"})

        # ====================================================================
        # STEP 2: Conversation loop
        # ====================================================================

        while True:
            # Wait for user audio
            message = await websocket.receive_json()

            if message.get("type") == "audio":
                # Transcribe user audio
                logger.info("[2] Transcribing user audio...")
                audio_data = base64.b64decode(message.get("data", ""))
                user_text = await transcribe_audio(audio_data)
                logger.info(f"[2] User: {user_text}")

                # Send transcript back
                await websocket.send_json({
                    "type": "user_transcript",
                    "text": user_text
                })

                # Call LangGraph with user message
                logger.info("[2] Calling LangGraph...")
                result = await stream_langgraph_workflow(
                    user_id,
                    thread_id=thread_id,
                    user_message=user_text
                )

                # Check if we have a roadmap (conversation complete)
                if "roadmap" in result and result["roadmap"]:
                    logger.info("[2] Roadmap complete!")
                    await websocket.send_json({
                        "type": "workflow_complete",
                        "roadmap": result["roadmap"],
                        "status": result.get("status")
                    })
                    break

                # Get AI response from voice_conversation node
                ai_text = None
                if "voice_conversation" in result:
                    messages = result["voice_conversation"].get("messages", [])
                    if messages:
                        ai_text = messages[-1].content

                if not ai_text:
                    logger.warning("[2] No AI response, conversation may be complete")
                    continue

                logger.info(f"[2] AI: {ai_text}")

                # Convert to speech
                audio_bytes = await text_to_speech(ai_text)
                audio_base64 = base64.b64encode(audio_bytes).decode()

                # Send to client
                await websocket.send_json({
                    "type": "audio",
                    "data": audio_base64
                })
                await websocket.send_json({
                    "type": "text",
                    "text": ai_text
                })
                await websocket.send_json({"type": "turn_complete"})

            elif message.get("type") == "end":
                logger.info("[2] User ended conversation")
                break

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {user_id}")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
```

### 4. Register Router

**File:** `PacksLight---Expo-Backend/main.py`

```python
from api import voice

app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
```

---

## Testing

### 1. Test STT/TTS

```python
# Test Whisper
audio_bytes = open("test.wav", "rb").read()
text = await transcribe_audio(audio_bytes)
print(f"Transcribed: {text}")

# Test Eleven Labs
audio = await text_to_speech("Hello, how are you?")
open("output.mp3", "wb").write(audio)
```

### 2. Test WebSocket

```python
import websockets
import json
import base64

async def test():
    uri = "ws://localhost:8000/api/voice/ws/test_user"
    async with websockets.connect(uri) as ws:
        # Receive greeting
        msg = await ws.recv()
        print(json.loads(msg))

        # Send audio
        audio = open("user_audio.wav", "rb").read()
        await ws.send(json.dumps({
            "type": "audio",
            "data": base64.b64encode(audio).decode()
        }))

        # Receive response
        msg = await ws.recv()
        print(json.loads(msg))
```

---

## WebSocket Protocol

### Client → Server

```json
{"type": "audio", "data": "base64_wav_audio"}
{"type": "end"}
```

### Server → Client

```json
{"type": "audio", "data": "base64_mp3_audio"}
{"type": "text", "text": "AI message"}
{"type": "user_transcript", "text": "What user said"}
{"type": "turn_complete"}
{"type": "workflow_complete", "roadmap": {...}, "status": "completed"}
{"type": "error", "message": "Error description"}
```

---

## Cost Per Conversation

- Whisper STT: $0.02
- Claude 3.5 Sonnet: $0.003
- Eleven Labs TTS: $0.10
- **Total: ~$0.13**

---

## Next Steps

1. ✅ LangGraph workflow updated (voice node added)
2. ⏳ Implement WebSocket endpoint in backend
3. ⏳ Add OpenAI/Eleven Labs API keys
4. ⏳ Test STT/TTS
5. ⏳ Test full flow
6. ⏳ Frontend integration

---

**Ready to implement!** See [FRONTEND_INTEGRATION_FINAL.md](FRONTEND_INTEGRATION_FINAL.md) for frontend guide.
