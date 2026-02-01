# Voice Conversation Deployment Fix

## Problem
The backend was calling `/voice_conversation/invoke` endpoint which didn't exist, causing 404 errors.

## Solution
Added `voice_conversation` as a separate graph in LangGraph deployment.

## Changes Made

### LangGraph Repository

#### 1. services/voice_conversation.py
- Added `user_message` field to `VoiceConversationState` TypedDict
- This allows the backend to pass user messages as input to the graph

#### 2. services/voice_graph.py (NEW)
- Created standalone voice conversation graph
- Processes ONE conversation turn per invocation
- Backend handles the conversation loop via WebSocket
- Flow: `prepare_input` → `voice_conversation` → END
- `prepare_input` node converts `user_message` string to LangChain `HumanMessage`

#### 3. langgraph.json
Updated deployment configuration:
```json
{
  "graphs": {
    "packslight": "services/build.py:workflow",
    "voice_conversation": "services/voice_graph.py:voice_workflow"
  }
}
```

## How It Works Now

### Turn-by-Turn Conversation Flow

1. **Backend** opens WebSocket connection for user
2. **Backend** calls LangGraph `/voice_conversation/invoke` with empty input
3. **LangGraph** generates AI greeting
4. **Backend** converts greeting to speech (Eleven Labs) and sends to client
5. **User** speaks
6. **Backend** transcribes (Whisper) and calls `/voice_conversation/invoke` with user_message
7. **LangGraph** generates AI response
8. **Backend** converts to speech and sends to client
9. **Repeat steps 5-8** until LangGraph calls `extract_dream_context()` function
10. **Backend** receives `enriched_context` in response
11. **Backend** calls `/api/dreams/create` to trigger main roadmap workflow

### Why Separate Graph?

The main `packslight` workflow includes routing that would automatically proceed to architect → gamification → image generation after voice conversation completes. For WebSocket use case, we need to:

- Return after each conversation turn (not loop in LangGraph)
- Let backend handle conversation loop and audio streaming
- Only trigger main workflow after context is fully extracted

## Testing

After deployment completes (usually 2-3 minutes after push):

1. Check LangGraph deployment status:
   ```
   https://smith.langchain.com/
   ```

2. Test voice endpoint health:
   ```
   curl https://<backend-url>/api/voice/health
   ```

3. Test WebSocket connection from frontend

## Expected Behavior

- WebSocket connects successfully
- User hears AI greeting
- Conversation proceeds turn-by-turn
- After 2-3 exchanges, context extracted
- Roadmap creation workflow triggered
- User sees new dream in app

## Deployment Status

Pushed to `demo` branch at: 2026-02-01
Commit: a54de05 "Add voice_conversation graph for WebSocket voice assistant"

LangGraph Platform will auto-deploy within 2-3 minutes.
