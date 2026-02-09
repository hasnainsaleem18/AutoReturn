from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from enum import Enum

class Intent(str, Enum):
    FETCH_MESSAGES = "fetch_messages"
    SEND_MESSAGE = "send_message"
    SUMMARIZE = "summarize"
    ANALYZE_PRIORITY = "analyze_priority"
    EXTRACT_TASKS = "extract_tasks"
    SEARCH = "search"
    UNKNOWN = "unknown"

class AgentRequest(BaseModel):
    intent: Intent
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    agent_name: str
