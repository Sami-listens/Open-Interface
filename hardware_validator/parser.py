"""
Adapter to parse CSV/Text exports from Comsense into HardwareSet schema objects.
Allows the validation engine to run on raw file inputs.
Also handles writing annotated CSVs back to disk.
"""
import csv
import shutil
from typing import List, Dict, Any, Optional
from .schema import HardwareSet, HardwareComponent, ValidationReport

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

class HardwareExportParser:
    """
    Parses CSV/Excel data into structured objects and writes annotated reports.
    """

    @staticmethod
    def parse_csv(file_path: str) -> List[Dict[str, Any]]:
        """
        Parses a CSV file where rows represent hardware components OR door schedule openings.
        Captures line numbers for traceability.
        """
        sets = {}
        
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # Determine Parsing Strategy based on Headers
            headers = [h.lower() for h in reader.fieldnames] if reader.fieldnames else []
            is_door_schedule = 'opening' in headers and 'width' in headers
            
            for row in reader:
                line_number = reader.line_num
                row_lower = {k.lower().strip(): v for k, v in row.items() if k}
                
                if is_door_schedule:
                    # Door Schedule Strategy: Each row is a "Set" (Opening)
                    # We use the Opening number as Set ID
                    opening_id = row_lower.get('opening')
                    if not opening_id: continue
                    
                    set_id = f"Opening_{opening_id}"
                    
                    # Create a "Component" representing the door itself so rules can check it
                    # In a full implementation, we'd look up the associated Hardware Set components
                    # But here we only have the door schedule info.
                    
                    # Initialize Context
                    width_val = row_lower.get('width')
                    height_val = row_lower.get('height')
                    width_in = HardwareExportParser._parse_dim(width_val) if width_val else 36.0
                    height_in = HardwareExportParser._parse_dim(height_val) if height_val else 84.0
                    
                    is_pair = 'pair' in row_lower.get('door type', '').lower() or \
                              '2' in str(row_lower.get('leaf count', '')) or \
                              '(2)' in str(row_lower.get('door size', ''))
                              
                    is_exterior = row_lower.get('exterior', 'N').upper() == 'Y'
                    
                    # Create Set Object using dict initially to avoid Schema validation errors during raw parse
                    hw_set = {
                        "set_id": set_id,
                        "name": f"Opening {opening_id}",
                        "opening_context": {
                            "width_inches": width_in, 
                            "height_inches": height_in,
                            "is_pair": is_pair,
                            "is_exterior": is_exterior,
                            "fire_rated": False # default, explicit column check could be added
                        },
                        "components": []
                    }
                    
                    # Add pseudo-components so rules have something to attach to if needed
                    # Or simply to carry the source_line
                    hw_set["components"].append({
                        "category": "Door",
                        "description": f"Door {opening_id} - {row_lower.get('door type', '')}",
                        "quantity": 1,
                        "source_file": file_path,
                        "source_line": line_number
                    })
                    
                    sets[set_id] = hw_set
                    
                else:
                    # Standard Component List Strategy
                    set_val = row_lower.get('set id') or row_lower.get('heading') or row_lower.get('hw set')
                    if set_val and set_val.strip():
                        current_set_id = set_val.strip()
                        if current_set_id not in sets:
                            sets[current_set_id] = HardwareExportParser._init_set(current_set_id)
                        HardwareExportParser._parse_component_row(row_lower, sets[current_set_id], line_number, file_path)

        # Convert dicts to Schema Objects (HardwareSet)
        # This ensures the Engine receives proper objects
        final_sets = []
        for s in sets.values():
            try:
                # Construct OpeningContext object first
                from .schema import OpeningContext, HardwareSet, HardwareComponent
                ctx = OpeningContext(**s["opening_context"])
                
                comps = []
                for c in s["components"]:
                    comps.append(HardwareComponent(**c))
                    
                final_sets.append(HardwareSet(
                    set_id=s["set_id"],
                    name=s["name"],
                    opening_context=ctx,
                    components=comps
                ))
            except Exception as e:
                print(f"Warning: Failed to convert set {s.get('set_id')} to schema: {e}")
                
        return final_sets

    @staticmethod
    def _init_set(set_id: str):
        return {
            "set_id": set_id,
            "name": f"Hardware Set {set_id}",
            "opening_context": {
                "width_inches": 36.0, 
                "height_inches": 84.0,
                "is_pair": False,
                "is_exterior": False,
                "fire_rated": False
            },
            "components": []
        }

    @staticmethod
    def _parse_component_row(row_lower: Dict, set_obj: Dict, line_number: int, file_path: str):
        desc = row_lower.get('description') or row_lower.get('product')
        if not desc or not desc.strip(): return
        
        qty = 1
        try: qty = int(float(row_lower.get('qty', '1')))
        except: pass
        
        category = row_lower.get('category') or "Hardware"
        # (Same inference logic as before...)
        if category == "Hardware":
            desc_l = desc.lower()
            if "hinge" in desc_l: category = "Hinge"
            elif "lock" in desc_l: category = "Lockset"
            elif "closer" in desc_l: category = "Closer"
            elif "exit" in desc_l: category = "Exit Device"
            elif "seal" in desc_l: category = "Seal"
            elif "harness" in desc_l or "con-" in desc_l: category = "Wire Harness"

        set_obj["components"].append({
            "category": category,
            "description": desc,
            "quantity": qty,
            "short_code": row_lower.get('code'),
            "source_file": file_path,
            "source_line": line_number
        })

    @staticmethod
    def _parse_dim(dim_str: str) -> float:
        """Parses dimensions like 3' - 0\" or 3072 into inches"""
        if not dim_str: return 0.0
        dim_str = str(dim_str).strip()
        try: return float(dim_str)
        except: pass
        
        if len(dim_str) == 4 and dim_str.isdigit():
            # 3072 usually means 3'0" x 7'2"
            # But here we handle single dimension if needed.
            # Heuristic: If passed as Width=3072, it's ambiguous.
            # Assuming format feet/inches
            return int(dim_str[0]) * 12.0 + int(dim_str[1]) * 12.0 
        
        if "'" in dim_str:
            parts = dim_str.split("'")
            try:
                feet = int(parts[0].strip())
            except:
                return 36.0 # fallback
            inches = 0
            if len(parts) > 1:
                inch_part = parts[1].replace('-', '').replace('"', '').strip()
                if inch_part:
                    try: inches = float(eval(inch_part.replace(' ', '+')))
                    except: pass
            return feet * 12.0 + inches
            
        return 36.0

    @staticmethod
    def write_annotated_csv(original_file: str, output_file: str, reports: List[ValidationReport]):
        """
        Reads the original CSV and writes a new one with an added "Validation Notes" column.
        Maps issues by both source_line AND opening ID (set_id) to ensure AI comments are captured.
        """
        issues_by_line = {}
        issues_by_opening = {}
        
        for report in reports:
            # Store issues by opening ID for matching
            opening_id = report.set_id.replace("Opening_", "") if report.set_id.startswith("Opening_") else report.set_id
            if opening_id not in issues_by_opening:
                issues_by_opening[opening_id] = []
            
            for issue in report.issues:
                issue_text = f"[{issue.level}] {issue.category}: {issue.message}"
                if issue.fix_suggestion:
                    issue_text += f" | Fix: {issue.fix_suggestion}"
                
                # Store by source line if available
                if issue.source_line:
                    if issue.source_line not in issues_by_line:
                        issues_by_line[issue.source_line] = []
                    issues_by_line[issue.source_line].append(issue_text)
                
                # Always store by opening ID
                issues_by_opening[opening_id].append(issue_text)
        
        with open(original_file, 'r', encoding='utf-8-sig') as fin, \
             open(output_file, 'w', newline='', encoding='utf-8-sig') as fout:
            
            reader = csv.reader(fin)
            writer = csv.writer(fout)
            
            # Determine opening column index
            opening_col_idx = None
            
            try:
                header = next(reader)
                header_lower = [h.lower().strip() for h in header]
                
                # Find the Opening column
                if 'opening' in header_lower:
                    opening_col_idx = header_lower.index('opening')
                
                header.append("Validation Notes")
                writer.writerow(header)
                
                for row in reader:
                    current_line = reader.line_num
                    notes_list = []
                    
                    # First check by source line
                    if current_line in issues_by_line:
                        notes_list.extend(issues_by_line[current_line])
                    
                    # Then check by opening ID (for AI-generated issues without source_line)
                    if opening_col_idx is not None and opening_col_idx < len(row):
                        opening_id = row[opening_col_idx].strip()
                        if opening_id and opening_id in issues_by_opening:
                            # Add issues that weren't already added via source_line
                            for issue_text in issues_by_opening[opening_id]:
                                if issue_text not in notes_list:
                                    notes_list.append(issue_text)
                    
                    notes = " || ".join(notes_list) if notes_list else ""
                    row.append(notes)
                    writer.writerow(row)
                    
            except StopIteration:
                pass
