# DEPRECATED - Gemini Live Voice Implementation

This voice assistant implementation using Gemini 2.0 Live API has been deprecated in favor of a LangGraph supervisor node approach with dedicated text-to-speech.

**Issues encountered:**
- Audio streaming chunk buffering complexity
- Inconsistent turn-based conversation flow
- Connection termination before proper conversation completion

**New Approach:**
- LangGraph supervisor node handles conversation logic
- Eleven Labs (or similar) for text-to-speech
- Clearer turn-based architecture
- Better error handling and state management

**Files:**
- `api/voice.py` - WebSocket endpoint (deprecated)
- `VOICE_ASSISTANT_README.md` - Documentation (deprecated)

**Date Deprecated:** 2026-02-01

See the new implementation in the LangGraph repository.

