"""
Orchestrator - The Central Brain of AutoCom.
Coordinates all agents using Pydantic AI for intent classification.
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
# PYDANTIC MODELS FOR AI
# -------------------------
class IntentClassification(BaseModel):
    """Intent classification result from Pydantic AI."""
    target_agent: str = Field(description="Which agent should handle this: 'gmail' or 'slack' or 'both'")
    action: str = Field(description="What action: 'fetch', 'send', 'summarize', 'analyze_priority'")
    confidence: float = Field(description="Confidence score 0.0 to 1.0")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters")


# -------------------------
# ORCHESTRATOR DEPENDENCIES
# -------------------------
class OrchestratorDeps(BaseModel):
    """Dependencies for the orchestrator AI agent."""
    available_agents: List[str]
    user_context: Dict[str, Any] = Field(default_factory=dict)


# -------------------------
# ORCHESTRATOR
# -------------------------
class Orchestrator:
    """
    The Central Brain of AutoCom that coordinates all agents.
    Uses Pydantic AI for intelligent intent classification.
    """
    
    def __init__(self, ollama_model: str = "kimi-k2.5:cloud", ollama_base_url: str = "http://localhost:11434"):
        # Services
        self.ai_service = OllamaService(model_name=ollama_model, base_url=ollama_base_url)
        
        # Agents (pass AI service to them)
        self.agents: Dict[str, BaseAgent] = {
            "gmail": GmailAgent(ai_service=self.ai_service),
            "slack": SlackAgent(ai_service=self.ai_service)
        }
        
        # Intelligent Components
        self.draft_manager = DraftManager(self.ai_service, tone_engine=None)  # Will be updated after tone_engine init
        
        # NEW: Tone Management System
        self.tone_engine = ToneEngine(ai_service=self.ai_service)
        self.tone_manager = self.tone_engine  # Backward compatibility alias

        # NEW: Automation policy components (DND / auto-reply settings + decisioning)
        self.automation_settings_service = AutomationSettingsService()
        self.reply_policy_engine = ReplyPolicyEngine()
        self.automation_coordinator = AutomationCoordinator(
            settings_service=self.automation_settings_service,
            policy_engine=self.reply_policy_engine,
        )
        
        # Update draft manager and agents with tone engine
        self.draft_manager.tone_engine = self.tone_engine
        for agent in self.agents.values():
            if hasattr(agent, 'set_tone_engine'):
                agent.set_tone_engine(self.tone_engine)
            elif hasattr(agent, 'set_tone_manager'):
                agent.set_tone_manager(self.tone_engine)
        
        # Pydantic AI Agent for intent classification
        self._setup_pydantic_agent(ollama_model)
        
        print(f"🧠 Orchestrator initialized with model {ollama_model}")
        print(f"   Available agents: {list(self.agents.keys())}")
        print(f"🎨 Tone Engine initialized")
        print(f"🤖 Automation Coordinator initialized")

    def _setup_pydantic_agent(self, model_name: str):
        """Set up Pydantic AI agent for intent classification."""
        # TODO: This would use Pydantic AI with Ollama
        # For now, we'll use simple heuristics until Pydantic AI Ollama integration is confirmed
        self.pydantic_agent = None
        print("   Intent classification: Using heuristic routing (Pydantic AI integration pending)")

    async def process_user_command(self, command: str, context: Dict[str, Any] = None) -> AgentResponse:
        """
        Process a natural language command from the user.
        This is the main entry point for the UI.
        
        Args:
            command: Natural language command from user
            context: Additional context for the command
            
        Returns:
            AgentResponse with results from the appropriate agent
        """
        try:
            # Classify intent using AI
            intent_result = await self._classify_intent(command, context or {})
            
            # Route to appropriate agent(s)
            if intent_result.target_agent == "both":
                # Execute on both agents concurrently
                results = await asyncio.gather(
                    self._execute_on_agent("gmail", intent_result),
                    self._execute_on_agent("slack", intent_result),
                    return_exceptions=True
                )
                # Combine results
                all_data = []
                errors = []
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
                # Execute on single agent
                return await self._execute_on_agent(intent_result.target_agent, intent_result)
                
        except Exception as e:
            return AgentResponse(
                success=False,
                error=f"Orchestrator error: {str(e)}",
                agent_name="orchestrator"
            )

    async def _classify_intent(self, command: str, context: Dict[str, Any]) -> IntentClassification:
        """
        Use AI to classify user intent.
        This is where Pydantic AI would normally be used.
        For now, using heuristics as a bridge implementation.
        """
        command_lower = command.lower()
        
        # Heuristic routing (to be replaced with Pydantic AI)
        if "both" in command_lower or "all" in command_lower:
            target = "both"
        elif "gmail" in command_lower or "email" in command_lower:
            target = "gmail"
        elif "slack" in command_lower or "message" in command_lower:
            target = "slack"
        else:
            # Default to both if unclear
            target = "both"
        
        # Determine action
        if "fetch" in command_lower or "get" in command_lower or "sync" in command_lower:
            action = "fetch"
        elif "send" in command_lower:
            action = "send"
        elif "summar" in command_lower:
            action = "summarize"
        elif "priority" in command_lower or "urgent" in command_lower:
            action = "analyze_priority"
        else:
            action = "fetch"  # default
        
        return IntentClassification(
            target_agent=target,
            action=action,
            confidence=0.8,  # Placeholder
            parameters=context
        )

    async def _execute_on_agent(self, agent_name: str, intent: IntentClassification) -> AgentResponse:
        """Execute a classified intent on a specific agent."""
        if agent_name not in self.agents:
            return AgentResponse(
                success=False,
                error=f"Agent '{agent_name}' not found",
                agent_name="orchestrator"
            )
        
        # Map action to Intent enum
        intent_mapping = {
            "fetch": Intent.FETCH_MESSAGES,
            "send": Intent.SEND_MESSAGE,
            "summarize": Intent.SUMMARIZE,
            "analyze_priority": Intent.ANALYZE_PRIORITY,
        }
        
        intent_enum = intent_mapping.get(intent.action, Intent.FETCH_MESSAGES)
        
        # Create agent request
        request = AgentRequest(
            intent=intent_enum,
            parameters=intent.parameters,
            context={"confidence": intent.confidence}
        )
        
        # Execute on agent
        return await self.agents[agent_name].process_request(request)

    async def route_request(self, target: str, request: AgentRequest) -> AgentResponse:
        """
        Direct routing to a specific agent (bypass intent classification).
        Useful when the UI already knows which agent to use.
        """
        if target not in self.agents:
            return AgentResponse(
                success=False, 
                error=f"Agent '{target}' not found", 
                agent_name="orchestrator"
            )
        
        return await self.agents[target].process_request(request)

    async def generate_draft_for_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a suggested draft for a message using the existing draft manager.

        Returns:
            dict: {'draft': str, 'tone': Any, 'confidence': float, ...}
        """
        # Pass the full message dict for context-aware generation
        draft_text = await self.draft_manager._generate_basic_draft(
            message_context=message.get('full_content', message.get('preview', '')),
            message_data=message,
        )
        return {
            'draft': draft_text,
            'tone': None,
            'confidence': 0.8,
        }

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get a specific agent by name."""
        return self.agents.get(name)
    
    def get_tone_engine(self) -> ToneEngine:
        """Get the tone engine instance."""
        return self.tone_engine

    def get_tone_manager(self) -> ToneEngine:
        """Backward-compatible getter for tone engine."""
        return self.tone_engine

    def get_automation_coordinator(self) -> AutomationCoordinator:
        """Get the automation coordinator instance."""
        return self.automation_coordinator
    
    def check_ollama_status(self) -> bool:
        """Check if Ollama is accessible."""
        return self.ai_service.check_connection()
