from abc import ABC, abstractmethod
from src.backend.models.agent_models import AgentRequest, AgentResponse

class BaseAgent(ABC):
    """Base class for all intelligent agents in the system."""
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process an incoming request from the Orchestrator."""
        pass

    def success_response(self, data: any = None) -> AgentResponse:
        return AgentResponse(success=True, data=data, agent_name=self.name)

    def error_response(self, error: str) -> AgentResponse:
        return AgentResponse(success=False, error=error, agent_name=self.name)
