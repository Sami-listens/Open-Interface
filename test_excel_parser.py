#!/usr/bin/env python3
"""
Test Excel Parser - Verify yellow cell detection from Door Schedule(2)
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph_interface.excel_parser_node import ExcelParserNode


def test_excel_parser():
    """Test parsing Door Schedule(2) for yellow-highlighted cells"""
    
    print("\n" + "="*80)
    print("TESTING EXCEL PARSER - DOOR SCHEDULE(2)")
    print("="*80 + "\n")
    
    # Path to Excel file
    excel_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'Project Example - THM WWTP',
        '1. Estimates',
        '00-Pricing',
        'THM WWTP - Project Tool - 8C.xlsm'
    )
    
    print(f"📁 Excel File: {excel_path}")
    
    # Check if file exists and show last modified time
    if os.path.exists(excel_path):
        import datetime
        mod_time = os.path.getmtime(excel_path)
        mod_datetime = datetime.datetime.fromtimestamp(mod_time)
        print(f"📅 Last Modified: {mod_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"❌ File not found!")
        return
    
    print(f"📊 Sheet: Door Schedule(2)")
    print()
    
    # Parse the Excel file
    parser = ExcelParserNode()
    result = parser({
        'excel_file_path': excel_path,
        'sheet_name': 'Door Schedule(2)',
        'status_updates': []
    })
    
    # Print status updates
    print("📋 Status Updates:")
    for update in result.get('status_updates', []):
        print(f"   {update}")
    print()
    
    # Check for errors
    if result.get('excel_parse_error'):
        print(f"❌ Error: {result['excel_parse_error']}")
        return
    
    # Get edits
    edits = result.get('excel_edits', [])
    
    print("="*80)
    print(f"FOUND {len(edits)} YELLOW-HIGHLIGHTED EDITS")
    print("="*80 + "\n")
    
    if len(edits) == 0:
        print("⚠️  No yellow-highlighted cells found!")
        print("   Please ensure cells are highlighted in yellow in 'Door Schedule(2)' sheet")
        return
    
    # Group by opening
    by_opening = {}
    for edit in edits:
        opening = edit['opening']
        if opening not in by_opening:
            by_opening[opening] = []
        by_opening[opening].append(edit)
    
    print(f"📊 Summary:")
    print(f"   Total edits: {len(edits)}")
    print(f"   Openings affected: {len(by_opening)}")
    print()
    
    # Print detailed edits
    print("📝 Edits by Opening:")
    print("-"*80)
    
    for opening, opening_edits in sorted(by_opening.items()):
        print(f"\n🔹 Opening: {opening}")
        for edit in opening_edits:
            marker = "🟡" if edit.get('is_yellow', False) else "🔴"
            module = edit.get('module', 'unknown').upper()
            field = edit['field']
            value = edit['new_value']
            row = edit.get('row', '?')
            col = edit.get('col', '?')
            
            print(f"   {marker} [{module}] {field} → '{value}' (Row {row}, Col {col})")
    
    print("\n" + "="*80)
    print("✅ PARSING TEST COMPLETE")
    print("="*80 + "\n")
    
    print("💡 Tips:")
    print("   - Yellow background = Edit to be made")
    print("   - Red text = Critical edit")
    print("   - Make sure to highlight cells in 'Door Schedule(2)' sheet")
    print()


if __name__ == "__main__":
    test_excel_parser()

