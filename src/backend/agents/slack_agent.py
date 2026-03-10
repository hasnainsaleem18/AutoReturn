"""
# -------------------------
# SLACK AGENT
# -------------------------
Bridge between AutoReturn and Slack API.
Fetches Slack messages and enriches each with Priority Score, Task
Classification, Tone Detection, and Calendar Event extraction.
"""

import asyncio
from typing import List, Dict, Optional
from src.backend.agents.base_agent import BaseAgent
from src.backend.models.agent_models import AgentRequest, AgentResponse, Intent
from src.backend.services.slack_backend import SlackService
from src.backend.services.ai_service import OllamaService
from src.backend.core.priority_engine import PriorityEngine
from src.backend.core.event_extractor import EventExtractor


class SlackAgent(BaseAgent):
    """Intelligent Slack agent with Priority Engine, Task Classifier, and Tone Detection."""

    # -------------------------
    # CONSTRUCTOR: INITIALIZE ALL COMPONENTS
    # Sets up the Slack backend connection, Priority Engine, and Event Extractor.
    # Tone Engine is injected later by the Orchestrator after startup.
    # -------------------------
    def __init__(self, ai_service: OllamaService):
        super().__init__(name="slack_agent")
        self.backend         = SlackService()        # Slack API wrapper
        self.ai_service      = ai_service            # Ollama AI connection
        self.priority_engine = PriorityEngine()      # Custom scoring algorithm (same as Gmail)
        self.tone_engine     = None                  # Set by Orchestrator
        self.event_extractor = EventExtractor(
            ai_service=self.ai_service,
            enable_llm_fallback=True,
            confidence_threshold=0.85
        )
        print(f"{self.name} initialized with AI capabilities and Priority Engine")

    # -------------------------
    # SET TONE ENGINE
    # Receives the shared Tone Engine from the Orchestrator and stores it.
    # Same engine used by Gmail Agent — tone preferences work across both platforms.
    # -------------------------
    def set_tone_engine(self, tone_engine):
        self.tone_engine = tone_engine

    # -------------------------
    # SET TONE MANAGER (BACKWARD COMPAT)
    # Old alias for set_tone_engine — kept so older code still works.
    # -------------------------
    def set_tone_manager(self, tone_manager):
        self.set_tone_engine(tone_manager)

    # -------------------------
    # MAIN REQUEST ROUTER
    # Entry point called by the Orchestrator to handle any Slack request.
    # Reads the intent field and routes to the correct handler function.
    # -------------------------
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        try:
            if request.intent == Intent.FETCH_MESSAGES:
                return await self._handle_fetch(request)
            elif request.intent == Intent.SEND_MESSAGE:
                return await self._handle_send(request)
            elif request.intent == Intent.SUMMARIZE:
                return await self._handle_summarize(request)
            elif request.intent == Intent.ANALYZE_PRIORITY:
                return await self._handle_priority(request)
            else:
                return self.error_response(f"Unsupported intent: {request.intent}")
        except Exception as e:
            return self.error_response(f"Slack agent error: {str(e)}")

    # -------------------------
    # FETCH AND ENRICH SLACK MESSAGES
    # Pulls raw messages from Slack API, then runs Priority Engine, Tone Detector,
    # Task Classifier, and Event Extractor on every message in parallel.
    # Marks each message for background summarization without blocking.
    # -------------------------
    async def _handle_fetch(self, request: AgentRequest) -> AgentResponse:
        limit  = request.parameters.get("limit", 200)
        add_ai = request.parameters.get("add_ai_analysis", True)

        messages = self.backend.sync_all_messages(limit=limit)

        if add_ai and messages:
            print(f"Slack Agent: Analyzing priority/tone for {len(messages)} messages...")

            async def process_slack_msg_light(msg):
                try:
                    # Run Priority Algorithm (High / Medium / Low)
                    priority_label           = await self._analyze_priority(msg)
                    msg['ai_priority_score'] = priority_label
                    msg['priority']          = priority_label   # UI badge reads this field

                    # Run Tone Detector (formal_leaning / informal_leaning / neutral)
                    msg['ai_tone_signal']    = await self._analyze_tone(msg)

                    # Run Task Classifier (File Attachment / Draft / Auto Reply / etc.)
                    msg['ai_tasks']          = self._classify_task(msg)

                    # Run Calendar Event Extractor (meeting dates/times)
                    try:
                        events               = await self.event_extractor.extract_from_message(msg)
                        msg['ai_events']     = [e.model_dump(mode="json") for e in events] if events else []
                        msg['ai_events_count'] = len(msg['ai_events'])
                    except Exception as e:
                        print(f"Slack schedule extraction error: {e}")

                    # Leave summary blank so background queue fills it later
                    if not msg.get('summary'):
                        msg['summary'] = ""
                except Exception as e:
                    print(f"Slack processing error: {e}")
                return msg

            # Process all messages simultaneously for maximum speed
            import asyncio
            processed_messages = await asyncio.gather(*[process_slack_msg_light(m) for m in messages], return_exceptions=True)
            messages           = [m for m in processed_messages if isinstance(m, dict)]
            print("Slack Agent: Initial processing complete")

        return self.success_response(data={"messages": messages, "count": len(messages)})

    # -------------------------
    # SEND MESSAGE HANDLER
    # Handles outgoing Slack message send requests routed from the Orchestrator.
    # Actual sending is done through the Send Dialog (not this agent directly).
    # -------------------------
    async def _handle_send(self, request: AgentRequest) -> AgentResponse:
        return self.error_response("Send functionality not yet implemented")

    # -------------------------
    # SUMMARIZE A SINGLE MESSAGE
    # Called when the user wants an on-demand AI summary for one specific Slack message.
    # Uses the AI service to generate a short 1-2 sentence summary.
    # -------------------------
    async def _handle_summarize(self, request: AgentRequest) -> AgentResponse:
        message = request.parameters.get("message")
        if not message:
            return self.error_response("No message provided for summarization")
        summary = await self._generate_summary(message)
        return self.success_response(data={"summary": summary})

    # -------------------------
    # ANALYZE PRIORITY FOR ONE MESSAGE
    # Directly runs the Priority Engine on a single Slack message and returns the label.
    # Same algorithm as Gmail — consistent scoring across both platforms.
    # -------------------------
    async def _handle_priority(self, request: AgentRequest) -> AgentResponse:
        message = request.parameters.get("message")
        if not message:
            return self.error_response("No message provided for priority analysis")
        priority_score = await self._analyze_priority(message)
        return self.success_response(data={"priority_score": priority_score})

    # -------------------------
    # GENERATE AI SUMMARY (INTERNAL)
    # Passes Slack message content to Ollama and returns a short summary.
    # Falls back from full_content to text preview if body is unavailable.
    # -------------------------
    async def _generate_summary(self, message: Dict) -> str:
        try:
            content = message.get('full_content') or message.get('text', '')
            if not content or len(content.strip()) < 10:
                return "No content to summarize"
            summary = await self.ai_service.generate_summary_async(content)
            return summary or "Summary unavailable"
        except Exception as e:
            print(f"Summary generation failed: {e}")
            return "Summary unavailable"

    # -------------------------
    # RUN PRIORITY ENGINE (INTERNAL)
    # Passes the full message dict to Priority Engine's calculate_priority method.
    # Returns "High", "Medium", or "Low" based on the weighted urgency formula.
    # -------------------------
    async def _analyze_priority(self, message: Dict) -> str:
        try:
            priority_label = self.priority_engine.calculate_priority(message)
            return priority_label
        except Exception as e:
            print(f"Priority analysis failed: {e}")
            return "Medium"

    # -------------------------
    # TASK CLASSIFIER (RULE-BASED)
    # Scans message text with keyword rules to determine the required action type.
    # Categories: File Attachment / Draft Generation / Auto Reply / Simple Reply / Informational.
    # No AI needed — fast deterministic keyword matching.
    # -------------------------
    def _classify_task(self, message: Dict) -> list:
        try:
            subject = (message.get('subject', '') or '').lower()
            body    = (
                message.get('full_content', '') or
                message.get('content_preview', '') or
                message.get('text', '') or ''
            ).lower()
            text = subject + " " + body

            attachment_signals = [
                "please send", "please attach", "send me", "attach the",
                "can you send", "forward the", "provide the document",
                "your cv", "your resume", "your report", "submit", "upload",
                "fill out", "fill in", "the form", "pdf", "spreadsheet", "send the"
            ]
            if any(p in text for p in attachment_signals):
                return ["File Attachment Required"]

            draft_signals = [
                "proposal", "detailed response", "explain in detail", "elaborate",
                "provide a full", "write a", "draft", "comprehensive", "cover letter",
                "formal response", "business case", "feedback on", "assessment of"
            ]
            if any(p in text for p in draft_signals):
                return ["Draft Generation"]

            auto_reply_signals = [
                "thank you for", "we have received", "this is to confirm",
                "your request has been", "order confirmation", "booking confirmation",
                "receipt", "invoice", "automated message", "noreply", "no-reply",
                "do not reply", "newsletter"
            ]
            if any(p in text for p in auto_reply_signals):
                return ["Auto Reply"]

            simple_reply_signals = [
                "please confirm", "can you confirm", "are you available",
                "please let me know", "quick question", "please respond",
                "please reply", "waiting for your", "reply needed",
                "response needed", "reply asap", "meeting request"
            ]
            if any(p in text for p in simple_reply_signals):
                return ["Simple Reply Required"]

            return ["Informational"]
        except Exception:
            return ["Informational"]

    # -------------------------
    # TONE DETECTOR (INTERNAL)
    # Uses the Tone Engine to detect if the incoming message is Formal or Informal.
    # Returns a signal string: "formal_leaning", "informal_leaning", or "neutral".
    # Helps suggest the correct reply tone to the user when composing a response.
    # -------------------------
    async def _analyze_tone(self, message: Dict) -> str:
        try:
            if self.tone_engine:
                text        = message.get('full_content', '') or message.get('content_preview', '')
                tone_result = self.tone_engine.analyze_incoming_tone(text)
                return tone_result.get('tone_signal', 'neutral')
            return "neutral"
        except Exception as e:
            print(f"Tone analysis failed: {e}")
            return "unknown"

    # -------------------------
    # CONNECT TO SLACK
    # Authenticates using a Slack bot token provided by the user in Settings.
    # Returns True if connection was successful, False otherwise.
    # -------------------------
    def connect(self, token: str) -> bool:
        return self.backend.connect(token)

    # -------------------------
    # CHECK IF SLACK IS CONNECTED
    # Returns True if a valid Slack session is active, False if not connected.
    # -------------------------
    def is_connected(self) -> bool:
        return self.backend.is_connected
