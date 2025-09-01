"""
LangGraph State Definition for Open Interface
"""
from typing import Annotated, List, Optional, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class OpenInterfaceState(TypedDict):
    """State for the Open Interface LangGraph"""
    
    # Core state
    messages: Annotated[List[BaseMessage], add_messages]
    user_request: str
    step_count: int
    max_steps: int
    
    # Execution state
    current_instructions: Optional[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]
    screenshot_data: Optional[str]
    
    # Control flow
    is_complete: bool
    error_message: Optional[str]
    interrupt_requested: bool
    
    # Settings
    model_name: str
    api_key: str
    custom_instructions: Optional[str]
