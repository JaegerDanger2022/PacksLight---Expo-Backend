# Voice Assistant Implementation

## Overview

The Voice Assistant feature uses **Gemini 2.0 Live API** to conduct natural voice conversations with users before generating personalized roadmaps.

## Quick Start

### 1. Environment Setup

Ensure your `.env` file has:

```bash
# Gemini API Key
GEMINI_API_KEY=your_actual_api_key_here

# LangGraph Configuration
LANGGRAPH_AGENT_URL=http://localhost:8002
LANGGRAPH_API_KEY=your_langgraph_api_key
LANGGRAPH_ASSISTANT_ID=your_assistant_id

# MongoDB
MONGODB_URL=your_mongodb_url
MONGODB_DB_NAME=dream_to_do
```

### 2. Install Dependencies

```bash
pip install google-genai --upgrade
```

### 3. Start the Backend

```bash
uvicorn main:app --reload --port 8001
```

### 4. Test the Service

```bash
# Health check
curl http://localhost:8001/api/voice/health
```

## WebSocket Endpoint

### URL
```
ws://localhost:8001/api/voice/ws/{user_id}
```

### Message Protocol

**Client → Server (Audio):**
```json
{
  "type": "audio",
  "data": "base64_encoded_16bit_pcm_16khz_mono_audio"
}
```

**Server → Client (Audio):**
```json
{
  "type": "audio",
  "data": "base64_encoded_audio_response"
}
```

**Server → Client (Text/Transcript):**
```json
{
  "type": "text",
  "text": "Assistant's spoken message"
}
```

**Server → Client (Conversation Complete):**
```json
{
  "type": "conversation_complete",
  "enriched_context": {
    "user_dream": "start a travel vlog YouTube channel",
    "timeline_preference": "few_months",
    "experience_level": "complete_beginner",
    "primary_motivation": "loves traveling",
    "specific_focus": "travel vlogs",
    "concerns": ["nervous", "new to content creation"],
    "conversation_summary": "User wants to start...",
    "user_engaged": true
  }
}
```

**Server → Client (Workflow Complete):**
```json
{
  "type": "workflow_complete",
  "thread_id": "dream_user123_xyz",
  "user_request": "start a travel vlog YouTube channel",
  "enriched_context": {...}
}
```

**Server → Client (Error):**
```json
{
  "type": "error",
  "message": "Error description"
}
```

## Conversation Flow

1. **Greeting (Assistant initiates):**
   - "Hi! I'm here to help you build a roadmap for your dreams. What's a goal or dream you'd like to work on?"

2. **User shares dream:**
   - "I want to start a YouTube channel"

3. **Assistant asks 1-2 clarifying questions:**
   - "Have you done any content creation before?"
   - "Is there a specific type of content you're thinking about?"
   - "Do you want to start soon, or just exploring?"

4. **Assistant extracts context:**
   - Uses function calling to structure the conversation details

5. **Trigger LangGraph workflow:**
   - Sends enriched_context to LangGraph orchestration service
   - Architect generates personalized roadmap using conversation insights

## Integration with LangGraph

The voice assistant sends the following to LangGraph:

```python
{
    "user_id": "user_123",
    "user_request": "start a travel vlog YouTube channel",  # From conversation
    "enriched_context": {
        "user_dream": "...",
        "timeline_preference": "few_months",
        "experience_level": "complete_beginner",
        "primary_motivation": "loves traveling",
        "specific_focus": "travel vlogs",
        "concerns": ["nervous", "new to content creation"],
        "conversation_summary": "...",
        "user_engaged": true
    },
    "user_profile": {
        "traits": {...},
        "preferences": {...}
    },
    "status": "planning",
    "thread_id": "generated_thread_id"
}
```

The LangGraph architect node then uses this enriched context to:
- Adjust milestone difficulty based on experience level
- Respect timeline preferences
- Address specific concerns proactively
- Focus on the user's specific interest area

## Audio Format Requirements

### Input (Client → Server)
- **Format**: 16-bit PCM
- **Sample Rate**: 16kHz
- **Channels**: Mono
- **Encoding**: Base64

### Output (Server → Client)
- **Format**: Audio bytes (base64 encoded)
- **Playable** directly in browser or mobile app

## API Reference

### Health Check

**GET** `/api/voice/health`

**Response:**
```json
{
  "status": "healthy",
  "gemini_api_key_configured": true,
  "langgraph_configured": true,
  "message": "Voice assistant service is ready"
}
```

## Files

- [`api/voice.py`](api/voice.py) - WebSocket endpoint and Gemini 2.0 Live integration
- [`main.py`](main.py) - Router registration (line 7 + 82)

## Related Documentation

- [Full Voice Assistant Guide](../PacksLight---Dream-to-do-challenges/VOICE_ASSISTANT_GUIDE.md)
- [Gemini 2.0 Live API Docs](https://ai.google.dev/gemini-api/docs/live)
- [Google AI Studio](https://aistudio.google.com/apikey)

## Cost Considerations

### Google AI Studio (Current Setup)
- **Pricing**: ~$0.075 per million tokens
- **Per Conversation**: $0.00015 - $0.00038
- **Best For**: Development and testing

### Vertex AI (Production)
- **Pricing**: ~$0.018 per million tokens (4x cheaper)
- **Per Conversation**: $0.00004 - $0.00009
- **Best For**: Production deployments

## Troubleshooting

### "GEMINI_API_KEY not configured"
- Check `.env` file has valid `GEMINI_API_KEY`
- Restart the server after updating `.env`

### "LangGraph not configured"
- Verify `LANGGRAPH_AGENT_URL`, `LANGGRAPH_API_KEY`, and `LANGGRAPH_ASSISTANT_ID` are set
- Ensure LangGraph orchestration service is running

### WebSocket Connection Fails
- Ensure backend is running on port 8001
- Check CORS settings allow WebSocket connections
- Verify user_id exists in database

### Audio Not Working
- Verify audio format is 16-bit PCM, 16kHz, mono
- Check base64 encoding is correct
- Test with raw audio bytes first

## Next Steps

1. **Build Frontend Client** - Implement WebSocket with audio streaming
2. **Add Authentication** - Secure WebSocket with JWT tokens
3. **Test End-to-End** - Connect voice → backend → LangGraph → roadmap
4. **Monitor Usage** - Track conversation quality and completion rates
5. **Switch to Vertex AI** - For production cost savings
