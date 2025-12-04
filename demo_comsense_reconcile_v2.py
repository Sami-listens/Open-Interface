#!/usr/bin/env python3
"""
Demo Comsense Reconciliation with Gemini Vision (google-genai)
Using the newer google-genai SDK instead of legacy google-generativeai
"""

import sys
import os
import pyautogui
import time
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure pyautogui for safety
pyautogui.PAUSE = 0.5
pyautogui.FAILSAFE = True


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


def take_and_save_screenshot(name):
    """Take and save a screenshot"""
    os.makedirs("demo_screenshots", exist_ok=True)
    screenshot = pyautogui.screenshot()
    filename = f"demo_screenshots/{name}.png"
    screenshot.save(filename)
    print(f"  📸 Saved: {filename}")
    return screenshot


class GeminiVisionAgent:
    """Gemini vision agent using the new google-genai SDK"""
    
    def __init__(self, api_key: str):
        # Initialize the client with API key
        self.client = genai.Client(api_key=api_key)
        self.screen_width, self.screen_height = pyautogui.size()
        print(f"  🖥️  Screen size: {self.screen_width}x{self.screen_height}")
        print(f"  🤖 Using: Gemini 2.0 Flash Experimental")
    
    def analyze_screenshot(self, screenshot, instruction):
        """Analyze screenshot and determine action"""
        # Convert PIL image to bytes
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        buffered.seek(0)
        
        # Create the message with image
        prompt = f"""
You are a UI automation assistant. Analyze this screenshot and help with:
{instruction}

The screen dimensions are {self.screen_width}x{self.screen_height} pixels.

Provide your response in this exact format:
DESCRIPTION: [What you see in the UI]
ACTION: [One of: click, type, key, wait, done]
COORDINATES: [x,y for clicks, or none]
TEXT: [text to type, or none]
KEY: [key name for key presses, or none]
REASONING: [Why this action helps]

For clicks, provide exact pixel coordinates like: COORDINATES: 450,320
For typing, provide the text like: TEXT: Hello World
For keys, use pyautogui key names like: KEY: tab
"""
        
        try:
            # Generate content using the new API
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
            
            # Parse the response
            text = response.text
            result = self.parse_response(text)
            
            if result:
                print(f"  🤖 Agent sees: {result.get('description', 'N/A')}")
                print(f"  💭 Reasoning: {result.get('reasoning', 'N/A')}")
            
            return result
            
        except Exception as e:
            print(f"  ❌ Error analyzing screenshot: {e}")
            return {"action": "wait", "reasoning": str(e)}
    
    def parse_response(self, text):
        """Parse the structured response"""
        result = {}
        
        lines = text.split('\n')
        for line in lines:
            if line.startswith('DESCRIPTION:'):
                result['description'] = line.replace('DESCRIPTION:', '').strip()
            elif line.startswith('ACTION:'):
                result['action'] = line.replace('ACTION:', '').strip().lower()
            elif line.startswith('COORDINATES:'):
                coords_str = line.replace('COORDINATES:', '').strip()
                if coords_str and coords_str.lower() != 'none':
                    try:
                        x, y = map(int, coords_str.split(','))
                        result['coordinates'] = (x, y)
                    except:
                        pass
            elif line.startswith('TEXT:'):
                text_val = line.replace('TEXT:', '').strip()
                if text_val and text_val.lower() != 'none':
                    result['text'] = text_val
            elif line.startswith('KEY:'):
                key_val = line.replace('KEY:', '').strip()
                if key_val and key_val.lower() != 'none':
                    result['key'] = key_val
            elif line.startswith('REASONING:'):
                result['reasoning'] = line.replace('REASONING:', '').strip()
        
        return result
    
    def execute_action(self, action_data):
        """Execute the determined action"""
        action = action_data.get('action', 'wait')
        
        try:
            if action == 'click' and 'coordinates' in action_data:
                x, y = action_data['coordinates']
                print(f"  🖱️ Clicking at ({x}, {y})")
                pyautogui.click(x, y)
                time.sleep(0.5)
                return True
            
            elif action == 'type' and 'text' in action_data:
                text = action_data['text']
                print(f"  ⌨️ Typing: {text}")
                pyautogui.typewrite(text)
                time.sleep(0.5)
                return True
            
            elif action == 'key' and 'key' in action_data:
                key = action_data['key']
                print(f"  ⌨️ Pressing key: {key}")
                pyautogui.press(key)
                time.sleep(0.5)
                return True
            
            elif action == 'wait':
                print(f"  ⏳ Waiting...")
                time.sleep(1)
                return True
            
            elif action == 'done':
                print(f"  ✅ Task complete")
                return True
                
        except Exception as e:
            print(f"  ❌ Error executing action: {e}")
            return False
        
        return False


def run_demo():
    """Run the demo workflow"""
    print("\n" + "="*80)
    print("🎬 COMSENSE RECONCILIATION DEMO (google-genai)")
    print("="*80)
    print("\n📋 This demo will:")
    print("  1. Load edits from Excel")
    print("  2. Navigate to Doors module")  
    print("  3. Apply edits using Gemini Vision")
    print("\n⚠️  Make sure Comsense is open with project 1200255 loaded!")
    print("⏳ Starting in 5 seconds... (Move mouse to corner to abort)\n")
    
    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    
    # Load API key
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return 1
    
    # Initialize agent
    print("\n🤖 Initializing Gemini Vision Agent...")
    agent = GeminiVisionAgent(api_key)
    print("✅ Agent initialized\n")
    
    # Load edits
    print("📂 Loading edits from Excel...")
    edits = get_excel_edits()
    print(f"✅ Found {len(edits)} edits\n")
    
    if not edits:
        print("❌ No edits found")
        return 1
    
    # Show edits
    print("📝 Edits to apply:")
    for i, edit in enumerate(edits, 1):
        marker = "🟡" if edit['is_yellow'] else "🔴"
        print(f"  {i}. {marker} {edit['opening']}: {edit['field']} → {edit['new_value']}")
    print()
    
    # Phase 1: Navigate to Doors
    print("="*80)
    print("PHASE 1: NAVIGATE TO DOORS MODULE")
    print("="*80)
    
    screenshot = take_and_save_screenshot("01_initial")
    
    print("\n🔍 Looking for Doors module...")
    action = agent.analyze_screenshot(
        screenshot,
        """Find the 'Doors' text/button in the left sidebar under the ESTIMATING section.
        It should be near the top of the ESTIMATING list.
        Look for a small clickable text item that says exactly 'Doors'.
        The coordinates should be in the left sidebar area (x < 300)."""
    )
    
    if action and action.get('action') == 'click':
        coords = action.get('coordinates')
        print(f"  📍 Agent suggested: {coords}")
        
        agent.execute_action(action)
        time.sleep(3)
        
        # Verify we opened the right module
        verify_screenshot = take_and_save_screenshot("01b_after_click")
        verify_action = agent.analyze_screenshot(
            verify_screenshot,
            """Check if we successfully opened the Doors module.
            Look for: 
            - A table/grid with door data
            - Headers like 'Opening', 'Width', 'Height', 'Exterior', etc.
            - Door numbers like 102B, 103WP, 104A in the table
            
            If you see this, respond with ACTION: done
            If you see something else (like 'Installation Operation Defaults'), respond with ACTION: wait"""
        )
        
        if verify_action and verify_action.get('action') == 'done':
            print("✅ Verified: Doors module is open")
            
            print("⌨️ Pressing Tab to load details...")
            pyautogui.press('tab')
            time.sleep(2)
            
            take_and_save_screenshot("02_doors_loaded")
            print("✅ Doors module loaded\n")
        else:
            print("⚠️ Wrong window opened. In production, Agent S3 with UI-TARS would be more accurate.")
            print("💡 For demo, please manually open Doors module and press Enter to continue...")
            input()
    else:
        print("⚠️ Could not find Doors module - continuing demo\n")
    
    # Phase 2: Apply first 2 edits for demo
    print("="*80)
    print("PHASE 2: APPLY EDITS (Demo: First 2)")
    print("="*80)
    
    demo_edits = edits[:2]  # Just first 2 for demo
    success_count = 0
    
    for idx, edit in enumerate(demo_edits, 1):
        print(f"\n📝 Edit {idx}: {edit['opening']} - {edit['field']} → {edit['new_value']}")
        
        screenshot = take_and_save_screenshot(f"edit_{idx}_before")
        
        # Find and click the door row
        instruction = f"Find door/opening {edit['opening']} in the table and click on the {edit['field']} field"
        action = agent.analyze_screenshot(screenshot, instruction)
        
        if action and action.get('action') == 'click':
            agent.execute_action(action)
            time.sleep(0.5)
            
            # Type new value
            print(f"  ⌨️ Entering new value: {edit['new_value']}")
            pyautogui.hotkey('ctrl', 'a')  # Select all
            time.sleep(0.2)
            pyautogui.typewrite(str(edit['new_value']))
            time.sleep(0.5)
            pyautogui.press('tab')
            time.sleep(1)
            
            take_and_save_screenshot(f"edit_{idx}_after")
            print(f"  ✅ Edit {idx} complete")
            success_count += 1
        else:
            print(f"  ⚠️ Could not locate field")
    
    # Summary
    print("\n" + "="*80)
    print("🎉 DEMO COMPLETE!")
    print("="*80)
    print(f"✅ Successfully applied: {success_count}/{len(demo_edits)} edits")
    print(f"📁 Screenshots saved in: demo_screenshots/")
    print("\n💡 Next steps:")
    print("  • Review the screenshots to verify edits")
    print("  • For full automation of all 5 edits, run the complete script")
    print("  • For production use, consider setting up UI-TARS grounding model")
    print("="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run_demo())
    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
