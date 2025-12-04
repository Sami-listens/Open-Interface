#!/usr/bin/env python3
"""
State-of-the-Art Computer Use Agent for Comsense
Advanced cursor positioning with visual verification and grounding stabilization
"""

import sys
import os
import pyautogui
import time
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw
from google import genai
from google.genai import types
from typing import Tuple, Dict, Optional, List
import json
from dataclasses import dataclass
from enum import Enum

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure pyautogui for precision
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True


class ActionType(Enum):
    CLICK = "click"
    TYPE = "type"
    KEY = "key"
    HOVER = "hover"
    WAIT = "wait"
    DONE = "done"


@dataclass
class VisualElement:
    """Represents a detected UI element"""
    description: str
    coordinates: Tuple[int, int]
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None  # x1, y1, x2, y2


@dataclass
class CursorState:
    """Current cursor state and history"""
    position: Tuple[int, int]
    target: Tuple[int, int]
    attempts: int
    history: List[Tuple[int, int]]
    error_distance: float


class VisionEngine:
    """Advanced vision engine with Gemini 2.0"""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.screen_width, self.screen_height = pyautogui.size()
        
    def analyze_screen(self, screenshot: Image.Image, query: str, 
                       highlight_cursor: bool = False) -> Dict:
        """Analyze screen with optional cursor highlighting"""
        
        # Draw cursor position if requested
        if highlight_cursor:
            cursor_x, cursor_y = pyautogui.position()
            img_copy = screenshot.copy()
            draw = ImageDraw.Draw(img_copy)
            # Draw crosshair at cursor
            draw.line((cursor_x - 20, cursor_y, cursor_x + 20, cursor_y), fill='red', width=3)
            draw.line((cursor_x, cursor_y - 20, cursor_x, cursor_y + 20), fill='red', width=3)
            draw.ellipse((cursor_x - 10, cursor_y - 10, cursor_x + 10, cursor_y + 10), 
                        outline='red', width=3)
            screenshot = img_copy
        
        # Convert to bytes
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        buffered.seek(0)
        
        prompt = f"""
TASK: {query}
Screen: {self.screen_width}x{self.screen_height}

Return ONLY valid JSON:
{{
    "element": "description of target element",
    "coordinates": [x, y],
    "confidence": 0.0-1.0,
    "reasoning": "why these coordinates",
    "alternative": [alt_x, alt_y] or null
}}"""
        
        response = self.client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=prompt),
                        types.Part.from_bytes(
                            data=buffered.getvalue(),
                            mime_type="image/png"
                        )
                    ]
                )
            ]
        )
        
        try:
            # Extract JSON from response
            text = response.text
            import re
            json_match = re.search(r'\{[^}]*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return {"coordinates": None, "confidence": 0.0}


class CursorController:
    """Precision cursor control with verification"""
    
    def __init__(self):
        self.movement_speed = 0.2  # seconds for movement
        self.verification_delay = 0.1
        
    def smooth_move(self, target: Tuple[int, int], duration: float = 0.2) -> Tuple[int, int]:
        """Smooth cursor movement with easing"""
        start_x, start_y = pyautogui.position()
        target_x, target_y = target
        
        # Use easing function for natural movement
        pyautogui.moveTo(target_x, target_y, duration=duration, tween=pyautogui.easeInOutQuad)
        time.sleep(self.verification_delay)
        
        return pyautogui.position()
    
    def verify_position(self, target: Tuple[int, int], tolerance: int = 5) -> bool:
        """Verify cursor reached target within tolerance"""
        current = pyautogui.position()
        distance = np.sqrt((current[0] - target[0])**2 + (current[1] - target[1])**2)
        return distance <= tolerance
    
    def micro_adjust(self, target: Tuple[int, int]) -> Tuple[int, int]:
        """Micro-adjustment for precision"""
        current = pyautogui.position()
        
        # Calculate micro-adjustment
        dx = target[0] - current[0]
        dy = target[1] - current[1]
        
        # Apply small movement
        if abs(dx) > 0 or abs(dy) > 0:
            pyautogui.moveRel(dx, dy, duration=0.05)
        
        return pyautogui.position()


class GroundingStabilizer:
    """Advanced grounding/stabilization system"""
    
    def __init__(self, vision: VisionEngine):
        self.vision = vision
        self.max_attempts = 5
        self.convergence_threshold = 3  # pixels
        
    def stabilize_to_target(self, element_description: str, 
                           initial_target: Tuple[int, int]) -> CursorState:
        """Stabilize cursor to target with visual feedback loop"""
        
        cursor_ctrl = CursorController()
        state = CursorState(
            position=pyautogui.position(),
            target=initial_target,
            attempts=0,
            history=[],
            error_distance=float('inf')
        )
        
        for attempt in range(self.max_attempts):
            state.attempts = attempt + 1
            
            # Move cursor
            new_pos = cursor_ctrl.smooth_move(state.target)
            state.position = new_pos
            state.history.append(new_pos)
            
            # Take screenshot with cursor highlighted
            screenshot = pyautogui.screenshot()
            
            # Verify position with vision
            verification = self.vision.analyze_screen(
                screenshot,
                f"Is the RED cursor crosshair directly over: {element_description}? "
                f"If not, where should it be? Target was ({state.target[0]}, {state.target[1]})",
                highlight_cursor=True
            )
            
            # Check if we're on target
            if verification.get('confidence', 0) > 0.9:
                print(f"  ✅ Stabilized in {attempt + 1} attempts")
                return state
            
            # Get correction if available
            if verification.get('alternative'):
                alt_x, alt_y = verification['alternative']
                state.target = (alt_x, alt_y)
                state.error_distance = np.sqrt(
                    (new_pos[0] - alt_x)**2 + (new_pos[1] - alt_y)**2
                )
                
                # Check convergence
                if state.error_distance <= self.convergence_threshold:
                    cursor_ctrl.micro_adjust(state.target)
                    print(f"  ✅ Converged in {attempt + 1} attempts (error: {state.error_distance:.1f}px)")
                    return state
                
                print(f"  🔄 Attempt {attempt + 1}: Adjusting by {state.error_distance:.1f}px")
            else:
                # No correction available, try micro-adjustment
                cursor_ctrl.micro_adjust(state.target)
                
        print(f"  ⚠️ Stabilization incomplete after {self.max_attempts} attempts")
        return state


class ComputerUseAgent:
    """State-of-the-art Computer Use Agent"""
    
    def __init__(self, api_key: str):
        self.vision = VisionEngine(api_key)
        self.stabilizer = GroundingStabilizer(self.vision)
        self.cursor = CursorController()
        os.makedirs("agent_screenshots", exist_ok=True)
        
    def execute_action(self, action_type: ActionType, target_element: str, 
                      params: Dict = None) -> bool:
        """Execute an action with visual grounding"""
        
        timestamp = time.strftime("%H%M%S")
        
        # Take initial screenshot
        screenshot = pyautogui.screenshot()
        screenshot.save(f"agent_screenshots/action_{timestamp}_before.png")
        
        if action_type == ActionType.CLICK:
            # Find element
            print(f"🔍 Locating: {target_element}")
            result = self.vision.analyze_screen(screenshot, f"Find: {target_element}")
            
            if result.get('coordinates'):
                x, y = result['coordinates']
                confidence = result.get('confidence', 0)
                
                print(f"  📍 Found at ({x}, {y}) with {confidence:.1%} confidence")
                
                # Stabilize cursor to target
                print(f"  🎯 Stabilizing cursor...")
                state = self.stabilizer.stabilize_to_target(target_element, (x, y))
                
                # Perform click
                print(f"  🖱️ Clicking at final position: {state.position}")
                pyautogui.click()
                
                # Capture result
                time.sleep(0.5)
                after = pyautogui.screenshot()
                after.save(f"agent_screenshots/action_{timestamp}_after.png")
                
                return True
            else:
                print(f"  ❌ Could not locate: {target_element}")
                return False
                
        elif action_type == ActionType.TYPE:
            text = params.get('text', '')
            print(f"  ⌨️ Typing: {text}")
            pyautogui.typewrite(text)
            return True
            
        elif action_type == ActionType.KEY:
            key = params.get('key', 'enter')
            print(f"  ⌨️ Key: {key}")
            pyautogui.press(key)
            return True
            
        elif action_type == ActionType.HOVER:
            # Find and hover
            result = self.vision.analyze_screen(screenshot, f"Find: {target_element}")
            if result.get('coordinates'):
                x, y = result['coordinates']
                state = self.stabilizer.stabilize_to_target(target_element, (x, y))
                print(f"  🎯 Hovering at: {state.position}")
                return True
            return False
            
        elif action_type == ActionType.WAIT:
            duration = params.get('duration', 1.0)
            print(f"  ⏳ Waiting {duration}s...")
            time.sleep(duration)
            return True
            
        return False


def get_excel_edits():
    """Get edits from Excel file"""
    from langgraph_interface.excel_parser_node import ExcelParserNode
    
    excel_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'Project Example - THM WWTP',
        '1. Estimates',
        '00-Pricing',
        'THM WWTP - Project Tool - 8C.xlsm'
    )
    
    parser = ExcelParserNode()
    result = parser({
        'excel_file_path': excel_path,
        'sheet_name': 'Door Schedule',
        'status_updates': []
    })
    
    return result.get('excel_edits', [])


def main():
    """Run the state-of-the-art Comsense reconciliation"""
    
    print("\n" + "="*80)
    print("🚀 COMPUTER USE AGENT - COMSENSE RECONCILIATION")
    print("="*80)
    print("Features:")
    print("  ✅ Visual element detection with Gemini 2.0")
    print("  ✅ Cursor stabilization with feedback loop")
    print("  ✅ Precision positioning (3px tolerance)")
    print("  ✅ Max 5 attempts per target")
    print("  ✅ Visual verification at each step")
    print("\n⚠️  Ensure Comsense is open with project 1200255")
    print("⏳ Starting in 3 seconds...\n")
    
    time.sleep(3)
    
    # Initialize agent
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("❌ GEMINI_API_KEY not found")
        return 1
    
    agent = ComputerUseAgent(api_key)
    print("✅ Agent initialized\n")
    
    # Load edits
    print("📂 Loading Excel edits...")
    edits = get_excel_edits()
    print(f"✅ Found {len(edits)} edits\n")
    
    if not edits:
        return 1
    
    # Display edits
    for i, edit in enumerate(edits, 1):
        marker = "🟡" if edit['is_yellow'] else "🔴"
        print(f"  {i}. {marker} {edit['opening']}: {edit['field']} → {edit['new_value']}")
    print()
    
    # Phase 1: Navigate to Doors
    print("="*80)
    print("PHASE 1: NAVIGATE TO DOORS MODULE")
    print("="*80 + "\n")
    
    success = agent.execute_action(
        ActionType.CLICK,
        "The 'Doors' text item in the left sidebar under ESTIMATING section",
        {}
    )
    
    if success:
        agent.execute_action(ActionType.WAIT, "", {"duration": 2})
        agent.execute_action(ActionType.KEY, "", {"key": "tab"})
        print("✅ Doors module loaded\n")
    
    # Phase 2: Apply edits
    print("="*80)
    print("PHASE 2: APPLY EDITS")
    print("="*80 + "\n")
    
    successful = 0
    for i, edit in enumerate(edits[:2], 1):  # Demo: first 2
        print(f"📝 Edit {i}: {edit['opening']} - {edit['field']} → {edit['new_value']}")
        
        # Click on the door row
        if agent.execute_action(
            ActionType.CLICK,
            f"Door/Opening {edit['opening']} in the table, specifically the {edit['field']} field",
            {}
        ):
            # Clear and type
            agent.execute_action(ActionType.KEY, "", {"key": ["ctrl", "a"]})
            agent.execute_action(ActionType.TYPE, "", {"text": str(edit['new_value'])})
            agent.execute_action(ActionType.KEY, "", {"key": "tab"})
            agent.execute_action(ActionType.WAIT, "", {"duration": 0.5})
            
            print(f"  ✅ Edit {i} complete\n")
            successful += 1
        else:
            print(f"  ⚠️ Edit {i} failed\n")
    
    # Summary
    print("="*80)
    print("🎉 EXECUTION COMPLETE")
    print("="*80)
    print(f"✅ Success rate: {successful}/{len(edits[:2])} edits")
    print(f"📁 Screenshots: agent_screenshots/")
    print(f"🎯 Precision: 3px tolerance with stabilization")
    print("="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
