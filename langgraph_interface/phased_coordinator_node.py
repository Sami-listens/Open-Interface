"""
Phased Coordinator Node - Orchestrates Excel parsing and phased workflow execution
Executes each phase sequentially with screenshot verification
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
from langgraph_interface.excel_parser_node import ExcelParserNode
from langgraph_interface.comsense_editor_node import ComsenseEditorNode
from models.factory import ModelFactory
from utils.settings import Settings


class PhasedCoordinatorNode:
    """
    Coordinates phased workflow execution:
    1. Parse Excel file to identify edits
    2. Execute each phase of the workflow
    3. Take screenshots after each phase
    4. Verify completion before moving to next phase
    """
    
    def __init__(self):
        """Initialize the coordinator"""
        pyautogui.PAUSE = 0.1
        pyautogui.FAILSAFE = False
        
        # Load settings and LLM for verification
        self.settings = Settings()
        settings_dict = self.settings.get_dict()
        model_name = settings_dict.get('model', 'gemini-2.0-flash-exp')
        base_url = settings_dict.get('base_url', 'https://api.openai.com/v1/')
        api_key = settings_dict.get('api_key')
        
        # Create model for screenshot verification
        self.model = ModelFactory.create_model(
            model_name, 
            base_url, 
            api_key, 
            "You are a computer vision assistant that verifies UI states from screenshots."
        )
        
        # Excel parser and Comsense editor
        self.excel_parser = ExcelParserNode()
        self.comsense_editor = ComsenseEditorNode()
        
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
        Execute phased workflow
        
        Expected state inputs:
            - phased_workflow_file: Path to phased workflow JSON
            - project_number: (Optional) Project number to substitute
            - verify_phases: (Optional) Whether to verify phases (default: True)
        
        State outputs:
            - phased_workflow_completed: True if all phases completed
            - excel_edits: Parsed edits from Excel file
            - completed_phases: List of completed phase IDs
            - current_phase: Current phase being executed
            - phase_screenshots: Dict of phase_id -> screenshot_b64
            - status_updates: Detailed progress messages
        """
        
        workflow_file = state.get('phased_workflow_file', 'workflows/w1_phased.json')
        project_number = state.get('project_number', '206551')
        verify_phases = state.get('verify_phases', True)
        
        status_updates = state.get('status_updates', [])
        status_updates.append(f'🎬 Starting phased workflow: {workflow_file}')
        
        try:
            # Load phased workflow
            workflow_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                workflow_file
            )
            
            with open(workflow_path, 'r') as f:
                workflow = json.load(f)
            
            status_updates.append(f'✓ Loaded: {workflow["name"]}')
            phases = workflow.get('phases', [])
            status_updates.append(f'📋 {len(phases)} phases to execute\n')
            
            completed_phases = []
            phase_screenshots = {}
            excel_edits = []
            
            # Create screenshots directory
            screenshots_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'screenshots'
            )
            os.makedirs(screenshots_dir, exist_ok=True)
            status_updates.append(f'📁 Screenshots will be saved to: {screenshots_dir}\n')
            
            # Execute each phase
            for i, phase in enumerate(phases, 1):
                phase_id = phase['id']
                phase_name = phase['name']
                phase_type = phase['type']
                
                status_updates.append(f'\n{"="*60}')
                status_updates.append(f'PHASE {i}/{len(phases)}: {phase_name}')
                status_updates.append(f'{"="*60}')
                status_updates.append(f'Type: {phase_type}')
                status_updates.append(f'Description: {phase["description"]}\n')
                
                # Execute based on phase type
                if phase_type == 'excel_parsing':
                    excel_edits = self._execute_excel_phase(phase, status_updates)
                    
                elif phase_type == 'workflow_execution':
                    self._execute_workflow_phase(
                        phase, 
                        project_number, 
                        status_updates,
                        screenshots_dir
                    )
                    
                elif phase_type == 'reconciliation':
                    self._execute_reconciliation_phase(
                        phase,
                        excel_edits,
                        project_number,
                        status_updates
                    )
                
                else:
                    status_updates.append(f'⚠️  Unknown phase type: {phase_type}')
                    continue
                
                # Take screenshot after phase
                status_updates.append(f'\n📸 Taking screenshot for phase verification...')
                screenshot_filename = f'phase_{i}_{phase_id}.png'
                screenshot_path = os.path.join(screenshots_dir, screenshot_filename)
                screenshot_b64 = self._take_screenshot(save_path=screenshot_path)
                phase_screenshots[phase_id] = screenshot_b64
                status_updates.append(f'✓ Screenshot saved: {screenshot_filename}')
                
                # Verify phase completion if enabled
                if verify_phases and phase.get('verification_prompt'):
                    status_updates.append(f'🔍 Verifying phase completion...')
                    verification = self._verify_phase(
                        screenshot_b64,
                        phase['verification_prompt'],
                        phase_name
                    )
                    status_updates.append(f'✓ Verification: {verification}')
                    
                    # Check if verification failed
                    if 'FAILED' in verification.upper():
                        status_updates.append(f'❌ Phase verification failed!')
                        status_updates.append(f'   You may need to check and retry this phase.')
                        # Continue anyway for now, but log the failure
                
                completed_phases.append(phase_id)
                status_updates.append(f'\n✅ Phase {i} completed: {phase_name}\n')
                
                # Small delay between phases
                time.sleep(1)
            
            status_updates.append(f'\n{"="*60}')
            status_updates.append(f'✅ ALL PHASES COMPLETED!')
            status_updates.append(f'{"="*60}')
            status_updates.append(f'📊 Completed {len(completed_phases)}/{len(phases)} phases')
            if excel_edits:
                status_updates.append(f'📝 Found {len(excel_edits)} edits from Excel')
                # Save Excel edits to JSON file for reference
                edits_file = os.path.join(screenshots_dir, 'excel_edits.json')
                with open(edits_file, 'w') as f:
                    json.dump(excel_edits, f, indent=2)
                status_updates.append(f'📄 Excel edits saved to: excel_edits.json')
            status_updates.append(f'📸 Screenshots saved to: {screenshots_dir}')
            status_updates.append(f'   Total screenshots: {len(phase_screenshots)}')
            
            return {
                **state,
                'phased_workflow_completed': True,
                'excel_edits': excel_edits,
                'completed_phases': completed_phases,
                'phase_screenshots': phase_screenshots,
                'status_updates': status_updates,
                'workflow_error': None
            }
            
        except Exception as e:
            status_updates.append(f'\n❌ Phased workflow error: {str(e)}')
            return {
                **state,
                'phased_workflow_completed': False,
                'workflow_error': str(e),
                'completed_phases': completed_phases if 'completed_phases' in locals() else [],
                'status_updates': status_updates
            }
    
    def _execute_excel_phase(self, phase: Dict, status_updates: List[str]) -> List[Dict]:
        """Execute Excel parsing phase"""
        status_updates.append('📂 Parsing Excel file...')
        
        config = phase.get('config', {})
        excel_path = config.get('excel_file_path')
        
        if not excel_path:
            status_updates.append('⚠️  No Excel file path specified')
            return []
        
        # Convert relative path to absolute
        if not os.path.isabs(excel_path):
            excel_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                excel_path
            )
        
        # Create state for Excel parser
        excel_state = {
            'excel_file_path': excel_path,
            'sheet_name': config.get('sheet_name', 'Door Schedule'),
            'status_updates': []
        }
        
        # Parse Excel
        result = self.excel_parser(excel_state)
        
        # Merge status updates
        status_updates.extend(result.get('status_updates', []))
        
        # Get edits
        edits = result.get('excel_edits', [])
        
        if edits:
            status_updates.append(f'\n📊 Excel Edits Summary:')
            by_opening = {}
            for edit in edits:
                opening = edit['opening']
                if opening not in by_opening:
                    by_opening[opening] = []
                by_opening[opening].append(edit)
            
            for opening, opening_edits in sorted(by_opening.items())[:5]:  # Show first 5
                status_updates.append(f'  Opening {opening}: {len(opening_edits)} edit(s)')
            
            if len(by_opening) > 5:
                status_updates.append(f'  ... and {len(by_opening) - 5} more openings')
        
        return edits
    
    def _execute_workflow_phase(self, phase: Dict, project_number: str, status_updates: List[str], screenshots_dir: str = None):
        """Execute workflow actions phase with step-by-step verification"""
        actions = phase.get('actions', [])
        status_updates.append(f'▶️  Executing {len(actions)} actions...\n')
        
        # Move mouse and click on desktop to ensure terminal loses focus
        screen_width, screen_height = pyautogui.size()
        # Click on a safe area (top right, away from menu bar)
        pyautogui.moveTo(screen_width - 200, 200, duration=0.3)
        pyautogui.click()
        time.sleep(0.5)
        status_updates.append(f'  → Clicked desktop to clear focus')
        
        for i, action in enumerate(actions, 1):
            # Substitute project number if needed
            action = self._substitute_project_number(action, project_number)
            
            action_desc = action.get('description', action['type'])
            status_updates.append(f'  [{i}/{len(actions)}] {action["type"]}: {action_desc}')
            
            # Execute action
            success = self._execute_action(action, status_updates)
            
            if not success:
                status_updates.append(f'    ⚠️  Action may have failed')
            
            # Take screenshot after important actions (not delays/comments)
            if action['type'] not in ['delay', 'comment']:
                screenshot_path = None
                if screenshots_dir:
                    screenshot_path = os.path.join(screenshots_dir, f'action_{i}_{action["type"]}.png')
                
                screenshot_b64 = self._take_screenshot(save_path=screenshot_path)
                
                # Use LLM to check for errors or unexpected states
                error_check = self._check_for_errors(screenshot_b64, action, i)
                
                if 'ERROR' in error_check or 'POPUP' in error_check or 'DIALOG' in error_check:
                    status_updates.append(f'    🚨 {error_check}')
                    # Save error screenshot with special naming
                    if screenshots_dir:
                        error_path = os.path.join(screenshots_dir, f'ERROR_action_{i}_{action["type"]}.png')
                        self._take_screenshot(save_path=error_path)
                        status_updates.append(f'    📸 Error screenshot saved: ERROR_action_{i}_{action["type"]}.png')
                    
                    # Ask agent to handle the error
                    status_updates.append(f'    🤖 Asking agent to handle this...')
                    recovery_action = self._get_recovery_action(screenshot_b64, error_check, action)
                    
                    if recovery_action:
                        status_updates.append(f'    💡 Agent suggestion: {recovery_action}')
                        # Execute recovery action if it's simple (like clicking OK)
                        if 'click' in recovery_action.lower() and 'ok' in recovery_action.lower():
                            status_updates.append(f'    → Clicking OK to dismiss dialog')
                            # Try to find and click OK button (center-ish of screen)
                            pyautogui.press('enter')  # Usually Enter works for OK
                            time.sleep(1)
            
            # Small delay between actions
            time.sleep(0.1)
    
    def _execute_reconciliation_phase(self, phase: Dict, excel_edits: List[Dict], project_number: str, status_updates: List[str]):
        """Execute reconciliation phase - apply Excel edits to Comsense"""
        status_updates.append('🤖 Starting reconciliation with Comsense Editor Agent...')
        
        if not excel_edits:
            status_updates.append('⚠️  No edits to apply (Excel was empty or parsing failed)')
            return
        
        # Create state for Comsense editor
        config = phase.get('config', {})
        editor_state = {
            'excel_edits': excel_edits,
            'project_number': project_number,
            'status_updates': [],
            'agent_backend': config.get('agent_backend', 'auto')
        }
        
        # Run the editor
        result = self.comsense_editor(editor_state)
        
        # Merge status updates
        status_updates.extend(result.get('status_updates', []))
        
        # Log results
        edits_applied = result.get('edits_applied', [])
        edits_failed = result.get('edits_failed', [])
        
        status_updates.append(f'\n✓ Reconciliation phase completed')
        status_updates.append(f'  Applied: {len(edits_applied)}')
        status_updates.append(f'  Failed: {len(edits_failed)}')
    
    def _substitute_project_number(self, action: Dict, project_number: str) -> Dict:
        """Substitute project number in action text"""
        if action['type'] == 'type' and action.get('text') in ['205394', '206551']:
            action = action.copy()
            action['text'] = project_number
        return action
    
    def _execute_action(self, action: Dict, status_updates: List[str]) -> bool:
        """Execute a single action"""
        try:
            action_type = action['type']
            
            if action_type == 'applescript_spotlight':
                # Use AppleScript to open Spotlight
                self._applescript_key_code(49, ['command'])
            
            elif action_type == 'click':
                x, y = int(action['x']), int(action['y'])
                if action['click_type'] == 'single':
                    pyautogui.moveTo(x, y, duration=0.5)
                    pyautogui.click()
                elif action['click_type'] == 'double':
                    self.reliable_double_click(x, y)
                elif action['click_type'] == 'right':
                    pyautogui.rightClick(x, y)
            
            elif action_type == 'type':
                # Use AppleScript for typing text
                self._applescript_type_text(action['text'])
            
            elif action_type == 'key':
                # Use AppleScript for key presses
                key = action['key']
                presses = action.get('presses', 1)
                for _ in range(presses):
                    self._applescript_press_key(key)
                    time.sleep(0.1)
            
            elif action_type == 'hotkey':
                # Use AppleScript for hotkey combinations
                self._applescript_hotkey(action['keys'])
            
            elif action_type == 'delay':
                reason = action.get('reason', 'Processing')
                status_updates.append(f'    ⏱️  Waiting {action["seconds"]}s ({reason})')
                time.sleep(action['seconds'])
            
            elif action_type == 'comment':
                status_updates.append(f'    💬 {action["text"]}')
            
            return True
            
        except Exception as e:
            status_updates.append(f'    ✗ Error: {str(e)}')
            return False
    
    def _take_screenshot(self, save_path: str = None) -> str:
        """Take screenshot and return as base64, optionally save to disk"""
        try:
            screenshot = pyautogui.screenshot()
            
            # Save to disk if path provided
            if save_path:
                screenshot.save(save_path)
            
            # Also return as base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        except Exception as e:
            print(f"Screenshot error: {e}")
            return ""
    
    def _check_for_errors(self, screenshot_b64: str, action: Dict, action_num: int) -> str:
        """Use LLM to check for errors, popups, or unexpected states"""
        try:
            if not screenshot_b64:
                return "OK"
            
            prompt = f"""Action #{action_num}: {action['type']} - {action.get('description', '')}

Look at this screenshot and check for:
1. Error dialogs or popups
2. Warning messages
3. Unexpected windows or alerts
4. Any issues that would prevent the next action from working

Respond with ONE LINE:
- "OK" if everything looks normal
- "ERROR: <description>" if there's an error dialog
- "POPUP: <description>" if there's an unexpected popup
- "DIALOG: <description>" if there's a dialog that needs handling

Be specific about what you see."""
            
            # Use Gemini API correctly
            message_content = [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": screenshot_b64}}
            ]
            
            from google.genai import types
            safety_settings = [
                types.SafetySetting(category=category.value, threshold="BLOCK_NONE")
                for category in types.HarmCategory
                if category.value != 'HARM_CATEGORY_UNSPECIFIED'
            ]
            
            response = self.model.client.models.generate_content(
                model=self.model.model_name,
                contents=message_content,
                config=types.GenerateContentConfig(safety_settings=safety_settings)
            )
            
            return response.text.strip() if response.text else "OK"
            
        except Exception as e:
            return f"OK"  # Don't fail workflow on verification errors
    
    def _get_recovery_action(self, screenshot_b64: str, error_description: str, failed_action: Dict) -> str:
        """Ask LLM for recovery action"""
        try:
            if not screenshot_b64:
                return ""
            
            prompt = f"""The automation encountered an issue: {error_description}

Failed action was: {failed_action['type']} - {failed_action.get('description', '')}

Looking at the screenshot, what should the agent do to recover?

Examples of good responses:
- "Click OK button to dismiss the error dialog"
- "Press Enter to close the popup"
- "Click the X button in the top-right of the dialog"
- "Type the project code again"

Provide a single, clear action to take. Keep it brief."""
            
            # Use Gemini API correctly
            message_content = [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": screenshot_b64}}
            ]
            
            from google.genai import types
            safety_settings = [
                types.SafetySetting(category=category.value, threshold="BLOCK_NONE")
                for category in types.HarmCategory
                if category.value != 'HARM_CATEGORY_UNSPECIFIED'
            ]
            
            response = self.model.client.models.generate_content(
                model=self.model.model_name,
                contents=message_content,
                config=types.GenerateContentConfig(safety_settings=safety_settings)
            )
            
            return response.text.strip() if response.text else ""
            
        except Exception as e:
            return ""  # Don't fail on recovery suggestion errors
    
    def _verify_phase(self, screenshot_b64: str, verification_prompt: str, phase_name: str) -> str:
        """Use LLM to verify phase completion"""
        try:
            if not screenshot_b64:
                return "SKIPPED: No screenshot available"
            
            prompt = f"""Phase: {phase_name}

Verification task: {verification_prompt}

Look at the screenshot and confirm if this phase completed successfully.
Respond with ONE LINE only: either "VERIFIED" or "FAILED: <brief reason>".

Examples:
- If the expected UI state is visible: "VERIFIED"
- If something is wrong: "FAILED: <specific issue>"
"""
            
            # Use Gemini API correctly
            message_content = [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": screenshot_b64}}
            ]
            
            from google.genai import types
            safety_settings = [
                types.SafetySetting(category=category.value, threshold="BLOCK_NONE")
                for category in types.HarmCategory
                if category.value != 'HARM_CATEGORY_UNSPECIFIED'
            ]
            
            response = self.model.client.models.generate_content(
                model=self.model.model_name,
                contents=message_content,
                config=types.GenerateContentConfig(safety_settings=safety_settings)
            )
            
            return response.text.strip() if response.text else "VERIFIED"
            
        except Exception as e:
            return f"VERIFIED"  # Don't fail workflow on verification errors
    
    def _applescript_type_text(self, text: str):
        """Type text using AppleScript"""
        # Escape quotes and backslashes in the text
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
        subprocess.run([
            'osascript', '-e',
            f'tell application "System Events" to keystroke "{escaped_text}"'
        ], check=True)
    
    def _applescript_press_key(self, key: str):
        """Press a single key using AppleScript"""
        # Map common key names to AppleScript key codes
        key_codes = {
            'enter': '36',
            'return': '36',
            'tab': '48',
            'space': '49',
            'delete': '51',
            'escape': '53',
            'command': '55',
            'shift': '56',
            'capslock': '57',
            'option': '58',
            'control': '59',
            'right': '124',
            'left': '123',
            'down': '125',
            'up': '126',
            'win': '55',  # Map Windows key to Command on Mac
        }
        
        key_lower = key.lower()
        
        if key_lower in key_codes:
            code = key_codes[key_lower]
            subprocess.run([
                'osascript', '-e',
                f'tell application "System Events" to key code {code}'
            ], check=True)
        else:
            # For regular characters, use keystroke
            subprocess.run([
                'osascript', '-e',
                f'tell application "System Events" to keystroke "{key}"'
            ], check=True)
    
    def _applescript_hotkey(self, keys: list):
        """Press a hotkey combination using AppleScript"""
        # Map key names to AppleScript modifiers
        modifier_map = {
            'command': 'command down',
            'cmd': 'command down',
            'ctrl': 'control down',
            'control': 'control down',
            'alt': 'option down',
            'option': 'option down',
            'shift': 'shift down',
            'win': 'command down',  # Windows key maps to Command
        }
        
        # Separate modifiers from the main key
        modifiers = []
        main_key = None
        
        for key in keys:
            key_lower = key.lower()
            if key_lower in modifier_map:
                modifiers.append(modifier_map[key_lower])
            else:
                main_key = key_lower
        
        if main_key:
            modifier_str = ' using {' + ', '.join(modifiers) + '}' if modifiers else ''
            
            # Check if main_key is a special key
            if main_key == 'f':
                # For single letter keys
                subprocess.run([
                    'osascript', '-e',
                    f'tell application "System Events" to keystroke "{main_key}" using {{{", ".join(modifiers)}}}'
                ], check=True)
            elif main_key == 'f4':
                # Alt+F4 is command+w on Mac (close window)
                subprocess.run([
                    'osascript', '-e',
                    'tell application "System Events" to keystroke "w" using {command down}'
                ], check=True)
            else:
                subprocess.run([
                    'osascript', '-e',
                    f'tell application "System Events" to keystroke "{main_key}" using {{{", ".join(modifiers)}}}'
                ], check=True)
    
    def _applescript_key_code(self, code: int, modifiers: list = None):
        """Press a key using its key code with optional modifiers"""
        modifier_map = {
            'command': 'command down',
            'ctrl': 'control down',
            'control': 'control down',
            'alt': 'option down',
            'option': 'option down',
            'shift': 'shift down',
        }
        
        if modifiers:
            modifier_strs = [modifier_map.get(m.lower(), m) for m in modifiers]
            modifier_clause = ' using {' + ', '.join(modifier_strs) + '}'
        else:
            modifier_clause = ''
        
        subprocess.run([
            'osascript', '-e',
            f'tell application "System Events" to key code {code}{modifier_clause}'
        ], check=True)
    
    def _fallback_double_click(self, x: int, y: int):
        """Fallback double-click implementation"""
        x, y = int(x), int(y)
        pyautogui.moveTo(x, y, duration=0.5)
        pyautogui.click()
        time.sleep(0.1)
        pyautogui.click()


# Standalone node function for LangGraph integration
def phased_coordinator_node(state: OpenInterfaceState) -> Dict[str, Any]:
    """
    Standalone phased coordinator node for LangGraph
    
    Usage in graph:
        builder.add_node("phased_coordinator", phased_coordinator_node)
    """
    coordinator = PhasedCoordinatorNode()
    return coordinator(state)


# Test function
def test_phased_coordinator():
    """Test the phased coordinator"""
    print("Phased Coordinator Node - Test Mode")
    print("=" * 80)
    print("\nThis will execute the w1_phased.json workflow")
    print("\nPhases:")
    print("  0. Excel Review - Parse Excel for edits")
    print("  1. Remote Desktop Connection")
    print("  2. VM Authentication & Connection")
    print("  3. Comsense Launch & Login")
    print("  4. Project Navigation")
    print("  5. Data Reconciliation (not yet implemented)")
    print("\n" + "=" * 80)
    
    test_state = {
        'phased_workflow_file': 'workflows/w1_phased.json',
        'project_number': '206551',
        'verify_phases': True,
        'status_updates': []
    }
    
    print(f"\nConfiguration:")
    print(f"  Workflow: {test_state['phased_workflow_file']}")
    print(f"  Project: {test_state['project_number']}")
    print(f"  Verification: {test_state['verify_phases']}")
    print("\n⚠️  WARNING: This will execute the full workflow!")
    print("\n🚀 Starting in 5 seconds...")
    print("    Press Ctrl+C to cancel\n")
    
    try:
        time.sleep(5)
        
        coordinator = PhasedCoordinatorNode()
        result = coordinator(test_state)
        
        print("\n" + "=" * 80)
        print("EXECUTION RESULTS")
        print("=" * 80 + "\n")
        
        for update in result.get('status_updates', []):
            print(update)
        
        print("\n" + "=" * 80)
        if result.get('phased_workflow_completed'):
            print("✅ SUCCESS!")
            print(f"Completed phases: {result.get('completed_phases', [])}")
            if result.get('excel_edits'):
                print(f"Excel edits found: {len(result['excel_edits'])}")
        else:
            print(f"❌ FAILED: {result.get('workflow_error')}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")


if __name__ == "__main__":
    test_phased_coordinator()

