"""
LangGraph Nodes for Open Interface
"""
import json
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

try:
    from .state import OpenInterfaceState
    from .tools import create_pyautogui_tools
except ImportError:
    # Handle direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from langgraph_interface.state import OpenInterfaceState
    from langgraph_interface.tools import create_pyautogui_tools
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
from models.factory import ModelFactory
from utils.settings import Settings


class OpenInterfaceNodes:
    """Collection of nodes for the Open Interface LangGraph"""
    
    def __init__(self):
        self.settings = Settings()
        self.settings_dict = self.settings.get_dict()
        self.tools = create_pyautogui_tools()
        self._setup_model()
    
    def _setup_model(self):
        """Setup the LLM model"""
        model_name = self.settings_dict.get('model', 'gemini-1.5-flash')
        base_url = self.settings_dict.get('base_url', 'https://api.openai.com/v1/')
        api_key = self.settings_dict.get('api_key')
        
        # Read context
        from pathlib import Path
        context_file = Path(__file__).parent.parent / 'app' / 'resources' / 'context.txt'
        with open(context_file, 'r') as f:
            context = f.read()
        
        self.model = ModelFactory.create_model(model_name, base_url, api_key, context)
    
    def planning_node(self, state: OpenInterfaceState) -> Dict[str, Any]:
        """Node that plans the next steps based on user request and current state"""
        
        # Take screenshot if this is the first step
        if state["step_count"] == 0:
            screenshot_result = self.tools[4].invoke({})  # take_screenshot tool
            state["screenshot_data"] = screenshot_result
        
        # Create system message with context
        system_message = SystemMessage(content=self._build_system_prompt(state))
        
        # Create user message with request and screenshot info
        user_content = f"User Request: {state['user_request']}\n"
        if state["screenshot_data"]:
            user_content += f"Screenshot available: {state['screenshot_data']}\n"
        if state["step_count"] > 0:
            user_content += f"Step {state['step_count']} - Previous results: {state['execution_results'][-1] if state['execution_results'] else 'None'}"
        
        user_message = HumanMessage(content=user_content)
        
        # Get instructions from model
        try:
            instructions = self.model.get_instructions_for_objective(
                state["user_request"], 
                state["step_count"]
            )
            

            
            return {
                "current_instructions": instructions,
                "messages": [system_message, user_message]
            }
        except Exception as e:
            return {
                "error_message": f"Planning failed: {str(e)}",
                "is_complete": True
            }
    
    def execution_node(self, state: OpenInterfaceState) -> Dict[str, Any]:
        """Node that executes the planned steps"""
        
        if not state["current_instructions"] or not state["current_instructions"].get("steps"):
            return {
                "error_message": "No instructions to execute",
                "is_complete": True
            }
        
        execution_results = []
        
        for step in state["current_instructions"]["steps"]:
            if state.get("interrupt_requested", False):
                return {
                    "error_message": "Execution interrupted by user",
                    "is_complete": True
                }
            
            function_name = step.get("function", "")
            parameters = step.get("parameters", {})
            justification = step.get("human_readable_justification", "")
            

            
            # Execute the step using appropriate tool
            result = self._execute_step(function_name, parameters)
            
            execution_results.append({
                "function": function_name,
                "parameters": parameters,
                "justification": justification,
                "result": result,
                "success": "failed" not in result.lower()
            })
        
        return {
            "execution_results": execution_results,
            "step_count": state["step_count"] + 1
        }
    
    def validation_node(self, state: OpenInterfaceState) -> Dict[str, Any]:
        """Node that validates if the task is complete"""
        
        instructions = state["current_instructions"]
        
        if instructions.get("done"):
            return {
                "is_complete": True,
                "messages": [AIMessage(content=instructions["done"])]
            }
        
        # Check if we've exceeded max steps
        if state["step_count"] >= state.get("max_steps", 10):
            return {
                "is_complete": True,
                "error_message": "Maximum steps exceeded"
            }
        
        # Continue to next iteration
        return {"is_complete": False}
    
    def screenshot_node(self, state: OpenInterfaceState) -> Dict[str, Any]:
        """Node that takes a screenshot for the next iteration"""
        
        try:
            screenshot_result = self.tools[4].invoke({})  # take_screenshot tool
            return {"screenshot_data": screenshot_result}
        except Exception as e:
            return {"error_message": f"Screenshot failed: {str(e)}"}
    
    def response_node(self, state: OpenInterfaceState) -> Dict[str, Any]:
        """Node that provides final response to user"""
        
        if state.get("error_message"):
            response = f"Task completed with error: {state['error_message']}"
        else:
            response = state["current_instructions"].get("done", "Task completed successfully")
        
        return {
            "messages": [AIMessage(content=response)],
            "is_complete": True
        }
    
    def _build_system_prompt(self, state: OpenInterfaceState) -> str:
        """Build system prompt with context"""
        prompt = "You are Open Interface, an AI assistant that controls computers using PyAutoGUI tools.\n"
        prompt += f"Model: {state.get('model_name', 'gemini-1.5-flash')}\n"
        
        if state.get("custom_instructions"):
            prompt += f"Custom instructions: {state['custom_instructions']}\n"
        
        prompt += "\nAvailable tools:\n"
        for tool in self.tools:
            prompt += f"- {tool.name}: {tool.description}\n"
        
        return prompt
    
    def _execute_step(self, function_name: str, parameters: Dict[str, Any]) -> str:
        """Execute a single step using the appropriate tool"""
        
        # Map function names to tools
        tool_mapping = {
            "click": 0,
            "type_text": 1, 
            "write": 1,  # Alias for type_text
            "press_key": 2,
            "press": 2,  # Alias for press_key
            "hotkey": 3,  # Separate hotkey tool
            "sleep": 4,
            "take_screenshot": 5
        }
        
        # Clean function name
        if function_name.startswith("pyautogui."):
            function_name = function_name.replace("pyautogui.", "")
        
        tool_index = tool_mapping.get(function_name)
        if tool_index is None:
            return f"Unknown function: {function_name}"
        
        try:
            tool = self.tools[tool_index]
            
            # Handle parameter mapping for different function names
            if function_name in ["write", "type_text"]:
                # Map 'text' parameter to 'text' for type_text tool
                if "text" in parameters:
                    params = {"text": parameters["text"], "interval": parameters.get("interval", 0.05)}
                else:
                    params = parameters
            elif function_name in ["press", "press_key"]:
                # Map 'keys' parameter to 'key' for press_key tool
                if "keys" in parameters:
                    params = {"key": parameters["keys"], "presses": parameters.get("presses", 1)}
                else:
                    params = parameters
            elif function_name == "hotkey":
                # Special handling for hotkey - convert keys list to individual arguments
                if "keys" in parameters and isinstance(parameters["keys"], list):
                    keys = parameters["keys"]
                    result = tool.func(*keys)  # Call the underlying function directly
                    return result
                else:
                    params = parameters
            elif function_name == "sleep":
                # Handle sleep function - map 'seconds' parameter
                if "seconds" in parameters:
                    params = {"seconds": parameters["seconds"]}
                elif "secs" in parameters:
                    params = {"seconds": parameters["secs"]}
                else:
                    # If no parameters, use default
                    params = {"seconds": 1}
            else:
                params = parameters
            
            result = tool.invoke(params)
            return result
        except Exception as e:
            return f"Execution failed: {str(e)}"
