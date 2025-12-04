import sys
import os
import csv

# Force import site-packages
sys.path.append('/opt/anaconda3/envs/door_company/lib/python3.11/site-packages')

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from hardware_validator.node import hardware_evaluator_node
from hardware_validator.parser import HardwareExportParser
from hardware_validator.schema import ValidationReport, ValidationIssue

def run_real_project_validation():
    excel_path = os.path.join(project_root, "Project Example - THM WWTP", "1. Estimates", "00-Pricing", "THM WWTP - Project Tool - 8C.xlsm")
    
    print(f"Target Project File: {excel_path}")
    
    csv_extract_path = os.path.join(os.path.dirname(__file__), "thm_wwtp_door_schedule.csv")
    annotated_path = os.path.join(os.path.dirname(__file__), "thm_wwtp_door_schedule_annotated.csv")
    
    print("Extracting 'Door Schedule' to CSV...")
    try:
        import openpyxl
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        ws = wb['Door Schedule']
        
        with open(csv_extract_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for row in ws.iter_rows(values_only=True):
                clean_row = [str(c) if c is not None else "" for c in row]
                writer.writerow(clean_row)
        print(f"Extracted to: {csv_extract_path}")
        
    except Exception as e:
        print(f"Extraction failed: {e}")
        return

    print("Parsing CSV...")
    # The parser is designed for component rows, but the Door Schedule has OPENING rows.
    # Our parser has logic to handle "opening" rows and infer context.
    hw_sets = HardwareExportParser.parse_csv(csv_extract_path)
    print(f"Parsed {len(hw_sets)} items/sets.")
    
    if not hw_sets:
        print("No valid hardware sets found. Checking CSV content...")
        return

    print("Running Validation Engine...")
    state = {"hardware_sets": hw_sets}
    result = hardware_evaluator_node(state)
    
    reports = []
    for r_data in result["validation_reports"]:
        clean_issues = []
        for i_data in r_data["issues"]:
            clean_issues.append(ValidationIssue(
                level=i_data['level'],
                category=i_data['category'],
                message=i_data['message'],
                component_index=i_data.get('component_index'),
                fix_suggestion=i_data.get('fix_suggestion'),
                source_line=i_data.get('source_line')
            ))
        reports.append(ValidationReport(
            set_id=r_data["set_id"],
            issues=clean_issues,
            score=r_data["score"]
        ))

    HardwareExportParser.write_annotated_csv(csv_extract_path, annotated_path, reports)
    
    print("\n" + "="*80)
    print(f"VALIDATION REPORT: {os.path.basename(excel_path)}")
    print("="*80)
    
    issues_found = False
    for report in reports:
        if report.issues:
            issues_found = True
            print(f"\nOpening: {report.set_id} (Score: {report.score})")
            for issue in report.issues:
                 loc = f"Line {issue.source_line}" if issue.source_line else "General"
                 print(f"  [{issue.level}] {loc}: {issue.message}")
                 print(f"      Fix: {issue.fix_suggestion}")
    
    if not issues_found:
        print("No issues found based on current rules.")
        
    print("\n" + "="*80)
    print(f"Annotated file saved to: {annotated_path}")

if __name__ == "__main__":
    run_real_project_validation()
