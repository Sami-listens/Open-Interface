"""
Excel Parser Node for Harrison Reconciliation Workflow
A LangGraph node that parses Excel files to extract Harrison's edits (yellow/red cells)
"""

import os
import openpyxl
from typing import Dict, Any, List, Optional
from langgraph_interface.state import OpenInterfaceState


class ExcelParserNode:
    """LangGraph node for parsing Excel files with formatting detection"""
    
    # Color definitions
    YELLOW_COLORS = [
        'FFFFFF00', 'FFFF00', 'FFFFE599', 'FFFFD966', 
        'FFFFFF99', 'FFCCCC00',
    ]
    
    RED_COLORS = [
        'FFFF0000', 'FFC00000', 'FFFF6666', 'FFCC0000',
    ]
    
    IGNORE_COLORS = [
        'FF000000', '00000000', 'FFFFFFFF',
    ]
    
    # Column mappings
    DOOR_COLUMNS = [
        'Door Type', 'Door Size', 'Opening Size', 'Height', 'Door Thick',
        'Door Arch Type', 'Door Material', 'Door Mfg Code', 'Door Finish'
    ]
    
    FRAME_COLUMNS = [
        'Frame Type', 'Frame Arch Type', 'Frame Material', 
        'Frame Mfg Code', 'Frame Finish'
    ]
    
    def __init__(self):
        """Initialize the Excel parser node"""
        self.workbook = None
        self.worksheet = None
        self.headers = {}
    
    def __call__(self, state: OpenInterfaceState) -> Dict[str, Any]:
        """
        Execute the Excel parsing node
        
        Expected state inputs:
            - excel_file_path: Path to the Excel file to parse
            - sheet_name: (Optional) Name of the sheet to parse, defaults to "Door Schedule"
        
        State outputs:
            - excel_edits: List of parsed edits
            - excel_parse_status: Status message
            - excel_parse_error: Error message if parsing failed
        """
        
        excel_path = state.get('excel_file_path')
        sheet_name = state.get('sheet_name', 'Door Schedule')
        
        if not excel_path:
            return {
                **state,
                'excel_parse_error': 'No excel_file_path provided in state',
                'excel_edits': [],
                'status_updates': state.get('status_updates', []) + ['❌ Excel parsing failed: No file path']
            }
        
        try:
            # Expand ~ in path
            excel_path = os.path.expanduser(excel_path)
            
            # Load workbook
            status_updates = state.get('status_updates', [])
            status_updates.append(f'📂 Loading Excel file: {excel_path}')
            
            self.workbook = openpyxl.load_workbook(excel_path, data_only=False)
            
            # Select sheet
            if sheet_name in self.workbook.sheetnames:
                self.worksheet = self.workbook[sheet_name]
            else:
                self.worksheet = self.workbook.active
                status_updates.append(f'⚠️  Sheet "{sheet_name}" not found, using: {self.worksheet.title}')
            
            status_updates.append(f'✓ Loaded sheet: {self.worksheet.title}')
            
            # Extract headers
            self._extract_headers()
            status_updates.append(f'✓ Found {len(self.headers)} columns')
            
            # Parse edits
            edits = self._parse_edits()
            status_updates.append(f'✓ Found {len(edits)} edits to process')
            
            # Close workbook
            self.workbook.close()
            
            return {
                **state,
                'excel_edits': edits,
                'excel_parse_status': 'success',
                'excel_parse_error': None,
                'status_updates': status_updates
            }
            
        except Exception as e:
            status_updates = state.get('status_updates', [])
            status_updates.append(f'❌ Excel parsing error: {str(e)}')
            
            return {
                **state,
                'excel_parse_error': str(e),
                'excel_edits': [],
                'excel_parse_status': 'error',
                'status_updates': status_updates
            }
    
    def _extract_headers(self, header_row: int = 1) -> Dict[int, str]:
        """Extract column headers from the specified row"""
        headers = {}
        for col_idx, cell in enumerate(self.worksheet[header_row], start=1):
            if cell.value:
                headers[col_idx] = str(cell.value).strip()
        self.headers = headers
        return headers
    
    def _is_yellow_cell(self, cell) -> bool:
        """Check if cell has yellow background"""
        if not cell.fill:
            return False
        
        try:
            # Check start_color
            if hasattr(cell.fill, 'start_color') and cell.fill.start_color:
                color_rgb = self._get_color_rgb(cell.fill.start_color)
                if color_rgb and self._is_yellow_color(color_rgb):
                    return True
            
            # Check fgColor for PatternFill
            if hasattr(cell.fill, 'fgColor') and cell.fill.fgColor:
                color_rgb = self._get_color_rgb(cell.fill.fgColor)
                if color_rgb and self._is_yellow_color(color_rgb):
                    return True
        except Exception:
            pass
        
        return False
    
    def _is_red_text(self, cell) -> bool:
        """Check if cell has red text"""
        if not cell.font or not cell.font.color:
            return False
        
        try:
            color_rgb = self._get_color_rgb(cell.font.color)
            if not color_rgb:
                return False
            
            # Skip ignored colors
            color_rgb_clean = color_rgb.replace(' ', '')
            if color_rgb_clean in [c.replace(' ', '') for c in self.IGNORE_COLORS]:
                return False
            
            # Check if it's a red color
            if self._is_red_color(color_rgb):
                return True
        except Exception:
            pass
        
        return False
    
    def _get_color_rgb(self, color_obj) -> Optional[str]:
        """Extract RGB string from color object"""
        if hasattr(color_obj, 'rgb'):
            return color_obj.rgb
        elif hasattr(color_obj, 'value'):
            return color_obj.value
        return None
    
    def _is_yellow_color(self, color_rgb: str) -> bool:
        """Check if RGB string represents yellow"""
        if not isinstance(color_rgb, str):
            return False
        
        color_rgb = color_rgb.upper()
        
        # Check explicit yellow colors
        if any(yellow in color_rgb for yellow in self.YELLOW_COLORS):
            return True
        
        # Heuristic: high R and G, low B
        if len(color_rgb) == 8:
            try:
                r = int(color_rgb[2:4], 16)
                g = int(color_rgb[4:6], 16)
                b = int(color_rgb[6:8], 16)
                if r > 200 and g > 200 and b < 100:
                    return True
            except ValueError:
                pass
        
        return False
    
    def _is_red_color(self, color_rgb: str) -> bool:
        """Check if RGB string represents red"""
        if not isinstance(color_rgb, str):
            return False
        
        color_rgb = color_rgb.upper()
        
        # Check explicit red colors
        if any(red in color_rgb for red in self.RED_COLORS):
            return True
        
        # Heuristic: high R, low G and B
        if len(color_rgb) == 8:
            try:
                r = int(color_rgb[2:4], 16)
                g = int(color_rgb[4:6], 16)
                b = int(color_rgb[6:8], 16)
                if r > 200 and g < 100 and b < 100:
                    return True
            except ValueError:
                pass
        
        return False
    
    def _determine_module(self, column_name: str) -> str:
        """Determine if column belongs to door or frame module"""
        if any(col.lower() in column_name.lower() for col in self.DOOR_COLUMNS):
            return 'door'
        elif any(col.lower() in column_name.lower() for col in self.FRAME_COLUMNS):
            return 'frame'
        else:
            if 'door' in column_name.lower():
                return 'door'
            elif 'frame' in column_name.lower():
                return 'frame'
            return 'unknown'
    
    def _parse_edits(self, start_row: int = 2, opening_col: str = 'Opening') -> List[Dict[str, Any]]:
        """
        Parse the worksheet to find all edited cells (yellow or red)
        
        Args:
            start_row: Row number to start parsing (after headers)
            opening_col: Name of the column containing opening numbers
        
        Returns:
            List of edit instructions
        """
        if not self.headers:
            return []
        
        # Find opening and notes column indices
        opening_col_idx = None
        notes_col_idx = None
        remarks_col_idx = None
        for col_idx, header in self.headers.items():
            header_lower = header.lower()
            if opening_col_idx is None and opening_col.lower() in header_lower:
                opening_col_idx = col_idx
            if notes_col_idx is None and 'notes' in header_lower:
                notes_col_idx = col_idx
            if remarks_col_idx is None and 'remarks' in header_lower:
                remarks_col_idx = col_idx
        
        if not opening_col_idx:
            return []
        
        edits = []
        
        # Scan all rows
        for row_idx, row in enumerate(self.worksheet.iter_rows(min_row=start_row), start=start_row):
            # Get opening number for this row
            opening_cell = self.worksheet.cell(row_idx, opening_col_idx)
            opening_number = opening_cell.value
            
            # Skip if no opening number
            if not opening_number:
                continue
            
            opening_number = str(opening_number).strip()
            
            # Capture any notes/remarks for this row
            notes_val = None
            if notes_col_idx:
                cell_val = self.worksheet.cell(row_idx, notes_col_idx).value
                if cell_val is not None and str(cell_val).strip() != '':
                    notes_val = str(cell_val).strip()
            remarks_val = None
            if remarks_col_idx:
                cell_val = self.worksheet.cell(row_idx, remarks_col_idx).value
                if cell_val is not None and str(cell_val).strip() != '':
                    remarks_val = str(cell_val).strip()
            row_notes = None
            if notes_val or remarks_val:
                # Prefer explicit strbucture but keep single field for simplicity
                parts = []
                if remarks_val:
                    parts.append(f"Remarks: {remarks_val}")
                if notes_val:
                    parts.append(f"Notes: {notes_val}")
                row_notes = " | ".join(parts)
            
            # Detect formatting on the Opening cell itself (don't miss red openings)
            opening_is_highlighted = self._is_yellow_cell(opening_cell)
            opening_is_red = self._is_red_text(opening_cell)
            if opening_is_highlighted or opening_is_red:
                edits.append({
                    'opening': opening_number,
                    'module': 'unknown',
                    'field': 'Opening',
                    'new_value': opening_number,
                    'row': row_idx,
                    'col': opening_col_idx,
                    'is_yellow': opening_is_highlighted,
                    'is_red': opening_is_red,
                    'row_notes': row_notes
                })
            
            # Check each cell in the row
            for col_idx, cell in enumerate(row, start=1):
                # Skip opening column itself
                if col_idx == opening_col_idx:
                    continue
                
                # Skip if no header for this column
                if col_idx not in self.headers:
                    continue
                
                # Get column name
                column_name = self.headers[col_idx]
                column_name_lower = column_name.lower()
                
                # IMPORTANT: Skip Notes, Remarks, Comments columns - these are for context only, not for editing
                if any(skip_word in column_name_lower for skip_word in ['note', 'remark', 'comment']):
                    continue
                
                # Skip Notes/Remarks columns that are used for capturing edits
                if col_idx == notes_col_idx or col_idx == remarks_col_idx:
                    continue
                
                # Check if cell is highlighted or has red text
                is_highlighted = self._is_yellow_cell(cell)
                is_red = self._is_red_text(cell)
                
                if is_highlighted or is_red:
                    cell_value = cell.value
                    
                    # Skip empty values
                    if cell_value is None or str(cell_value).strip() == '':
                        continue
                    
                    module = self._determine_module(column_name)
                    
                    edit_info = {
                        'opening': opening_number,
                        'module': module,
                        'field': column_name,
                        'new_value': str(cell_value),
                        'row': row_idx,
                        'col': col_idx,
                        'is_yellow': is_highlighted,
                        'is_red': is_red,
                        'row_notes': row_notes
                    }
                    
                    edits.append(edit_info)
        
        return edits


# Standalone node function for LangGraph integration
def excel_parser_node(state: OpenInterfaceState) -> Dict[str, Any]:
    """
    Standalone Excel parser node for LangGraph
    
    Usage in graph:
        builder.add_node("excel_parser", excel_parser_node)
    """
    parser = ExcelParserNode()
    return parser(state)


# Test function
def test_excel_parser():
    """Test the Excel parser node"""
    import os
    
    # Get the project root directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # Path to sample Excel file
    excel_path = os.path.join(
        project_root,
        'Project Example - THM WWTP',
        '1. Estimates',
        '00-Pricing',
        'THM WWTP - Project Tool - 8C.xlsm'
    )
    
    print(f"Testing Excel Parser Node")
    print(f"=" * 80)
    print(f"File: {excel_path}")
    print()
    
    # Create test state
    test_state = {
        'excel_file_path': excel_path,
        'sheet_name': 'Door Schedule',
        'status_updates': []
    }
    
    # Run the node
    parser = ExcelParserNode()
    result = parser(test_state)
    
    # Print results
    print("Status Updates:")
    for update in result.get('status_updates', []):
        print(f"  {update}")
    print()
    
    if result.get('excel_parse_error'):
        print(f"❌ Error: {result['excel_parse_error']}")
        return
    
    edits = result.get('excel_edits', [])
    print(f"\n{'='*80}")
    print(f"FOUND {len(edits)} EDITS")
    print(f"{'='*80}\n")
    
    # Group by opening
    by_opening = {}
    for edit in edits:
        opening = edit['opening']
        if opening not in by_opening:
            by_opening[opening] = []
        by_opening[opening].append(edit)
    
    for opening, opening_edits in sorted(by_opening.items()):
        print(f"Opening: {opening}")
        for edit in opening_edits:
            marker = "🟡" if edit['is_yellow'] else "🔴"
            print(f"  {marker} [{edit['module'].upper()}] {edit['field']} → {edit['new_value']}")
        print()


if __name__ == "__main__":
    test_excel_parser()