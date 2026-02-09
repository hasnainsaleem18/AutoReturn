from src.backend.models.agent_models import AgentRequest, AgentResponse
from src.backend.services.ai_service import OllamaService

class TaskExtractor:
    """AI component for extracting tasks from message content."""
    
    def __init__(self, ai_service: OllamaService):
        self.ai_service = ai_service

    async def extract(self, text: str) -> list:
        # Placeholder for AI task extraction logic
        return []
