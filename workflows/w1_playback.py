#!/usr/bin/env python3
"""
Auto-generated playback script for: w1.json
Generated on: 2025-10-01T18:24:37.644194
"""

import json
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyautogui
from final_double_click_solution import reliable_double_click

def play_workflow():
    """Play the recorded workflow."""
    
    # Load workflow
    workflow_path = os.path.join(os.path.dirname(__file__), "w1.json")
    with open(workflow_path, 'r') as f:
        workflow = json.load(f)
    
    print(f"🎬 Playing: {workflow['name']}")
    print(f"📝 {workflow['description']}")
    print(f"⏱️  Starting in 3 seconds...")
    time.sleep(3)
    
    actions = workflow["actions"]
    
    for i, action in enumerate(actions, 1):
        print(f"[{i}/{len(actions)}] {action['type']}")
        
        if action["type"] == "applescript_spotlight":
            # Use AppleScript to open Spotlight (most reliable on macOS)
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
            reason = f" ({action.get('reason', '')})" if action.get('reason') else ""
            print(f"   ⏱️  Waiting {action['seconds']}s{reason}")
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
            
        time.sleep(0.1)  # Small delay between actions
    
    print("✅ Workflow complete!")

if __name__ == "__main__":
    play_workflow()
