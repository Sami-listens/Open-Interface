#!/usr/bin/env python3
"""
Agent S3 Comsense Reconciliation - Simple Iterative Approach
Starts from: Comsense open with project loaded
Uses Agent S3 to handle everything from clicking Doors onwards
"""

import sys
import os
import pyautogui
import time
from io import BytesIO

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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


def take_screenshot():
    """Take screenshot and return as bytes"""
    screenshot = pyautogui.screenshot()
    buffered = BytesIO()
    screenshot.save(buffered, format="PNG")
    return buffered.getvalue()


def main():
    print("\n" + "="*80)
    print("AGENT S3 COMSENSE RECONCILIATION")
    print("="*80)
    print("\nStarting Point: Comsense open, project 1200255 loaded")
    print("Agent S3 will handle: Click Doors → Tab → Apply all edits")
    print("\n🚀 Starting in 3 seconds...\n")
    
    time.sleep(3)
    
    # Step 1: Load edits from Excel
    print("📂 Loading edits from Excel...")
    edits = get_excel_edits()
    print(f"✓ Found {len(edits)} edits to apply\n")
    
    if not edits:
        print("❌ No edits found")
        return 1
    
    # Show edits
    print("📝 Edits to apply:")
    for i, edit in enumerate(edits, 1):
        marker = "🟡" if edit['is_yellow'] else "🔴"
        print(f"  {i}. {marker} {edit['opening']}: {edit['field']} → {edit['new_value']}")
    print()
    
    # Step 2: Initialize Agent S3
    print("🤖 Initializing Agent S3 with Gemini 2.5...\n")
    
    try:
        from gui_agents.s3.agents.agent_s import AgentS3
        from gui_agents.s3.agents.grounding import OSWorldACI
        
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            print("❌ GEMINI_API_KEY not found in .env file")
            return 1
        
        engine_params = {
            "engine_type": "gemini",
            "model": "gemini-2.5-pro",
            "api_key": api_key,
        }
        
        engine_params_for_grounding = {
            "engine_type": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": api_key,
            "grounding_width": 1920,
            "grounding_height": 1080,
        }
        
        grounding_agent = OSWorldACI(
            env=None,
            platform="darwin",
            engine_params_for_generation=engine_params,
            engine_params_for_grounding=engine_params_for_grounding,
            width=1920,
            height=1080,
        )
        
        agent = AgentS3(
            engine_params,
            grounding_agent,
            platform="darwin",
            max_trajectory_length=8,
            enable_reflection=True,
        )
        
        print("✓ Agent S3 ready")
        print("  Agent: gemini-2.5-pro (reasoning)")
        print("  Ground: gemini-2.5-flash (coordinates)\n")
        
    except Exception as e:
        print(f"❌ Failed to initialize Agent S3: {e}")
        return 1
    
    # Step 3: Agent S3 Multi-Stage Task
    print("="*80)
    print("STAGE 1: NAVIGATE TO DOORS MODULE")
    print("="*80 + "\n")
    
    # Create comprehensive task for Agent S3
    task_context = f"""You are automating Comsense software for Harrison's reconciliation workflow.

CURRENT STATE:
- Comsense is open
- Project 1200255 is loaded (visible on screen)
- You're looking at the project setup screen

GOAL:
Apply {len(edits)} edits from Excel to the Doors module.

STAGE 1 - Navigate to Doors Module:
1. Look at the left sidebar under "ESTIMATING" or "DETAILING" section
2. Find and click on "Doors" button/menu item
3. Wait 1 second
4. Press Tab key to load door details
5. Verify the Doors table is visible with columns: Opening, Qty, Type, etc.

After Stage 1 completes, you'll apply the edits.

EDITS TO APPLY (from Excel - marked in red):
"""
    
    for i, edit in enumerate(edits, 1):
        task_context += f"\n{i}. Opening '{edit['opening']}': Set '{edit['field']}' to '{edit['new_value']}'"
    
    task_context += "\n\nExecute STAGE 1 now: Navigate to Doors module and load details."
    
    # Take initial screenshot
    obs = {"screenshot": take_screenshot()}
    
    try:
        print("📋 Task sent to Agent S3:")
        print("   → Navigate to Doors module")
        print("   → Press Tab to load details\n")
        
        info, actions = agent.predict(instruction=task_context, observation=obs)
        
        print(f"✓ Agent S3 planned {len(actions)} action(s)\n")
        
        # Execute Stage 1 actions
        for i, action in enumerate(actions, 1):
            print(f"  [{i}/{len(actions)}] Executing action...")
            exec(action)
            time.sleep(0.5)
        
        print("\n✅ STAGE 1 COMPLETE - Doors module should be open\n")
        time.sleep(2)
        
    except Exception as e:
        print(f"❌ Stage 1 failed: {e}")
        return 1
    
    # Step 4: Apply Edits (Stage 2)
    print("="*80)
    print("STAGE 2: APPLY EDITS")
    print("="*80 + "\n")
    
    success_count = 0
    
    for i, edit in enumerate(edits, 1):
        print(f"\n--- Edit {i}/{len(edits)} ---")
        print(f"Opening: {edit['opening']}")
        print(f"Field: {edit['field']} → {edit['new_value']}")
        
        # Take fresh screenshot
        obs = {"screenshot": take_screenshot()}
        
        # Create specific edit instruction
        edit_task = f"""CURRENT STATE ANALYSIS REQUIRED:
Look at the Comsense Doors module screenshot and describe what you see.

Then execute this edit:
- Opening: {edit['opening']}
- Field: {edit['field']}
- New Value: {edit['new_value']}

STEPS:
1. Analyze current screen - are you in the Doors module table view?
2. Find the row where Opening column = "{edit['opening']}"
3. In that row, locate the "{edit['field']}" column
4. Click on the cell at the intersection
5. Select all text (Ctrl+A or Cmd+A)
6. Type: {edit['new_value']}
7. Press Tab to save

CONTEXT:
- This is edit {i} of {len(edits)}
- Marked in {'yellow' if edit['is_yellow'] else 'red'} in Excel
- Previous edits: {i-1} completed

If you encounter any issues (dialog boxes, errors, wrong screen), describe what you see and suggest how to proceed."""
        
        try:
            print("📋 Asking Agent S3 to apply edit...")
            
            info, actions = agent.predict(instruction=edit_task, observation=obs)
            
            print(f"✓ Agent planned {len(actions)} action(s)")
            
            # Execute edit actions
            for j, action in enumerate(actions, 1):
                print(f"    [{j}/{len(actions)}] Executing...")
                exec(action)
                time.sleep(0.3)
            
            print(f"✅ Edit {i} completed\n")
            success_count += 1
            
            # Small delay between edits
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Edit {i} failed: {e}")
            print("   Agent S3 will continue with next edit...\n")
            continue
    
    # Summary
    print("\n" + "="*80)
    print("RECONCILIATION COMPLETE")
    print("="*80)
    print(f"✅ Applied: {success_count}/{len(edits)} edits")
    print(f"❌ Failed: {len(edits) - success_count}/{len(edits)} edits")
    print("="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

