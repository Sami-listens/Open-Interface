#!/usr/bin/env python3
"""
Test script for the improved Comsense hybrid agent
Tests the table navigation and cell editing capabilities
"""

import sys
import os
import time

# Add path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comsense_agent_s3_hybrid import AgentS3Hybrid


def test_table_navigation():
    """Test the table navigation capabilities"""
    
    print("\n" + "="*80)
    print("🧪 TESTING IMPROVED COMSENSE HYBRID AGENT")
    print("="*80)
    
    # Initialize agent
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("❌ GEMINI_API_KEY not found")
        return 1
    
    agent = AgentS3Hybrid(api_key)
    print("✅ Agent initialized\n")
    
    print("📋 Test Plan:")
    print("1. Test finding opening references in table")
    print("2. Test field navigation")
    print("3. Test complete edit workflow\n")
    
    print("⚠️ Ensure Comsense is open with Doors module loaded")
    print("⏳ Starting in 3 seconds...\n")
    time.sleep(3)
    
    # Test 1: Find an opening
    print("Test 1: Finding opening 102B")
    coords = agent.find_opening_in_table("102B")
    if coords:
        print(f"✅ Found at {coords}\n")
    else:
        print("⚠️ Not found - will use Ctrl+F fallback\n")
    
    # Test 2: Navigate to a field
    print("Test 2: Field navigation")
    success = agent.navigate_to_field("Exterior")
    if success:
        print("✅ Navigation successful\n")
    else:
        print("⚠️ Navigation failed\n")
    
    # Test 3: Complete edit
    print("Test 3: Complete edit workflow")
    print("Editing 102B - Exterior → Y")
    
    if agent.edit_table_cell("102B", "Exterior", "Y"):
        print("✅ Edit successful!\n")
    else:
        print("⚠️ Edit failed\n")
    
    print("="*80)
    print("🎉 TEST COMPLETE")
    print("="*80)
    print("Check agent_screenshots/ for visual logs")
    print("="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_table_navigation())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
