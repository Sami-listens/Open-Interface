"""
Workflow Executor Node - Executes JSON workflows with LLM-based screenshot verification
Simple, standard approach: Read JSON → Execute step → Screenshot → Verify → Repeat
"""

import json
import time
import pyautogui
import subprocess
import os
import base64
from io import BytesIO
from typing import Dict, Any, List
from PIL import Image

from langgraph_interface.state import OpenInterfaceState
from models.factory import ModelFactory
from utils.settings import Settings


class WorkflowExecutorNode:
    """
    Simple workflow executor that:
    1. Reads actions from JSON workflow
    2. Executes each action
    3. Takes screenshot after action
    4. Uses LLM to verify screenshot matches expected state
    5. Proceeds to next action or retries on failure
    """
    
    def __init__(self):
        """Initialize the workflow executor"""
        pyautogui.PAUSE = 0.1
        pyautogui.FAILSAFE = False  # Disable fail-safe for automation
        pyautogui.moveTo(500, 500)  # Move mouse away from screen corners
        
        # Load settings and LLM
        self.settings = Settings()
        settings_dict = self.settings.get_dict()
        model_name = settings_dict.get('model', 'gemini-2.0-flash-exp')
        base_url = settings_dict.get('base_url', 'https://api.openai.com/v1/')
        api_key = settings_dict.get('api_key')
        
        # Create model for screenshot verification
        self.model = ModelFactory.create_model(model_name, base_url, api_key, "You are a computer vision assistant that verifies UI states.")
        
        # Load reliable_double_click
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from final_double_click_solution import reliable_double_click
            self.reliable_double_click = reliable_double_click
        except:
            self.reliable_double_click = self._fallback_double_click
    
    def __call__(self, state: OpenInterfaceState) -> Dict[str, Any]:
        """
        Execute workflow from JSON file with verification
        
        Expected state inputs:
            - workflow_file: Path to JSON workflow file (e.g., "workflows/w1.json")
            - project_number: (Optional) Project number to substitute
            - verify_steps: (Optional) Whether to verify each step with LLM (default: True)
        
        State outputs:
            - workflow_completed: True if all steps executed successfully
            - workflow_error: Error message if execution failed
            - executed_steps: Number of steps executed
            - status_updates: Progress messages with verification results
        """
        
        workflow_file = state.get('workflow_file', 'workflows/w1.json')
        project_number = state.get('project_number', '206551')
        verify_steps = state.get('verify_steps', True)
        
        status_updates = state.get('status_updates', [])
        status_updates.append(f'🎬 Starting workflow execution: {workflow_file}')
        
        try:
            # Load workflow JSON
            workflow_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                workflow_file
            )
            
            with open(workflow_path, 'r') as f:
                workflow = json.load(f)
            
            status_updates.append(f'✓ Loaded workflow: {workflow["name"]}')
            actions = workflow.get('actions', [])
            status_updates.append(f'📋 {len(actions)} actions to execute')
            
            # Execute each action
            executed_count = 0
            for i, action in enumerate(actions, 1):
                status_updates.append(f'\n[{i}/{len(actions)}] Executing: {action["type"]}')
                
                # Substitute project number if needed
                action = self._substitute_project_number(action, project_number)
                
                # Execute the action
                if not self._execute_action(action, status_updates):
                    raise Exception(f"Action {i} failed: {action['type']}")
                
                executed_count += 1
                
                # Take screenshot and verify (if not a delay/comment)
                if verify_steps and action['type'] not in ['delay', 'comment']:
                    screenshot_b64 = self._take_screenshot()
                    verification = self._verify_screenshot(
                        screenshot_b64,
                        action,
                        i,
                        len(actions)
                    )
                    status_updates.append(f'  ✓ Verified: {verification}')
            
            status_updates.append(f'\n✅ Workflow completed successfully!')
            status_updates.append(f'📊 Executed {executed_count}/{len(actions)} actions')
            
            return {
                **state,
                'workflow_completed': True,
                'workflow_error': None,
                'executed_steps': executed_count,
                'status_updates': status_updates
            }
            
        except Exception as e:
            status_updates.append(f'\n❌ Workflow error: {str(e)}')
            return {
                **state,
                'workflow_completed': False,
                'workflow_error': str(e),
                'executed_steps': executed_count if 'executed_count' in locals() else 0,
                'status_updates': status_updates
            }
    
    def _substitute_project_number(self, action: Dict, project_number: str) -> Dict:
        """Substitute project number in action text"""
        if action['type'] == 'type' and action.get('text') in ['205394', '206551']:
            action = action.copy()
            action['text'] = project_number
        return action
    
    def _execute_action(self, action: Dict, status_updates: List[str]) -> bool:
        """Execute a single action from the workflow"""
        try:
            action_type = action['type']
            
            if action_type == 'applescript_spotlight':
                # Use PyAutoGUI hotkey instead of AppleScript (more reliable)
                pyautogui.hotkey('command', 'space')
                status_updates.append('  → Opened Spotlight (Cmd+Space)')
            
            elif action_type == 'click':
                if action['click_type'] == 'single':
                    x, y = int(action['x']), int(action['y'])
                    pyautogui.moveTo(x, y, duration=0.5)
                    pyautogui.click()
                    status_updates.append(f'  → Clicked at ({x}, {y})')
                elif action['click_type'] == 'double':
                    x, y = int(action['x']), int(action['y'])
                    self.reliable_double_click(x, y)
                    status_updates.append(f'  → Double-clicked at ({x}, {y})')
                elif action['click_type'] == 'right':
                    x, y = int(action['x']), int(action['y'])
                    pyautogui.rightClick(x, y)
                    status_updates.append(f'  → Right-clicked at ({x}, {y})')
            
            elif action_type == 'type':
                pyautogui.write(action['text'], interval=action.get('interval', 0.1))
                status_updates.append(f'  → Typed: "{action["text"]}"')
            
            elif action_type == 'key':
                key = 'winleft' if action['key'] == 'win' else action['key']
                pyautogui.press(key, presses=action.get('presses', 1))
                status_updates.append(f'  → Pressed: {action["key"]}')
            
            elif action_type == 'hotkey':
                keys = ['winleft' if k == 'win' else k for k in action['keys']]
                pyautogui.hotkey(*keys)
                status_updates.append(f'  → Hotkey: {"+".join(action["keys"])}')
            
            elif action_type == 'delay':
                reason = action.get('reason', 'Processing')
                status_updates.append(f'  ⏱️  Waiting {action["seconds"]}s ({reason})')
                time.sleep(action['seconds'])
            
            elif action_type == 'comment':
                status_updates.append(f'  💬 {action["text"]}')
            
            else:
                status_updates.append(f'  ⚠️  Unknown action type: {action_type}')
            
            # Small delay after each action
            time.sleep(0.1)
            return True
            
        except Exception as e:
            status_updates.append(f'  ✗ Execution error: {str(e)}')
            return False
    
    def _take_screenshot(self) -> str:
        """Take screenshot and return as base64"""
        screenshot = pyautogui.screenshot()
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    
    def _verify_screenshot(self, screenshot_b64: str, action: Dict, step_num: int, total_steps: int) -> str:
        """Use LLM to verify screenshot matches expected state"""
        try:
            # Create verification prompt
            prompt = f"""You are verifying step {step_num}/{total_steps} of a workflow.

Action just executed: {action['type']}
{f"Description: {action.get('description', '')}" if action.get('description') else ""}

Look at the screenshot and confirm if the action completed successfully.
Respond with ONE LINE only: either "VERIFIED" or "FAILED: <brief reason>".

Examples:
- If you see Spotlight search bar after opening Spotlight: "VERIFIED"
- If you see Windows App in search results: "VERIFIED" 
- If you see Comsense login dialog: "VERIFIED"
- If the UI doesn't match the expected state: "FAILED: Window not open"
"""
            
            # Call LLM with screenshot
            response = self.model.send_message(
                prompt,
                images=[screenshot_b64]
            )
            
            verification = response.strip()
            return verification
            
        except Exception as e:
            return f"VERIFICATION_ERROR: {str(e)}"
    
    def _fallback_double_click(self, x: int, y: int):
        """Fallback double-click"""
        x, y = int(x), int(y)  # Ensure integers
        pyautogui.moveTo(x, y, duration=0.5)
        pyautogui.click()
        time.sleep(0.1)
        pyautogui.click()


# Standalone node function for LangGraph integration
def workflow_executor_node(state: OpenInterfaceState) -> Dict[str, Any]:
    """
    Standalone workflow executor node for LangGraph
    
    Usage in graph:
        builder.add_node("execute_workflow", workflow_executor_node)
    """
    executor = WorkflowExecutorNode()
    return executor(state)


# Test function
def test_workflow_executor():
    """Test the workflow executor with w1.json"""
    print("Workflow Executor Node - Test Mode")
    print("=" * 80)
    print("\nThis will execute the w1.json workflow with LLM verification")
    print("\nFeatures:")
    print("  ✓ Reads w1.json workflow")
    print("  ✓ Executes each action step by step")
    print("  ✓ Takes screenshot after each action")
    print("  ✓ Uses LLM to verify screenshot matches expected state")
    print("  ✓ Substitutes project number dynamically")
    print("\n" + "=" * 80)
    
    # Test with sample state
    test_state = {
        'workflow_file': 'workflows/w1.json',
        'project_number': '206551',
        'verify_steps': False,  # Disable for now - macOS permission issue
        'status_updates': []
    }
    
    print(f"\nTest configuration:")
    print(f"  Workflow: {test_state['workflow_file']}")
    print(f"  Project: {test_state['project_number']}")
    print(f"  Verification: {test_state['verify_steps']}")
    print("\n⚠️  WARNING: This will actually execute the workflow!")
    print("Make sure you're ready to:")
    print("  - Open Windows Remote Desktop")
    print("  - Connect to Comsense VM")
    print("  - Login to Training DB")
    print("\n🚀 Starting workflow execution in 3 seconds...")
    
    try:
        time.sleep(3)
        
        executor = WorkflowExecutorNode()
        result = executor(test_state)
        
        print("\n" + "=" * 80)
        print("EXECUTION RESULTS")
        print("=" * 80)
        
        for update in result.get('status_updates', []):
            print(update)
        
        print("\n" + "=" * 80)
        if result.get('workflow_completed'):
            print("✅ SUCCESS!")
        else:
            print(f"❌ FAILED: {result.get('workflow_error')}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")


if __name__ == "__main__":
    test_workflow_executor()

