"""
LangGraph Implementation for Open Interface
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

try:
    from .state import OpenInterfaceState
    from .nodes import OpenInterfaceNodes
    from .tools import create_pyautogui_tools
except ImportError:
    # Handle direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from langgraph_interface.state import OpenInterfaceState
    from langgraph_interface.nodes import OpenInterfaceNodes
    from langgraph_interface.tools import create_pyautogui_tools


class OpenInterfaceGraph:
    """LangGraph-based Open Interface implementation"""
    
    def __init__(self):
        self.nodes = OpenInterfaceNodes()
        self.tools = create_pyautogui_tools()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Create the state graph
        builder = StateGraph(OpenInterfaceState)
        
        # Add nodes
        builder.add_node("planning", self.nodes.planning_node)
        builder.add_node("execution", self.nodes.execution_node)
        builder.add_node("validation", self.nodes.validation_node)
        builder.add_node("screenshot", self.nodes.screenshot_node)
        builder.add_node("response", self.nodes.response_node)
        
        # Add tool node for direct tool execution
        tool_node = ToolNode(tools=self.tools)
        builder.add_node("tools", tool_node)
        
        # Define edges
        builder.add_edge(START, "planning")
        
        # Planning -> Execution
        builder.add_edge("planning", "execution")
        
        # Execution -> Validation
        builder.add_edge("execution", "validation")
        
        # Validation -> Screenshot (if not complete) or Response (if complete)
        builder.add_conditional_edges(
            "validation",
            self._should_continue,
            {
                "continue": "screenshot",
                "complete": "response"
            }
        )
        
        # Screenshot -> Planning (for next iteration)
        builder.add_edge("screenshot", "planning")
        
        # Response -> END
        builder.add_edge("response", END)
        
        # Compile the graph
        return builder.compile()
    
    def _should_continue(self, state: OpenInterfaceState) -> Literal["continue", "complete"]:
        """Determine if the graph should continue or complete"""
        
        if state.get("is_complete", False):
            return "complete"
        
        if state.get("error_message"):
            return "complete"
        
        if state.get("interrupt_requested", False):
            return "complete"
        
        return "continue"
    
    def execute_request(self, user_request: str, max_steps: int = 10) -> dict:
        """Execute a user request using the LangGraph"""
        
        # Initialize state
        initial_state = {
            "messages": [],
            "user_request": user_request,
            "step_count": 0,
            "max_steps": max_steps,
            "current_instructions": None,
            "execution_results": [],
            "screenshot_data": None,
            "is_complete": False,
            "error_message": None,
            "interrupt_requested": False,
            "model_name": self.nodes.settings_dict.get('model', 'gemini-1.5-flash'),
            "api_key": self.nodes.settings_dict.get('api_key', ''),
            "custom_instructions": self.nodes.settings_dict.get('custom_llm_instructions', '')
        }
        
        try:
            # Execute the graph
            result = self.graph.invoke(initial_state)
            return result
        except Exception as e:
            return {
                "error_message": f"Graph execution failed: {str(e)}",
                "is_complete": True
            }
    
    def stream_execution(self, user_request: str, max_steps: int = 10):
        """Stream the execution of a user request"""
        
        initial_state = {
            "messages": [],
            "user_request": user_request,
            "step_count": 0,
            "max_steps": max_steps,
            "current_instructions": None,
            "execution_results": [],
            "screenshot_data": None,
            "is_complete": False,
            "error_message": None,
            "interrupt_requested": False,
            "model_name": self.nodes.settings_dict.get('model', 'gemini-1.5-flash'),
            "api_key": self.nodes.settings_dict.get('api_key', ''),
            "custom_instructions": self.nodes.settings_dict.get('custom_llm_instructions', '')
        }
        
        try:
            # Stream the graph execution
            for chunk in self.graph.stream(initial_state):
                yield chunk
        except Exception as e:
            yield {
                "error_message": f"Graph execution failed: {str(e)}",
                "is_complete": True
            }
