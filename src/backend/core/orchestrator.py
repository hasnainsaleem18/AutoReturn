# -------------------------
# ORCHESTRATOR
# -------------------------
"""
The Central Brain of AutoReturn.
Receives all requests from the UI, decides which agent should handle them
(Gmail or Slack), and coordinates all core systems: AI, Tone, Drafts, Automation.
"""

import asyncio
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from src.backend.agents.base_agent import BaseAgent
from src.backend.agents.gmail_agent import GmailAgent
from src.backend.agents.slack_agent import SlackAgent
from src.backend.models.agent_models import AgentRequest, AgentResponse, Intent
from src.backend.services.ai_service import OllamaService
from src.backend.core.draft_manager import DraftManager
from src.backend.core.tone_engine import ToneEngine
from src.backend.core.automation_coordinator import AutomationCoordinator
from src.backend.core.reply_policy_engine import ReplyPolicyEngine
from src.backend.services.automation_settings_service import AutomationSettingsService


# -------------------------
# PYDANTIC MODEL: INTENT CLASSIFICATION RESULT
# Defines the expected structure of the AI's output when it classifies a user command.
# The AI must return a target agent, an action type, and a confidence score.
# -------------------------
class IntentClassification(BaseModel):
    """Intent classification result from Pydantic AI."""
    target_agent: str = Field(description="Which agent: 'gmail', 'slack', or 'both'")
    action: str = Field(description="Action type: 'fetch', 'send', 'summarize', 'analyze_priority'")
    confidence: float = Field(description="Confidence score 0.0 to 1.0")
    parameters: Dict[str, Any] = Field(default_factory=dict)


# -------------------------
# PYDANTIC MODEL: ORCHESTRATOR DEPENDENCIES
# Provides the AI agent with context about which tools and agents are available.
# -------------------------
class OrchestratorDeps(BaseModel):
    """Dependencies passed to the orchestrator AI agent at runtime."""
    available_agents: List[str]
    user_context: Dict[str, Any] = Field(default_factory=dict)


# -------------------------
# ORCHESTRATOR CLASS
# Central coordinator that manages all agents and core services.
# -------------------------
class Orchestrator:
    """
    The Central Brain of AutoReturn.
    Coordinates Gmail Agent, Slack Agent, Tone Engine, and Automation.
    """

    # -------------------------
    # CONSTRUCTOR: BOOT ALL SERVICES
    # Starts the AI service, registers all agents, sets up Tone Engine,
    # Draft Manager, and Automation Coordinator. Injects Tone Engine into agents.
    # -------------------------
    def __init__(self, ollama_model: str = "qwen2.5:1.5b", ollama_base_url: str = "http://localhost:11434"):
        # Start the AI service that connects to the local Ollama model
        self.ai_service = OllamaService(model_name=ollama_model, base_url=ollama_base_url)

        # Register available agents — Gmail and Slack
        self.agents: Dict[str, BaseAgent] = {
            "gmail": GmailAgent(ai_service=self.ai_service),
            "slack": SlackAgent(ai_service=self.ai_service)
        }

        # Draft Manager generates AI-powered reply drafts for messages
        self.draft_manager = DraftManager(self.ai_service, tone_engine=None)

        # Tone Engine detects and applies Formal/Informal tone to replies
        self.tone_engine  = ToneEngine(ai_service=self.ai_service)
        self.tone_manager = self.tone_engine   # Backward-compatible alias

        # Automation Coordinator manages DND mode and auto-reply policy
        self.automation_settings_service = AutomationSettingsService()
        self.reply_policy_engine = ReplyPolicyEngine()
        self.automation_coordinator = AutomationCoordinator(
            settings_service=self.automation_settings_service,
            policy_engine=self.reply_policy_engine,
        )

        # Inject Tone Engine into Draft Manager and all registered agents
        self.draft_manager.tone_engine = self.tone_engine
        for agent in self.agents.values():
            if hasattr(agent, 'set_tone_engine'):
                agent.set_tone_engine(self.tone_engine)
            elif hasattr(agent, 'set_tone_manager'):
                agent.set_tone_manager(self.tone_engine)

        # Set up the Pydantic AI intent classifier
        self._setup_pydantic_agent(ollama_model)

        print(f"Orchestrator initialized with model {ollama_model}")
        print(f"   Available agents: {list(self.agents.keys())}")
        print(f"Tone Engine initialized")
        print(f"Automation Coordinator initialized")

    # -------------------------
    # SETUP PYDANTIC AI CLASSIFIER
    # Prepares the AI-powered intent classification layer.
    # Currently uses heuristic (keyword) routing while the full AI model is finalized.
    # -------------------------
    def _setup_pydantic_agent(self, model_name: str):
        self.pydantic_agent = None
        print("   Intent classification: Using heuristic routing (Pydantic AI integration pending)")

    # -------------------------
    # MAIN COMMAND PROCESSOR (ENTRY POINT FROM UI)
    # Takes a plain-English command, classifies the intent using AI/heuristics,
    # then routes to the correct agent(s). Returns the combined result to the UI.
    # -------------------------
    async def process_user_command(self, command: str, context: Dict[str, Any] = None) -> AgentResponse:
        try:
            # Step 1: Determine what the user wants and which agent to use
            intent_result = await self._classify_intent(command, context or {})

            # Step 2: Route to the correct agent(s)
            if intent_result.target_agent == "both":
                # Run both Gmail and Slack agents simultaneously (parallel execution)
                results = await asyncio.gather(
                    self._execute_on_agent("gmail", intent_result),
                    self._execute_on_agent("slack", intent_result),
                    return_exceptions=True
                )
                # Merge results from both agents into one combined response
                all_data = []
                errors   = []
                for result in results:
                    if isinstance(result, Exception):
                        errors.append(str(result))
                    elif isinstance(result, AgentResponse):
                        if result.success:
                            if result.data and 'messages' in result.data:
                                all_data.extend(result.data['messages'])
                        else:
                            errors.append(f"{result.agent_name}: {result.error}")

                return AgentResponse(
                    success=len(all_data) > 0 or not errors,
                    data={"messages": all_data, "count": len(all_data), "errors": errors},
                    error="; ".join(errors) if errors and not all_data else None,
                    agent_name="orchestrator"
                )
            else:
                # Route to a single agent only
                return await self._execute_on_agent(intent_result.target_agent, intent_result)

        except Exception as e:
            return AgentResponse(
                success=False,
                error=f"Orchestrator error: {str(e)}",
                agent_name="orchestrator"
            )

    # -------------------------
    # INTENT CLASSIFIER
    # Reads keywords in a command to decide: which platform (Gmail/Slack/both)
    # and what action (fetch/send/summarize/priority). Returns IntentClassification.
    # -------------------------
    async def _classify_intent(self, command: str, context: Dict[str, Any]) -> IntentClassification:
        command_lower = command.lower()

        # Determine target platform from keywords in the command
        if "both" in command_lower or "all" in command_lower:
            target = "both"
        elif "gmail" in command_lower or "email" in command_lower:
            target = "gmail"
        elif "slack" in command_lower or "message" in command_lower:
            target = "slack"
        else:
            target = "both"   # Default: query both if unclear

        # Determine what action to perform from keywords
        if "fetch" in command_lower or "get" in command_lower or "sync" in command_lower:
            action = "fetch"
        elif "send" in command_lower:
            action = "send"
        elif "summar" in command_lower:
            action = "summarize"
        elif "priority" in command_lower or "urgent" in command_lower:
            action = "analyze_priority"
        else:
            action = "fetch"   # Default action

        return IntentClassification(
            target_agent=target,
            action=action,
            confidence=0.8,
            parameters=context
        )

    # -------------------------
    # AGENT EXECUTOR
    # Converts a classified intent into a proper AgentRequest and sends it
    # to the target agent (gmail or slack). Returns the agent's response.
    # -------------------------
    async def _execute_on_agent(self, agent_name: str, intent: IntentClassification) -> AgentResponse:
        if agent_name not in self.agents:
            return AgentResponse(
                success=False,
                error=f"Agent '{agent_name}' not found",
                agent_name="orchestrator"
            )

        # Map the action string to the Intent enum used by all agents
        intent_mapping = {
            "fetch":            Intent.FETCH_MESSAGES,
            "send":             Intent.SEND_MESSAGE,
            "summarize":        Intent.SUMMARIZE,
            "analyze_priority": Intent.ANALYZE_PRIORITY,
        }
        intent_enum = intent_mapping.get(intent.action, Intent.FETCH_MESSAGES)

        # Build and dispatch the AgentRequest to the target agent
        request = AgentRequest(
            intent=intent_enum,
            parameters=intent.parameters,
            context={"confidence": intent.confidence}
        )
        return await self.agents[agent_name].process_request(request)

    # -------------------------
    # DIRECT ROUTING (BYPASS CLASSIFIER)
    # Sends a request directly to a named agent without going through intent classification.
    # Used by the UI buttons that already know which platform to target.
    # -------------------------
    async def route_request(self, target: str, request: AgentRequest) -> AgentResponse:
        if target not in self.agents:
            return AgentResponse(
                success=False,
                error=f"Agent '{target}' not found",
                agent_name="orchestrator"
            )
        return await self.agents[target].process_request(request)

    # -------------------------
    # GENERATE AI DRAFT FOR A MESSAGE
    # Passes the full message context to the Draft Manager so the AI can write
    # a specific, relevant reply. Returns the draft text plus tone and confidence.
    # -------------------------
    async def generate_draft_for_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        draft_text = await self.draft_manager._generate_basic_draft(
            message_context=message.get('full_content', message.get('preview', '')),
            message_data=message,
        )
        return {
            'draft':      draft_text,
            'tone':       None,
            'confidence': 0.8,
        }

    # -------------------------
    # GET AGENT BY NAME
    # Returns the agent object (GmailAgent or SlackAgent) for the given name.
    # -------------------------
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self.agents.get(name)

    # -------------------------
    # GET TONE ENGINE
    # Returns the Tone Engine instance used across the whole application.
    # -------------------------
    def get_tone_engine(self) -> ToneEngine:
        return self.tone_engine

    # -------------------------
    # GET TONE MANAGER (BACKWARD COMPATIBLE)
    # Same as get_tone_engine — kept for older code that uses the old name.
    # -------------------------
    def get_tone_manager(self) -> ToneEngine:
        return self.tone_engine

    # -------------------------
    # GET AUTOMATION COORDINATOR
    # Returns the coordinator that manages DND and auto-reply settings.
    # -------------------------
    def get_automation_coordinator(self) -> AutomationCoordinator:
        return self.automation_coordinator

    # -------------------------
    # CHECK OLLAMA STATUS
    # Pings the local Ollama AI server to verify it is running.
    # Returns True if reachable, False if offline.
    # -------------------------
    def check_ollama_status(self) -> bool:
        return self.ai_service.check_connection()
