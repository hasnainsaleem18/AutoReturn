"""
# -------------------------
# GMAIL AGENT
# -------------------------
Bridge between AutoReturn and Gmail API.
Fetches emails, enriches each with Priority Score, Task Classification,
and Calendar Event extraction using the custom Priority Engine and AI Service.
"""

import os
import asyncio
from typing import List, Dict, Optional
from src.backend.agents.base_agent import BaseAgent
from src.backend.models.agent_models import AgentRequest, AgentResponse, Intent
from src.backend.services.gmail_backend import GmailIntegrationService
from src.backend.services.ai_service import OllamaService
from src.backend.core.priority_engine import PriorityEngine
from src.backend.core.event_extractor import EventExtractor


class GmailAgent(BaseAgent):
    """Intelligent Gmail agent with Priority Engine, Task Classifier, and AI summarization."""

    # -------------------------
    # CONSTRUCTOR: INITIALIZE ALL COMPONENTS
    # Sets up the Gmail backend connection, Priority Engine, and Event Extractor.
    # Tone Engine is injected later by the Orchestrator after startup.
    # -------------------------
    def __init__(self, ai_service: OllamaService, data_dir: str = None):
        super().__init__(name="gmail_agent")

        if not data_dir:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            data_dir = os.path.join(project_root, "data", "gmail_data")

        self.backend        = GmailIntegrationService(data_dir=data_dir)   # Gmail API wrapper
        self.ai_service     = ai_service                                    # Ollama AI connection
        self.priority_engine = PriorityEngine()                            # Custom scoring algorithm
        self.tone_engine    = None                                          # Set by Orchestrator
        self.event_extractor = EventExtractor(
            ai_service=self.ai_service,
            enable_llm_fallback=True,
            confidence_threshold=0.85
        )
        print(f"{self.name} initialized with AI capabilities and Priority Engine")

    # -------------------------
    # SET TONE ENGINE
    # Receives the shared Tone Engine from the Orchestrator and stores it.
    # Called once during startup so all agents share the same tone preferences.
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
    # Entry point called by the Orchestrator to handle any Gmail request.
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
            return self.error_response(f"Gmail agent error: {str(e)}")

    # -------------------------
    # FETCH AND ENRICH EMAILS
    # Pulls raw emails from Gmail API, then runs Priority Engine, Task
    # Classifier, and Event Extractor on every message in parallel.
    # Marks each message for background summarization without blocking.
    # -------------------------
    async def _handle_fetch(self, request: AgentRequest) -> AgentResponse:
        import asyncio
        if not self.backend or not self.backend.is_connected:
            print("Gmail Agent: Backend not connected")
            return self.error_response("Gmail not connected. Please authorize Gmail in Settings.")

        max_results = request.parameters.get("max_results", 25)
        query       = request.parameters.get("query", "in:inbox")
        add_ai      = request.parameters.get("add_ai_analysis", True)

        print(f"Gmail Agent: Syncing Gmail (max={max_results}, ai={add_ai})...")

        try:
            messages = self.backend.fetch_messages(max_results=max_results, query=query)
            print(f"Gmail Agent: Fetched {len(messages)} messages from backend")

            if not messages:
                return self.success_response(data={"messages": [], "count": 0})

            if add_ai:
                print(f"Gmail Agent: analyzing priority and tasks for {len(messages)} messages...")

                async def process_msg_light(msg):
                    try:
                        # Run Priority Algorithm (High / Medium / Low)
                        priority_label        = await self._analyze_priority(msg)
                        msg['ai_priority_score'] = priority_label
                        msg['priority']          = priority_label   # UI badge reads this field

                        # Run Task Classifier (File Attachment / Draft / Auto Reply / etc.)
                        msg['ai_tasks']          = await self._extract_tasks(msg)

                        # Run Calendar Event Extractor (meeting dates/times)
                        try:
                            events               = await self.event_extractor.extract_from_message(msg)
                            msg['ai_events']     = [e.model_dump(mode="json") for e in events] if events else []
                            msg['ai_events_count'] = len(msg['ai_events'])
                            if events:
                                print(f"Events extracted for {msg.get('id', '')[:8]}: {len(events)}")
                        except Exception as e:
                            print(f"Event extraction error for {msg.get('id')}: {e}")

                        # Leave summary blank so background queue fills it later
                        if not msg.get('summary'):
                            msg['summary'] = ""
                    except Exception as e:
                        print(f"Error processing message {msg.get('id')}: {e}")
                    return msg

                # Process all messages simultaneously for speed
                processed_messages = await asyncio.gather(*[process_msg_light(m) for m in messages], return_exceptions=True)
                messages           = [m for m in processed_messages if isinstance(m, dict)]
                print("Gmail Agent: Initial processing complete")

            return self.success_response(data={"messages": messages, "count": len(messages)})

        except Exception as e:
            print(f"Gmail Agent: Fetch failed: {e}")
            return self.error_response(str(e))

    # -------------------------
    # SEND EMAIL HANDLER
    # Handles outgoing email send requests routed from the Orchestrator.
    # Actual sending is done through the Send Dialog (not this agent directly).
    # -------------------------
    async def _handle_send(self, request: AgentRequest) -> AgentResponse:
        return self.error_response("Send functionality not yet implemented")

    # -------------------------
    # SUMMARIZE A SINGLE EMAIL
    # Called when the user wants an on-demand AI summary for one specific email.
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
    # Directly runs the Priority Engine on a single message and returns the label.
    # Called when the Orchestrator routes an analyze_priority intent here.
    # -------------------------
    async def _handle_priority(self, request: AgentRequest) -> AgentResponse:
        message = request.parameters.get("message")
        if not message:
            return self.error_response("No message provided for priority analysis")
        priority_score = await self._analyze_priority(message)
        return self.success_response(data={"priority_score": priority_score})

    # -------------------------
    # GENERATE AI SUMMARY (INTERNAL)
    # Passes email content to Ollama and returns a 1-2 sentence summary.
    # Falls back through content fields: full_content → preview → snippet → subject.
    # -------------------------
    async def _generate_summary(self, message: Dict) -> str:
        try:
            content = (
                message.get('full_content') or
                message.get('preview') or
                message.get('snippet') or
                message.get('subject', '')
            )
            if not content or len(content.strip()) < 10:
                print(f"Skipping summary for {message.get('id')}: Content too short")
                return "No content to summarize"
            summary = await self.ai_service.generate_summary_async(
                content,
                sender=message.get('sender', ''),
                subject=message.get('subject', '')
            )
            return summary or "Summary unavailable"
        except Exception as e:
            print(f"Summary generation failed for {message.get('id')}: {e}")
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
    # Scans subject and body with keyword rules to determine what action is needed.
    # Categories: File Attachment / Draft Generation / Auto Reply / Simple Reply / Informational.
    # No AI used here — pure deterministic keyword matching for speed.
    # -------------------------
    async def _extract_tasks(self, message: Dict) -> List[str]:
        try:
            subject = (message.get('subject', '') or '').lower()
            body    = (message.get('full_content', '') or message.get('preview', '') or '').lower()
            text    = subject + " " + body

            attachment_signals = [
                "please send", "please attach", "send me", "attach the",
                "can you send", "forward the", "provide the document",
                "your cv", "your resume", "your report", "submit", "upload",
                "fill out", "fill in", "the form", "pdf", "spreadsheet"
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
        except Exception as e:
            print(f"Task extraction failed: {e}")
            return ["Informational"]

    # -------------------------
    # CONNECT TO GMAIL
    # Starts the OAuth authentication flow so the user can authorize the app.
    # allow_flow=True means it will open the browser for permission if no token exists.
    # -------------------------
    def connect(self, allow_flow: bool = True) -> tuple[bool, str]:
        return self.backend.connect(allow_flow=allow_flow)

    # -------------------------
    # CHECK IF GMAIL IS AUTHENTICATED
    # Returns True if a valid Gmail token already exists (user already connected).
    # Returns False if the user needs to go through the OAuth flow again.
    # -------------------------
    def has_token(self) -> bool:
        return self.backend.has_token()
