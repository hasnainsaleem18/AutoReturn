"""
Slack Agent - Intelligent wrapper around Slack backend service.
Adds AI capabilities: summarization, priority scoring, sentiment analysis.
"""
import asyncio
from typing import List, Dict, Optional
from src.backend.agents.base_agent import BaseAgent
from src.backend.models.agent_models import AgentRequest, AgentResponse, Intent
from src.backend.services.slack_backend import SlackService
from src.backend.services.ai_service import OllamaService
from src.backend.core.priority_engine import PriorityEngine


class SlackAgent(BaseAgent):
    """Intelligent agent for Slack management with AI capabilities."""
    
    def __init__(self, ai_service: OllamaService):
        super().__init__(name="slack_agent")
        
        # Backend service for API calls
        self.backend = SlackService()
        
        # AI service for intelligence
        self.ai_service = ai_service
        
        # Priority Engine (New Algorithm Implementation)
        self.priority_engine = PriorityEngine()
        
        print(f"✅ {self.name} initialized with AI capabilities and Priority Engine")

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process Slack related requests with AI intelligence."""
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

    async def _handle_fetch(self, request: AgentRequest) -> AgentResponse:
        """Fetch Slack messages and add AI intelligence."""
        limit = request.parameters.get("limit", 50)
        add_ai = request.parameters.get("add_ai_analysis", True)
        
        # Use backend service to fetch messages
        messages = self.backend.fetch_all_messages(limit=limit)
        
        # Add lightweight AI intelligence (Priority & Sentiment)
        # We skip heavy summarization here to return to UI instantly.
        if add_ai and messages:
            print(f"🤖 Slack Agent: Analyzing priority/sentiment for {len(messages)} messages...")
            
            async def process_slack_msg_light(msg):
                try:
                    # AI Priority Analysis
                    priority_label = await self._analyze_priority(msg)
                    msg['ai_priority_score'] = priority_label
                    msg['priority'] = priority_label  # UI reads this field
                    
                    # Sentiment analysis
                    msg['ai_sentiment'] = await self._analyze_sentiment(msg)
                    
                    # Mark for background summarization if content is sufficient
                    if not msg.get('summary'):
                         msg['summary'] = ""
                except Exception as e:
                    print(f"⚠️ Slack processing error: {e}")
                return msg

            # Run parallel processing for lightweight tasks
            # No batching needed for these simple heuristics
            import asyncio
            processed_messages = await asyncio.gather(*[process_slack_msg_light(m) for m in messages], return_exceptions=True)
            
            # Filter out exceptions
            messages = [m for m in processed_messages if isinstance(m, dict)]
            
            print("✅ Slack Agent: Initial processing complete")
        
        return self.success_response(data={"messages": messages, "count": len(messages)})

    async def _handle_send(self, request: AgentRequest) -> AgentResponse:
        """Send Slack message."""
        # Implement send logic using backend
        return self.error_response("Send functionality not yet implemented")

    async def _handle_summarize(self, request: AgentRequest) -> AgentResponse:
        """Generate AI summary for a specific message."""
        message = request.parameters.get("message")
        if not message:
            return self.error_response("No message provided for summarization")
        
        summary = await self._generate_summary(message)
        return self.success_response(data={"summary": summary})

    async def _handle_priority(self, request: AgentRequest) -> AgentResponse:
        """Analyze priority for a message."""
        message = request.parameters.get("message")
        if not message:
            return self.error_response("No message provided for priority analysis")
        
        priority_score = await self._analyze_priority(message)
        return self.success_response(data={"priority_score": priority_score})

    async def _generate_summary(self, message: Dict) -> str:
        """Use AI to generate summary of Slack message."""
        try:
            content = message.get('full_content') or message.get('text', '')
            if not content or len(content.strip()) < 10:
                return "No content to summarize"
            
            # Use AI service asynchronously
            summary = await self.ai_service.generate_summary_async(content)
            return summary or "Summary unavailable"
        except Exception as e:
            print(f"Summary generation failed: {e}")
            return "Summary unavailable"

    async def _analyze_priority(self, message: Dict) -> str:
        """Algorithm: Email/Message Priority Classification"""
        try:
            # Pass full message to the Priority Engine
            priority_label = self.priority_engine.calculate_priority(message)
            return priority_label
        except Exception as e:
            print(f"Priority analysis failed: {e}")
            return "Medium"

    async def _analyze_sentiment(self, message: Dict) -> str:
        """Use AI to analyze sentiment of message."""
        try:
            # Placeholder - can use AI prompt for sentiment analysis
            return "neutral"
        except Exception as e:
            print(f"Sentiment analysis failed: {e}")
            return "unknown"
            
    def connect(self, token: str) -> bool:
        """Connect to Slack using backend service."""
        return self.backend.connect(token)
    
    def is_connected(self) -> bool:
        """Check if connected to Slack."""
        return self.backend.is_connected
