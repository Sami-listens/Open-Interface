import sys
import os

# Add project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from hardware_validator.node import hardware_evaluator_node
    from hardware_validator.parser import HardwareExportParser
    from hardware_validator.schema import ValidationReport, ValidationIssue
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def run_project_test():
    # 1. Locate File
    base_dir = os.path.join(project_root, "Project Example - THM WWTP/1. Estimates/00-Pricing")
    filename = "THM WWTP - Project Tool - 8C.xlsm"
    file_path = os.path.join(base_dir, filename)
    
    # Output path
    output_filename = filename.replace(".xlsm", "_VALIDATED.xlsx") # Saving as xlsx to avoid macro issues
    output_path = os.path.join(base_dir, output_filename)
    
    print(f"Target Project File: {file_path}")
    if not os.path.exists(file_path):
        print("Error: File not found!")
        return

    # 2. Parse Excel
    # We assume the hardware data is on "Door Schedule" or similar tab? 
    # Or maybe "Hardware Sets"?
    # The transcript mentions "Hardware Sets" being separate. 
    # Let's try to find a relevant sheet or default to active.
    print("Parsing Excel file...")
    # Note: If the file structure is vastly different from the simple CSV, 
    # the parser might need column mapping tweaks.
    # For this test, we'll try the "Door Schedule" sheet as a best guess from previous context.
    hw_sets = HardwareExportParser.parse_excel(file_path, sheet_name="Door Schedule")
    
    if not hw_sets:
        print("No hardware sets found. Trying active sheet...")
        hw_sets = HardwareExportParser.parse_excel(file_path)
    
    print(f"Parsed {len(hw_sets)} hardware sets/groups.")
    
    if not hw_sets:
        print("Parsing returned no data. Check column headers matches keywords (Set ID, Description, etc).")
        return

    # 3. Run Validation
    print("Running Validation...")
    state = {"hardware_sets": hw_sets}
    result = hardware_evaluator_node(state)
    
    # 4. Write Annotation
    # Reconstruct report objects
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
        
    print(f"Writing annotated report to: {output_path}")
    HardwareExportParser.write_annotated_excel(file_path, output_path, reports, sheet_name="Door Schedule") # Or active

    # 5. Console Summary
    print("\n" + "="*80)
    print("PROJECT VALIDATION SUMMARY")
    print("="*80)
    print(result["validation_summary"])
    
    # Print top 3 worst scoring sets
    sorted_reports = sorted(reports, key=lambda r: r.score)
    print("\nTop 3 Sets with Issues:")
    for r in sorted_reports[:3]:
        if r.issues:
            print(f"\nSet {r.set_id} (Score: {r.score})")
            for i in r.issues:
                print(f"  - Line {i.source_line}: {i.message}")

if __name__ == "__main__":
    run_project_test()

