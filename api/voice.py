"""
Voice Assistant WebSocket Endpoint

Handles real-time voice conversations with users using Gemini 2.0 Live API,
then triggers LangGraph orchestration with enriched context.
"""

import asyncio
import logging
import json
import base64
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Optional
import httpx
from dotenv import load_dotenv
from google import genai
from datetime import datetime

from core.database import get_db

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LANGGRAPH_AGENT_URL = os.getenv("LANGGRAPH_AGENT_URL")
LANGGRAPH_API_KEY = os.getenv("LANGGRAPH_API_KEY")
LANGGRAPH_ASSISTANT_ID = os.getenv("LANGGRAPH_ASSISTANT_ID")


# ============================================================================
# CONVERSATION SYSTEM INSTRUCTION
# ============================================================================

VOICE_ASSISTANT_INSTRUCTION = """
You are a warm, encouraging dream coach helping people turn their goals into action plans.

CONVERSATION FLOW:

1. INTRODUCTION (Your first message):
   "Hi! I'm here to help you build a roadmap for your dreams. What's a goal or dream you'd like to work on?"

2. LISTEN TO THEIR DREAM:
   - Let them share in their own words
   - Acknowledge it warmly (e.g., "That sounds exciting!", "I love that!", "Great choice!")

3. ASK 1-2 CLARIFYING QUESTIONS (choose based on what's relevant):
   - Timeline: "Do you want to start on this soon, or are you exploring for now?"
   - Experience: "Have you done anything like this before?"
   - Motivation: "What's drawing you to this?"
   - Focus: "Is there a specific part you're most excited about?"

4. LISTEN FOR CONCERNS:
   - Notice if they mention blockers (time, money, fear, skills, etc.)
   - Don't probe deeply - just note them naturally
   - Be encouraging if they express doubt

5. WRAP UP (after 2-3 exchanges):
   "Got it! I have what I need to create your personalized roadmap. Give me just a moment..."
   - Then call end_conversation function with all the details you gathered

RULES:
- Keep it conversational and brief (2-3 min max total conversation)
- Ask ONE question at a time
- Don't sound like a form or survey
- Be warm but efficient
- If they give short answers, don't push - move forward
- Never repeat questions they already answered
- If they seem unsure about timeline/experience, that's okay - just note "not_mentioned"
"""


# ============================================================================
# FUNCTION DECLARATION FOR CONTEXT EXTRACTION
# ============================================================================

def end_conversation(
    user_dream: str,
    timeline_preference: str,
    experience_level: str,
    primary_motivation: str,
    conversation_summary: str,
    specific_focus: str = "",
    concerns: list[str] = None
):
    """
    Call this when you have gathered enough context about the user's dream.
    Required after introduction and 1-2 clarifying questions.

    Args:
        user_dream: The goal/dream the user shared in their own words
        timeline_preference: When user wants to achieve this (immediate, few_months, year_plus, exploring, not_mentioned)
        experience_level: User's familiarity with this domain (complete_beginner, some_experience, intermediate, not_mentioned)
        primary_motivation: Why the user wants this (exact words if possible, or 'not_mentioned')
        conversation_summary: 2-3 sentence summary of the conversation for context
        specific_focus: Any specific aspect they mentioned (e.g., 'travel vlogs' for YouTube channel), or empty string if none
        concerns: Any blockers or worries mentioned (empty list if none)
    """
    if concerns is None:
        concerns = []

    return {
        "user_dream": user_dream,
        "timeline_preference": timeline_preference,
        "experience_level": experience_level,
        "primary_motivation": primary_motivation,
        "specific_focus": specific_focus,
        "concerns": concerns,
        "conversation_summary": conversation_summary,
        "user_engaged": True
    }


# ============================================================================
# VOICE ASSISTANT CLIENT
# ============================================================================

class VoiceAssistantSession:
    """Manages a single Gemini 2.0 Live API session."""

    def __init__(self):
        # Use v1alpha API version for Gemini 2.0 Live API features
        self.client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={'api_version': 'v1alpha'}
        )
        # Use the correct model name for Live API (bidiGenerateContent)
        # Reference: https://github.com/google/adk-python/issues/866
        self.model = "gemini-2.0-flash-live-001"
        self.enriched_context = None

    async def run_conversation(self, websocket: WebSocket) -> Optional[dict]:
        """
        Run voice conversation and extract enriched context.

        Args:
            websocket: WebSocket connection for bidirectional audio streaming

        Returns:
            enriched_context dict or None
        """
        config = {
            "system_instruction": VOICE_ASSISTANT_INSTRUCTION,
            "tools": [end_conversation],
            "response_modalities": ["AUDIO"],
        }

        try:
            async with self.client.aio.live.connect(
                model=self.model,
                config=config
            ) as session:
                logger.info("🎤 Gemini Live session started")

                # Create tasks for bidirectional streaming
                send_task = asyncio.create_task(
                    self._send_audio_from_client(websocket, session)
                )
                receive_task = asyncio.create_task(
                    self._receive_responses(websocket, session)
                )

                # Wait for conversation to complete
                done, pending = await asyncio.wait(
                    [send_task, receive_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel remaining tasks
                for task in pending:
                    task.cancel()

                # Extract result
                for task in done:
                    if not task.exception():
                        result = task.result()
                        if result and isinstance(result, dict):
                            self.enriched_context = result
                            break

        except Exception as e:
            logger.error(f"❌ Gemini Live session error: {e}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "message": f"Voice session error: {str(e)}"
            })

        return self.enriched_context

    async def _send_audio_from_client(self, websocket: WebSocket, session):
        """Stream audio from client to Gemini."""
        try:
            while True:
                message = await websocket.receive_json()

                if message.get("type") == "audio":
                    # Decode base64 audio and send to Gemini
                    audio_data = base64.b64decode(message.get("data", ""))
                    await session.send(input=audio_data, end_of_turn=False)

                elif message.get("type") == "end_audio":
                    # User finished speaking for this turn
                    break

        except WebSocketDisconnect:
            logger.info("Client disconnected during audio send")
        except Exception as e:
            logger.error(f"Error sending audio to Gemini: {e}")

    async def _receive_responses(self, websocket: WebSocket, session):
        """Receive responses from Gemini and send to client."""
        try:
            async for response in session.receive():
                # Check for function call (end_conversation)
                if response.tool_call:
                    logger.info("🎯 Function call received: end_conversation")

                    for part in response.server_content.model_turn.parts:
                        if hasattr(part, 'function_call'):
                            func_call = part.function_call
                            if func_call.name == "end_conversation":
                                # Extract arguments and call the function to get enriched context
                                args = dict(func_call.args)
                                logger.info(f"📦 Extracted context: {json.dumps(args, indent=2)}")

                                # Call the function to get formatted context
                                enriched_context = end_conversation(**args)

                                # Notify client
                                await websocket.send_json({
                                    "type": "conversation_complete",
                                    "enriched_context": enriched_context
                                })

                                return enriched_context

                # Handle audio/text responses
                if response.server_content:
                    for part in response.server_content.model_turn.parts:
                        # Audio response - send to client
                        if hasattr(part, 'inline_data'):
                            audio_bytes = part.inline_data.data
                            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                            await websocket.send_json({
                                "type": "audio",
                                "data": audio_base64
                            })

                        # Text response - send for transcript
                        if hasattr(part, 'text'):
                            await websocket.send_json({
                                "type": "text",
                                "text": part.text
                            })

        except Exception as e:
            logger.error(f"Error receiving from Gemini: {e}", exc_info=True)

        return None


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws/{user_id}")
async def voice_assistant_websocket(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for voice conversation.

    Flow:
    1. Client connects
    2. Server initiates Gemini 2.0 Live session
    3. Bidirectional audio streaming
    4. Extract enriched_context when conversation completes
    5. Trigger LangGraph workflow with enriched context
    6. Return thread_id to client
    7. Close connection
    """

    await websocket.accept()
    logger.info(f"🎤 WebSocket connection established for user: {user_id}")

    try:
        # ========================================================================
        # STEP 1: Verify user exists in database
        # ========================================================================

        db = get_db()
        if db is None:
            await websocket.send_json({
                "type": "error",
                "message": "Database not connected"
            })
            await websocket.close()
            return

        user = await db.users.find_one({"user_id": user_id})
        if not user:
            await websocket.send_json({
                "type": "error",
                "message": "User not found"
            })
            await websocket.close()
            return

        logger.info(f"✅ User verified: {user.get('firstname', 'Unknown')}")

        # ========================================================================
        # STEP 2: Run voice conversation
        # ========================================================================

        voice_session = VoiceAssistantSession()
        enriched_context = await voice_session.run_conversation(websocket)

        if not enriched_context or not enriched_context.get("user_dream"):
            await websocket.send_json({
                "type": "error",
                "message": "Failed to extract dream from conversation"
            })
            await websocket.close()
            return

        logger.info(f"✅ Context extracted: {enriched_context['user_dream']}")

        # ========================================================================
        # STEP 3: Trigger LangGraph workflow
        # ========================================================================

        user_request = enriched_context["user_dream"]

        # Create LangGraph thread
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                # Create thread
                thread_response = await client.post(
                    f"{LANGGRAPH_AGENT_URL}/threads",
                    headers={"x-api-key": LANGGRAPH_API_KEY},
                    json={"metadata": {"user_id": user_id}}
                )
                thread_response.raise_for_status()
                thread_data = thread_response.json()
                thread_id = thread_data["thread_id"]

                logger.info(f"📝 Thread created: {thread_id}")

                # Prepare input with enriched context
                run_payload = {
                    "assistant_id": LANGGRAPH_ASSISTANT_ID,
                    "input": {
                        "user_id": user_id,
                        "user_request": user_request,
                        "enriched_context": enriched_context,  # Voice conversation context
                        "user_profile": {
                            "traits": user.get("traits", {}),
                            "preferences": user.get("preferences", {})
                        },
                        "status": "planning",
                        "thread_id": thread_id
                    }
                }

                # Notify client that workflow is starting
                await websocket.send_json({
                    "type": "workflow_starting",
                    "thread_id": thread_id,
                    "user_request": user_request
                })

                # Start workflow run (async)
                run_response = await client.post(
                    f"{LANGGRAPH_AGENT_URL}/threads/{thread_id}/runs/wait",
                    headers={"x-api-key": LANGGRAPH_API_KEY},
                    json=run_payload
                )
                run_response.raise_for_status()

                logger.info(f"🚀 Workflow completed for thread: {thread_id}")

                # Send success to client
                await websocket.send_json({
                    "type": "workflow_complete",
                    "thread_id": thread_id,
                    "user_request": user_request,
                    "enriched_context": enriched_context
                })

            except httpx.HTTPError as e:
                logger.error(f"LangGraph API error: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"Failed to start roadmap generation: {str(e)}"
                })

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected for user: {user_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}", exc_info=True)
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
        logger.info(f"🔒 WebSocket connection closed for user: {user_id}")


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/health")
async def voice_assistant_health():
    """Health check for voice assistant service."""

    gemini_configured = bool(GEMINI_API_KEY)
    langgraph_configured = bool(LANGGRAPH_AGENT_URL and LANGGRAPH_API_KEY)

    status = "healthy" if (gemini_configured and langgraph_configured) else "degraded"

    return {
        "status": status,
        "gemini_api_key_configured": gemini_configured,
        "langgraph_configured": langgraph_configured,
        "message": "Voice assistant service is ready" if status == "healthy"
                   else "Missing configuration (check GEMINI_API_KEY and LANGGRAPH_*)"
    }
