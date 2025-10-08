#!/usr/bin/env python3
"""
Interactive Workflow Recorder for macOS

Records user actions (clicks, typing, hotkeys, etc.) into a JSON file
that can be played back later. Perfect for automating repetitive tasks.
"""

import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add conda environment packages
sys.path.insert(0, '/opt/anaconda3/envs/open-interface/lib/python3.12/site-packages')

import pyautogui
from final_double_click_solution import reliable_double_click

class WorkflowRecorder:
    """Interactive workflow recorder that saves actions to JSON."""
    
    def __init__(self):
        self.workflow = {
            "name": "",
            "description": "",
            "created": "",
            "screen_size": {},
            "actions": []
        }
        self.recording = False
        
    def start_recording(self):
        """Start a new recording session."""
        print("\n🎬 WORKFLOW RECORDER")
        print("=" * 50)
        
        # Get workflow metadata
        self.workflow["name"] = input("Workflow name: ").strip() or "Untitled Workflow"
        self.workflow["description"] = input("Description (optional): ").strip()
        self.workflow["created"] = datetime.now().isoformat()
        
        # Get screen size for reference
        screen_width, screen_height = pyautogui.size()
        self.workflow["screen_size"] = {
            "width": screen_width,
            "height": screen_height
        }
        
        print(f"\n📺 Screen size: {screen_width}x{screen_height}")
        print("\n✅ Recording started! Use the menu to add actions.")
        self.recording = True
        
    def show_menu(self):
        """Display the action menu."""
        print("\n" + "=" * 50)
        print("📋 ACTION MENU")
        print("=" * 50)
        print("1. 🖱️  Click (single)")
        print("2. 🖱️  Double-click (native macOS)")
        print("3. 🖱️  Right-click")
        print("4. ⌨️  Type text")
        print("5. ⌨️  Press key(s)")
        print("6. ⌨️  Hotkey combination")
        print("7. 🕐 Add delay")
        print("8. 📍 Move mouse")
        print("9. 📜 Scroll")
        print("10. 💬 Add comment")
        print("11. 🔍 Open Spotlight (macOS)")
        print("-" * 50)
        print("12. 👁️  Show recorded actions")
        print("13. ▶️  Test playback")
        print("14. 💾 Save and exit")
        print("15. ❌ Cancel (don't save)")
        print("=" * 50)
        
    def get_coordinates(self, prompt="Enter coordinates"):
        """Get coordinates from user or current mouse position."""
        print(f"\n{prompt}:")
        print("1. Use current mouse position")
        print("2. Enter coordinates manually")
        
        choice = input("Choice (1-2): ").strip()
        
        if choice == "1":
            print("Move mouse to desired position and press Enter...")
            input()
            x, y = pyautogui.position()
            print(f"Captured: ({x}, {y})")
        else:
            x = int(input("X coordinate: "))
            y = int(input("Y coordinate: "))
            
        return x, y
    
    def add_click(self, click_type="single"):
        """Add a click action."""
        x, y = self.get_coordinates(f"📍 {click_type.capitalize()}-click location")
        
        action = {
            "type": "click",
            "click_type": click_type,
            "x": x,
            "y": y,
            "timestamp": time.time()
        }
        
        # Add optional parameters
        if click_type == "single":
            duration = input("Move duration in seconds (default: 0.5): ").strip()
            action["move_duration"] = float(duration) if duration else 0.5
        
        self.workflow["actions"].append(action)
        print(f"✅ Added {click_type}-click at ({x}, {y})")
        
    def add_type_text(self):
        """Add a text typing action."""
        text = input("\n📝 Text to type: ")
        interval = input("Typing interval between chars (default: 0.1): ").strip()
        
        action = {
            "type": "type",
            "text": text,
            "interval": float(interval) if interval else 0.1,
            "timestamp": time.time()
        }
        
        self.workflow["actions"].append(action)
        print(f"✅ Added typing: '{text[:30]}{'...' if len(text) > 30 else ''}'")
        
    def add_key_press(self):
        """Add a key press action."""
        print("\n⌨️ Common keys: enter, tab, escape, space, up, down, left, right")
        key = input("Key to press: ").strip()
        presses = input("Number of presses (default: 1): ").strip()
        
        action = {
            "type": "key",
            "key": key,
            "presses": int(presses) if presses else 1,
            "timestamp": time.time()
        }
        
        self.workflow["actions"].append(action)
        print(f"✅ Added key press: {key} x{action['presses']}")
        
    def add_hotkey(self):
        """Add a hotkey combination."""
        print("\n⌨️ Enter keys separated by spaces")
        print("Example: command space (for Spotlight)")
        print("Example: ctrl command f (for fullscreen)")
        
        keys = input("Keys: ").strip().split()
        
        action = {
            "type": "hotkey",
            "keys": keys,
            "timestamp": time.time()
        }
        
        self.workflow["actions"].append(action)
        print(f"✅ Added hotkey: {'+'.join(keys)}")
        
    def add_delay(self):
        """Add a delay/wait action."""
        seconds = float(input("\n⏱️ Delay in seconds: "))
        reason = input("Reason for delay (optional): ").strip()
        
        action = {
            "type": "delay",
            "seconds": seconds,
            "reason": reason,
            "timestamp": time.time()
        }
        
        self.workflow["actions"].append(action)
        print(f"✅ Added {seconds}s delay" + (f" ({reason})" if reason else ""))
        
    def add_mouse_move(self):
        """Add a mouse movement action."""
        x, y = self.get_coordinates("📍 Move mouse to")
        duration = input("Move duration in seconds (default: 0.5): ").strip()
        
        action = {
            "type": "move",
            "x": x,
            "y": y,
            "duration": float(duration) if duration else 0.5,
            "timestamp": time.time()
        }
        
        self.workflow["actions"].append(action)
        print(f"✅ Added mouse move to ({x}, {y})")
        
    def add_scroll(self):
        """Add a scroll action."""
        direction = input("\n📜 Scroll direction (up/down): ").strip().lower()
        clicks = int(input("Number of scroll clicks: "))
        
        action = {
            "type": "scroll",
            "direction": direction,
            "clicks": clicks,
            "timestamp": time.time()
        }
        
        # Optional: scroll at specific position
        if input("Scroll at specific position? (y/n): ").lower() == 'y':
            x, y = self.get_coordinates("Scroll position")
            action["x"] = x
            action["y"] = y
        
        self.workflow["actions"].append(action)
        print(f"✅ Added scroll {direction} x{clicks}")
        
    def add_comment(self):
        """Add a comment to explain what's happening."""
        comment = input("\n💬 Comment: ")
        
        action = {
            "type": "comment",
            "text": comment,
            "timestamp": time.time()
        }
        
        self.workflow["actions"].append(action)
        print(f"✅ Added comment: {comment}")
        
    def add_spotlight(self):
        """Add Spotlight opening action (macOS specific)."""
        action = {
            "type": "applescript_spotlight",
            "description": "Open Spotlight using AppleScript",
            "timestamp": time.time()
        }
        
        self.workflow["actions"].append(action)
        print("✅ Added Spotlight open action (will use AppleScript for reliability)")
        
    def show_actions(self):
        """Display all recorded actions."""
        print("\n📜 RECORDED ACTIONS")
        print("=" * 50)
        
        if not self.workflow["actions"]:
            print("No actions recorded yet.")
            return
            
        for i, action in enumerate(self.workflow["actions"], 1):
            if action["type"] == "click":
                print(f"{i}. {action['click_type'].capitalize()}-click at ({action['x']}, {action['y']})")
            elif action["type"] == "type":
                text = action['text'][:30] + '...' if len(action['text']) > 30 else action['text']
                print(f"{i}. Type: '{text}'")
            elif action["type"] == "key":
                print(f"{i}. Press key: {action['key']} x{action['presses']}")
            elif action["type"] == "hotkey":
                print(f"{i}. Hotkey: {'+'.join(action['keys'])}")
            elif action["type"] == "delay":
                reason = f" ({action['reason']})" if action.get('reason') else ""
                print(f"{i}. Delay: {action['seconds']}s{reason}")
            elif action["type"] == "move":
                print(f"{i}. Move to ({action['x']}, {action['y']})")
            elif action["type"] == "scroll":
                pos = f" at ({action['x']}, {action['y']})" if 'x' in action else ""
                print(f"{i}. Scroll {action['direction']} x{action['clicks']}{pos}")
            elif action["type"] == "comment":
                print(f"{i}. Comment: {action['text']}")
                
    def test_playback(self):
        """Test playback of recorded actions."""
        if not self.workflow["actions"]:
            print("❌ No actions to playback.")
            return
            
        print("\n▶️ TESTING PLAYBACK")
        print("Starting in 3 seconds...")
        time.sleep(3)
        
        for i, action in enumerate(self.workflow["actions"], 1):
            print(f"Executing action {i}/{len(self.workflow['actions'])}: {action['type']}")
            
            if action["type"] == "applescript_spotlight":
                import subprocess
                subprocess.run(['osascript', '-e', 'tell application "System Events" to key code 49 using command down'], check=True)
                
            elif action["type"] == "click":
                if action["click_type"] == "single":
                    pyautogui.moveTo(action["x"], action["y"], 
                                   duration=action.get("move_duration", 0.5))
                    pyautogui.click()
                elif action["click_type"] == "double":
                    reliable_double_click(action["x"], action["y"])
                elif action["click_type"] == "right":
                    pyautogui.rightClick(action["x"], action["y"])
                    
            elif action["type"] == "type":
                pyautogui.write(action["text"], interval=action["interval"])
                
            elif action["type"] == "key":
                pyautogui.press(action["key"], presses=action["presses"])
                
            elif action["type"] == "hotkey":
                pyautogui.hotkey(*action["keys"])
                
            elif action["type"] == "delay":
                time.sleep(action["seconds"])
                
            elif action["type"] == "move":
                pyautogui.moveTo(action["x"], action["y"], 
                               duration=action["duration"])
                
            elif action["type"] == "scroll":
                if "x" in action:
                    pyautogui.moveTo(action["x"], action["y"])
                scroll_amount = action["clicks"] if action["direction"] == "up" else -action["clicks"]
                pyautogui.scroll(scroll_amount)
                
            elif action["type"] == "comment":
                print(f"   💬 {action['text']}")
                
            # Small delay between actions
            time.sleep(0.2)
            
        print("✅ Playback complete!")
        
    def save_workflow(self):
        """Save the workflow to a JSON file."""
        filename = input("\n💾 Save as (default: workflow.json): ").strip()
        if not filename:
            filename = "workflow.json"
        if not filename.endswith('.json'):
            filename += '.json'
            
        # Create workflows directory if it doesn't exist
        os.makedirs("workflows", exist_ok=True)
        filepath = os.path.join("workflows", filename)
        
        with open(filepath, 'w') as f:
            json.dump(self.workflow, f, indent=2)
            
        print(f"✅ Saved to: {filepath}")
        print(f"📊 Total actions: {len(self.workflow['actions'])}")
        
        # Generate playback script
        self.generate_playback_script(filename)
        
    def generate_playback_script(self, workflow_file):
        """Generate a standalone playback script."""
        script_name = workflow_file.replace('.json', '_playback.py')
        script_path = os.path.join("workflows", script_name)
        
        script = f'''#!/usr/bin/env python3
"""
Auto-generated playback script for: {workflow_file}
Generated on: {datetime.now().isoformat()}
"""

import json
import time
import sys
import os
import subprocess

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyautogui
from final_double_click_solution import reliable_double_click

def play_workflow():
    """Play the recorded workflow."""
    
    # Load workflow
    workflow_path = os.path.join(os.path.dirname(__file__), "{workflow_file}")
    with open(workflow_path, 'r') as f:
        workflow = json.load(f)
    
    print(f"🎬 Playing: {{workflow['name']}}")
    print(f"📝 {{workflow['description']}}")
    print(f"⏱️  Starting in 3 seconds...")
    time.sleep(3)
    
    actions = workflow["actions"]
    
    for i, action in enumerate(actions, 1):
        print(f"[{{i}}/{{len(actions)}}] {{action['type']}}")
        
        if action["type"] == "applescript_spotlight":
            subprocess.run(['osascript', '-e', 'tell application "System Events" to key code 49 using command down'], check=True)
            
        elif action["type"] == "click":
            if action["click_type"] == "single":
                pyautogui.moveTo(action["x"], action["y"], 
                               duration=action.get("move_duration", 0.5))
                pyautogui.click()
            elif action["click_type"] == "double":
                reliable_double_click(action["x"], action["y"])
            elif action["click_type"] == "right":
                pyautogui.rightClick(action["x"], action["y"])
                
        elif action["type"] == "type":
            pyautogui.write(action["text"], interval=action["interval"])
            
        elif action["type"] == "key":
            pyautogui.press(action["key"], presses=action["presses"])
            
        elif action["type"] == "hotkey":
            pyautogui.hotkey(*action["keys"])
            
        elif action["type"] == "delay":
            reason = f" ({{action.get('reason', '')}})" if action.get('reason') else ""
            print(f"   ⏱️  Waiting {{action['seconds']}}s{{reason}}")
            time.sleep(action["seconds"])
            
        elif action["type"] == "move":
            pyautogui.moveTo(action["x"], action["y"], 
                           duration=action["duration"])
            
        elif action["type"] == "scroll":
            if "x" in action:
                pyautogui.moveTo(action["x"], action["y"])
            scroll_amount = action["clicks"] if action["direction"] == "up" else -action["clicks"]
            pyautogui.scroll(scroll_amount)
            
        elif action["type"] == "comment":
            print(f"   💬 {{action['text']}}")
            
        time.sleep(0.1)  # Small delay between actions
    
    print("✅ Workflow complete!")

if __name__ == "__main__":
    play_workflow()
'''
        
        with open(script_path, 'w') as f:
            f.write(script)
            
        # Make executable
        os.chmod(script_path, 0o755)
        
        print(f"📜 Generated playback script: {script_path}")
        
    def run(self):
        """Run the interactive recorder."""
        self.start_recording()
        
        while self.recording:
            self.show_menu()
            choice = input("\nSelect action (1-15): ").strip()
            
            if choice == "1":
                self.add_click("single")
            elif choice == "2":
                self.add_click("double")
            elif choice == "3":
                self.add_click("right")
            elif choice == "4":
                self.add_type_text()
            elif choice == "5":
                self.add_key_press()
            elif choice == "6":
                self.add_hotkey()
            elif choice == "7":
                self.add_delay()
            elif choice == "8":
                self.add_mouse_move()
            elif choice == "9":
                self.add_scroll()
            elif choice == "10":
                self.add_comment()
            elif choice == "11":
                self.add_spotlight()
            elif choice == "12":
                self.show_actions()
            elif choice == "13":
                self.test_playback()
            elif choice == "14":
                self.save_workflow()
                self.recording = False
                print("\n👋 Recording saved and ended!")
            elif choice == "15":
                if input("Are you sure? (y/n): ").lower() == 'y':
                    self.recording = False
                    print("\n❌ Recording cancelled.")
            else:
                print("❌ Invalid choice. Please try again.")

def main():
    """Main entry point."""
    print("🎬 INTERACTIVE WORKFLOW RECORDER")
    print("=" * 50)
    print("Record your actions and save them to a JSON file for playback.")
    print("Perfect for automating repetitive tasks!")
    
    recorder = WorkflowRecorder()
    recorder.run()

if __name__ == "__main__":
    main()
