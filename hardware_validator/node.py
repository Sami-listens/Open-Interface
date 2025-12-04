"""
LangGraph Node wrapper for the Hardware Validation Engine.
Integrates the validator into the main workflow.
"""
import json
from typing import Dict, Any
from hardware_validator.engine import HardwareValidationEngine

# Initialize engine globally or per-node execution if stateless
_ENGINE = HardwareValidationEngine()

def hardware_evaluator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that validates hardware sets found in the state.
    
    Input State Keys:
        - hardware_sets (List[Dict]): The hardware sets extracted from Comsense/Excel.
        
    Output State Keys:
        - validation_reports (List[Dict]): The resulting validation reports.
        - validation_summary (str): A text summary of issues found.
    """
    hw_sets = state.get("hardware_sets", [])
    
    if not hw_sets:
        # Try loading from mock file if no input (for testing/dev)
        # In production this might just return empty
        try:
            with open("hardware_validator/mock_hardware_set.json", "r") as f:
                hw_sets = json.load(f)
        except FileNotFoundError:
             return {
                "validation_reports": [],
                "validation_summary": "No hardware sets provided and no mock data found."
            }

    reports = _ENGINE.validate_batch(hw_sets)
    
    # Serialize reports to dicts
    reports_data = [json.loads(r.json()) for r in reports]
    
    # Create a summary
    total_errors = sum(1 for r in reports for i in r.issues if i.level == "ERROR")
    total_warnings = sum(1 for r in reports for i in r.issues if i.level == "WARNING")
    
    summary = f"Validated {len(reports)} hardware sets. Found {total_errors} Errors, {total_warnings} Warnings."
    
    # Detailed log for the agent chat
    detailed_log = []
    for r in reports:
        if r.issues:
            detailed_log.append(f"Set {r.set_id} (Score: {r.score}):")
            for issue in r.issues:
                detailed_log.append(f"  - [{issue.level}] {issue.message} (Fix: {issue.fix_suggestion})")
    
    if detailed_log:
        summary += "\nDetails:\n" + "\n".join(detailed_log)

    return {
        "validation_reports": reports_data,
        "validation_summary": summary
    }

