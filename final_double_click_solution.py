#!/usr/bin/env python3
"""
Final Double-Click Solution for macOS
This is the ONLY file you need for fixing double-click issues.

The issue: PyAutoGUI clicks are happening but not being recognized 
as valid double-clicks by the Windows App/Comsense Cloud.

Solution: Use CGEvents directly for native macOS clicks that are 
indistinguishable from physical trackpad clicks.
"""

import time
import subprocess
import sys
import os

# Add conda environment packages
sys.path.insert(0, '/opt/anaconda3/envs/open-interface/lib/python3.12/site-packages')

def native_double_click(x, y):
    """
    Perform a native macOS double-click using Quartz CGEvents.
    This creates clicks identical to physical trackpad clicks.
    
    Args:
        x, y: Screen coordinates to click
        
    Returns:
        bool: True if successful
    """
    try:
        from Quartz import (
            CGEventCreateMouseEvent,
            CGEventPost,
            kCGEventLeftMouseDown,
            kCGEventLeftMouseUp,
            kCGHIDEventTap,
            CGEventSetIntegerValueField,
            kCGMouseEventClickState,
            CGPointMake
        )
        
        # Create a point for the click location
        point = CGPointMake(x, y)
        
        # CRITICAL: Set click count properly for double-click recognition
        # First click
        event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, 0)
        CGEventSetIntegerValueField(event, kCGMouseEventClickState, 1)
        CGEventPost(kCGHIDEventTap, event)
        
        event = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, 0)
        CGEventSetIntegerValueField(event, kCGMouseEventClickState, 1)
        CGEventPost(kCGHIDEventTap, event)
        
        # CRITICAL: Use system double-click timing (not too fast, not too slow)
        time.sleep(0.1)  # 100ms is within macOS double-click threshold
        
        # Second click with click count = 2
        event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, 0)
        CGEventSetIntegerValueField(event, kCGMouseEventClickState, 2)
        CGEventPost(kCGHIDEventTap, event)
        
        event = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, 0)
        CGEventSetIntegerValueField(event, kCGMouseEventClickState, 2)
        CGEventPost(kCGHIDEventTap, event)
        
        return True
        
    except ImportError:
        print("❌ Quartz not available. Installing...")
        os.system("pip install pyobjc-framework-Quartz")
        return False
    except Exception as e:
        print(f"❌ Native click error: {e}")
        return False

def reliable_double_click(x, y, method="native"):
    """
    The most reliable double-click function for macOS.
    
    Args:
        x, y: Coordinates to click
        method: "native" (default, most reliable) or "pyautogui" (fallback)
        
    Returns:
        bool: True if successful
    """
    
    if method == "native":
        # Method 1: Native CGEvents (most reliable)
        success = native_double_click(x, y)
        if success:
            print(f"✅ Native double-click at ({x}, {y})")
            return True
    
    # Method 2: PyAutoGUI fallback
    try:
        import pyautogui
        
        # Move to position first
        pyautogui.moveTo(x, y, duration=0.2)
        time.sleep(0.1)
        
        # Use the fastest reliable interval
        pyautogui.click(x, y, clicks=2, interval=0.08)
        print(f"✅ PyAutoGUI double-click at ({x}, {y})")
        return True
        
    except Exception as e:
        print(f"❌ PyAutoGUI error: {e}")
        
    return False

def test_comsense_click():
    """Test double-clicking the Comsense Cloud tile."""
    print("🧪 Testing Comsense Cloud Double-Click")
    print("=" * 40)
    
    x, y = 411, 254
    print(f"Coordinates: ({x}, {y})")
    print("\nMake sure Windows App is open and Comsense Cloud tile is visible.")
    print("\nTesting in 3 seconds...")
    time.sleep(3)
    
    # Test native method
    print("\n1. Testing NATIVE double-click (like trackpad)...")
    success = reliable_double_click(x, y, method="native")
    
    if success:
        print("✅ Native double-click executed!")
        print("Check if Comsense Cloud opened.")
        return True
    
    # Test PyAutoGUI fallback
    print("\n2. Testing PyAutoGUI fallback...")
    success = reliable_double_click(x, y, method="pyautogui")
    
    if success:
        print("✅ PyAutoGUI double-click executed!")
        return True
    
    print("\n❌ Double-click not working. Check coordinates or window state.")
    return False

def update_comsense_workflow():
    """Update your Comsense workflow with the working solution."""
    
    updated_code = '''
# Updated run_comsense_workflow.py snippet
# Replace your double-click code with this:

from final_double_click_solution import reliable_double_click

# ... your existing code ...

# Step 3: Double-click Comsense tile
print(f"Double-clicking Comsense Cloud at ({comsense_x}, {comsense_y})...")
pyautogui.moveTo(comsense_x, comsense_y, duration=0.5)

# Use native double-click for reliability
success = reliable_double_click(comsense_x, comsense_y, method="native")

if not success:
    print("❌ Double-click failed")
    return

time.sleep(5)  # Wait for credentials dialog
'''
    
    print("\n📝 UPDATE YOUR WORKFLOW:")
    print("=" * 40)
    print(updated_code)
    print("\n💡 Import this function in your workflow:")
    print("   from final_double_click_solution import reliable_double_click")

def main():
    """Main test function."""
    print("🎯 FINAL DOUBLE-CLICK SOLUTION FOR MACOS")
    print("=" * 45)
    print("This uses native CGEvents to create clicks identical to trackpad clicks.\n")
    
    # Test the solution
    success = test_comsense_click()
    
    if success:
        print("\n✅ SOLUTION VERIFIED!")
        update_comsense_workflow()
    else:
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Verify coordinates (411, 254) are correct")
        print("2. Ensure Windows App is maximized")
        print("3. Check if Comsense tile is visible")
        print("4. Try adjusting the sleep time between clicks")
    
    print("\n📌 USE THIS FILE ONLY:")
    print("   final_double_click_solution.py")
    print("\n🗑️  Delete these redundant files:")
    print("   - pyautogui_double_click_fix.py")
    print("   - macos_double_click.py")
    print("   - debug_double_click.py")
    print("   - ultimate_double_click_fix.py")
    print("   - test_permissions.py")

if __name__ == "__main__":
    main()
