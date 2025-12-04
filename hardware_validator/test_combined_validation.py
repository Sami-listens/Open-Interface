"""
Test script to validate Door Schedule using BOTH:
1. TDC (The Door Company) rules - embedded in ai_evaluator.py
2. Project-Specific rules - extracted from PDF spec sections

This demonstrates the full validation pipeline.
"""
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware_validator.engine import HardwareValidationEngine
from hardware_validator.parser import HardwareExportParser

def load_project_rules(rules_path: str = None) -> list:
    """Load project-specific rules from JSON file."""
    if rules_path is None:
        rules_path = os.path.join(os.path.dirname(__file__), "project_rules.json")
    
    if not os.path.exists(rules_path):
        print(f"⚠ No project rules found at {rules_path}")
        return []
    
    with open(rules_path, 'r') as f:
        rules = json.load(f)
    
    print(f"✓ Loaded {len(rules)} project-specific rules")
    return rules

def run_combined_validation(csv_path: str, project_rules_path: str = None):
    """
    Run validation with both TDC and project-specific rules.
    """
    print("=" * 60)
    print("COMBINED VALIDATION: TDC Rules + Project Rules")
    print("=" * 60)
    
    # 1. Load Project Rules
    project_rules = load_project_rules(project_rules_path)
    
    # 2. Parse Door Schedule - this already returns HardwareSet objects
    print(f"\nParsing door schedule from: {csv_path}")
    hw_set_objects = HardwareExportParser.parse_csv(csv_path)
    print(f"✓ Parsed {len(hw_set_objects)} hardware sets/openings")
    
    if not hw_set_objects:
        print("⚠ No valid hardware sets to validate")
        return
    
    # 3. Run AI Evaluation with project rules
    from hardware_validator.ai_evaluator import DynamicEvaluator
    
    print("\n--- Running Validation ---")
    evaluator = DynamicEvaluator()
    ai_issues = evaluator.evaluate_batch(hw_set_objects, project_rules=project_rules)
    
    # 4. Display Results
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    
    total_issues = 0
    for set_id, issues in ai_issues.items():
        if issues:
            print(f"\n📋 {set_id}:")
            for issue in issues:
                total_issues += 1
                level_icon = "❌" if issue.level == "ERROR" else "⚠️"
                print(f"   {level_icon} [{issue.category}] {issue.message}")
                if issue.fix_suggestion:
                    print(f"      → Fix: {issue.fix_suggestion}")
    
    if total_issues == 0:
        print("\n✅ No issues found! All openings pass validation.")
    else:
        print(f"\n📊 Summary: {total_issues} issues found across {sum(1 for v in ai_issues.values() if v)} openings")
    
    return ai_issues

if __name__ == "__main__":
    # Default to the annotated CSV in hardware_validator
    default_csv = os.path.join(
        os.path.dirname(__file__),
        "TxDMV Camp Hubbard - The Door Company_Door_Schedule_-_New_Office_annotated.csv"
    )
    
    csv_path = sys.argv[1] if len(sys.argv) > 1 else default_csv
    
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)
    
    run_combined_validation(csv_path)

