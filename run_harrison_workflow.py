#!/usr/bin/env python3
"""
Production script to run Harrison Reconciliation Workflow
Usage: python run_harrison_workflow.py [project_number]
Example: python run_harrison_workflow.py 1200255
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph_interface.phased_coordinator_node import PhasedCoordinatorNode


def check_excel_file(project_number):
    """Check if Excel file exists for the project"""
    excel_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'Project Example - THM WWTP',
        '1. Estimates',
        '00-Pricing',
        'THM WWTP - Project Tool - 8C.xlsm'
    )
    
    if not os.path.exists(excel_path):
        print("\n⚠️  WARNING: Excel file not found!")
        print(f"   Expected: {excel_path}")
        print("\n   Make sure the Excel file is available locally.")
        print("\nContinue anyway? (y/n): ", end='')
        
        response = input().lower()
        if response != 'y':
            print("\n❌ Cancelled. Please ensure Excel file is available.")
            sys.exit(1)
        
        print("\n⚠️  Continuing without Excel file...")
        print("   Parsing will fail\n")
    else:
        print(f"✓ Excel file found: {os.path.basename(excel_path)}")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Run Harrison Reconciliation Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_harrison_workflow.py 1200255
  python run_harrison_workflow.py --project 1200255 --no-verify
  python run_harrison_workflow.py --help
        """
    )
    
    parser.add_argument(
        'project_number',
        nargs='?',
        default='1200255',
        help='Project number to process (default: 1200255)'
    )
    
    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip phase verification (faster but less safe)'
    )
    
    parser.add_argument(
        '--workflow',
        default='workflows/w1_phased.json',
        help='Workflow file to use (default: workflows/w1_phased.json)'
    )
    
    return parser.parse_args()


def main():
    # Parse arguments
    args = parse_arguments()
    project_number = args.project_number
    verify_phases = not args.no_verify
    workflow_file = args.workflow
    
    print("\n" + "="*80)
    print("HARRISON RECONCILIATION WORKFLOW")
    print("="*80)
    print(f"\n📋 Configuration:")
    print(f"   Project Number: {project_number}")
    print(f"   Workflow File: {workflow_file}")
    print(f"   Phase Verification: {'Enabled' if verify_phases else 'Disabled'}")
    print()
    
    # Check setup
    check_excel_file(project_number)
    
    print("\n🚀 Starting workflow in 3 seconds...")
    print("   Press Ctrl+C to cancel\n")
    
    import time
    time.sleep(3)
    
    # Configure and run
    coordinator = PhasedCoordinatorNode()
    result = coordinator({
        'phased_workflow_file': workflow_file,
        'project_number': project_number,
        'verify_phases': verify_phases,
        'status_updates': []
    })
    
    # Print status updates
    print("\n" + "="*80)
    print("EXECUTION LOG")
    print("="*80 + "\n")
    
    for update in result.get('status_updates', []):
        print(update)
    
    # Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    if result.get('phased_workflow_completed'):
        print("✅ WORKFLOW COMPLETED SUCCESSFULLY")
        
        if result.get('excel_edits'):
            print(f"📝 Total edits found: {len(result['excel_edits'])}")
        
        if result.get('edits_applied'):
            print(f"✅ Edits applied: {len(result.get('edits_applied', []))}")
        
        if result.get('edits_failed'):
            failed = result.get('edits_failed', [])
            print(f"❌ Edits failed: {len(failed)}")
            if failed:
                print("\nFailed edits:")
                for edit in failed[:5]:  # Show first 5
                    print(f"  - {edit.get('opening')}: {edit.get('field')} (Reason: {edit.get('reason')})")
        
        print(f"\n📸 Screenshots saved to: screenshots/")
        print(f"📄 Excel edits saved to: screenshots/excel_edits.json")
        
    else:
        print("❌ WORKFLOW FAILED")
        error = result.get('workflow_error', 'Unknown error')
        print(f"Error: {error}")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Workflow cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

