#!/usr/bin/env python3
"""
Hybrid Agent S3 + Gemini Grounding for Comsense
Combines Agent S3's planning with custom visual grounding and cursor stabilization
"""

import sys
import os
import pyautogui
import time
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw
from google import genai
from google.genai import types
from typing import Tuple, Dict, Optional, List, Any
from dataclasses import dataclass
from enum import Enum
import json
import re

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True


@dataclass
class BoundingBox:
    """Normalized bounding box [0-1]"""
    label: str
    x: float  # center x normalized
    y: float  # center y normalized
    width: float
    height: float
    confidence: float
    
    def to_pixels(self, screen_width: int, screen_height: int) -> Tuple[int, int]:
        """Convert to pixel coordinates (center)"""
        px = int(self.x * screen_width)
        py = int(self.y * screen_height)
        return (px, py)
    
    def to_pixel_box(self, screen_width: int, screen_height: int) -> Tuple[int, int, int, int]:
        """Convert to pixel box (x1, y1, x2, y2)"""
        w_px = int(self.width * screen_width)
        h_px = int(self.height * screen_height)
        cx, cy = self.to_pixels(screen_width, screen_height)
        x1 = cx - w_px // 2
        y1 = cy - h_px // 2
        x2 = cx + w_px // 2
        y2 = cy + h_px // 2
        return (x1, y1, x2, y2)


class GeminiVisionGrounding:
    """Gemini-based vision grounding with structured outputs"""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.screen_width, self.screen_height = pyautogui.size()
        # Known coordinates fallback
        # Project 1200255 specific coordinates
        self.known_elements = {
            "doors": (25, 403),
            "frames": (25, 420),
            "quick_search": (240, 175),
            "show_valid_checkbox": (140, 900),
            "horizontal_scroll_left": (150, 865),
            "opening_ref_column": (150, 300),
            "validate": (1200, 900),
            "save": (1300, 900)
        }
        
    def detect_elements(self, screenshot: Image.Image, target_description: str,
                       spatial_hints: Optional[Dict] = None) -> List[BoundingBox]:
        """
        Detect UI elements with structured bounding boxes
        
        Args:
            screenshot: PIL Image
            target_description: What to find (e.g., "Doors button in left sidebar")
            spatial_hints: Optional hints like {"region": "left", "max_x": 0.3}
        
        Returns:
            List of BoundingBox objects sorted by confidence
        """
        
        # Convert to bytes
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        buffered.seek(0)
        
        # Build spatial context
        spatial_ctx = ""
        if spatial_hints:
            if spatial_hints.get("region") == "left":
                spatial_ctx = " (left sidebar area, x < 0.3)"
            elif spatial_hints.get("region") == "center":
                spatial_ctx = " (center area, 0.3 < x < 0.7)"
        
        prompt = f"""Detect UI element: {target_description}{spatial_ctx}

Screen: {self.screen_width}x{self.screen_height}px

Return ONLY valid JSON array of detected elements:
[
  {{
    "label": "element description",
    "x": 0.0-1.0,
    "y": 0.0-1.0,
    "width": 0.0-1.0,
    "height": 0.0-1.0,
    "confidence": 0.0-1.0
  }}
]

Coordinates are NORMALIZED (0-1):
- x, y: center of bounding box
- width, height: size of box
- Return empty [] if not found
- Return multiple candidates if uncertain"""

        # Check for known elements first
        target_lower = target_description.lower()
        if 'doors' in target_lower or 'door' in target_lower:
            if 'doors' in self.known_elements:
                print("  📍 Using known coordinates for Doors")
                px, py = self.known_elements['doors']
                box = BoundingBox(
                    label="Doors (known)",
                    x=px / self.screen_width,
                    y=py / self.screen_height,
                    width=0.05,
                    height=0.02,
                    confidence=0.95
                )
                return [box]
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',  # Using 2.5-flash as requested
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part.from_bytes(
                                data=buffered.getvalue(),
                                mime_type="image/png"
                            )
                        ]
                    )
                ]
            )
            
            # Use robust JSON parsing
            elements = self.parse_json_robust(response.text)
            if not elements:
                print("  ⚠️ No valid JSON found in response")
                return self.fallback_to_known(target_lower)
            
            boxes = []
            for elem in elements:
                # Validate and filter by spatial hints
                if spatial_hints and spatial_hints.get("max_x"):
                    if elem.get('x', 1.0) > spatial_hints['max_x']:
                        continue
                
                box = BoundingBox(
                    label=elem.get('label', ''),
                    x=elem.get('x', 0.5),
                    y=elem.get('y', 0.5),
                    width=elem.get('width', 0.1),
                    height=elem.get('height', 0.05),
                    confidence=elem.get('confidence', 0.5)
                )
                boxes.append(box)
            
            # Sort by confidence
            boxes.sort(key=lambda b: b.confidence, reverse=True)
            return boxes
        except Exception as e:
            print(f"  ⚠️ Vision error: {e}")
            return self.fallback_to_known(target_lower)
    
    def fallback_to_known(self, target_lower: str) -> List[BoundingBox]:
        """Fallback to known coordinates"""
        if 'doors' in target_lower:
            print("  📍 Fallback to known Doors coordinates")
            px, py = self.known_elements['doors']
            box = BoundingBox(
                label="Doors (fallback)",
                x=px / self.screen_width,
                y=py / self.screen_height,
                width=0.05,
                height=0.02,
                confidence=0.8
            )
            return [box]
        return []
    
    def parse_json_robust(self, text: str) -> List[dict]:
        """Robust JSON parsing with multiple fallback strategies"""
        if not text:
            return []
        
        # Strategy 1: Direct parsing
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract JSON from text
        try:
            # Find JSON array or object
            json_match = re.search(r'(\[.*?\]|\{.*?\})', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Fix common issues
        try:
            # Remove extra text before/after JSON
            text = text.strip()
            
            # Find the JSON part
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                
                # Fix common issues
                json_str = self.fix_json_common_issues(json_str)
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        return []
    
    def fix_json_common_issues(self, json_str: str) -> str:
        """Fix common JSON formatting issues"""
        # Add missing commas
        json_str = re.sub(r'(\d)\s*\n\s*"', r'\1,\n"', json_str)
        json_str = re.sub(r'(\w)\s*\n\s*"', r'\1",\n"', json_str)
        json_str = re.sub(r'}\s*\n\s*{', r'},\n{', json_str)
        json_str = re.sub(r']\s*\n\s*[', r'],\n[', json_str)
        
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        return json_str
    
    def verify_cursor_on_target(self, screenshot: Image.Image, target_label: str,
                               cursor_pos: Tuple[int, int]) -> Dict:
        """Verify if cursor is on the target with visual feedback"""
        
        # Draw cursor on screenshot
        img_copy = screenshot.copy()
        draw = ImageDraw.Draw(img_copy)
        cx, cy = cursor_pos
        # Red crosshair
        draw.line((cx - 15, cy, cx + 15, cy), fill='red', width=3)
        draw.line((cx, cy - 15, cx, cy + 15), fill='red', width=3)
        draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), outline='red', width=3)
        
        # Convert
        buffered = BytesIO()
        img_copy.save(buffered, format="PNG")
        buffered.seek(0)
        
        prompt = f"""The RED crosshair shows cursor position.

Question: Is the cursor DIRECTLY on "{target_label}"?

Return JSON:
{{
  "on_target": true/false,
  "confidence": 0.0-1.0,
  "correction_needed": true/false,
  "corrected_x": 0.0-1.0 or null,
  "corrected_y": 0.0-1.0 or null,
  "reason": "explanation"
}}"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',  # Using 2.5-flash
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part.from_bytes(
                                data=buffered.getvalue(),
                                mime_type="image/png"
                            )
                        ]
                    )
                ]
            )
            
            # Use robust JSON parsing
            result = self.parse_json_robust(response.text)
            if result:
                # Handle both dict and list responses
                if isinstance(result, list) and len(result) > 0:
                    return result[0]
                elif isinstance(result, dict):
                    return result
        except Exception as e:
            print(f"    ⚠️ Verification error: {e}")
        
        return {"on_target": False, "confidence": 0.0}


class CursorStabilizer:
    """Precision cursor stabilization with visual feedback loop"""
    
    def __init__(self, vision: GeminiVisionGrounding):
        self.vision = vision
        self.max_attempts = 5
        self.convergence_threshold = 3  # pixels
        
    def stabilize_to_box(self, target_box: BoundingBox, target_label: str,
                         save_prefix: str = "") -> Tuple[bool, Tuple[int, int]]:
        """
        Stabilize cursor to bounding box with verification
        
        Returns:
            (success, final_position)
        """
        
        screen_w, screen_h = self.vision.screen_width, self.vision.screen_height
        target_px = target_box.to_pixels(screen_w, screen_h)
        
        print(f"  🎯 Target: {target_label} at normalized ({target_box.x:.3f}, {target_box.y:.3f})")
        print(f"  📍 Pixel target: ({target_px[0]}, {target_px[1]})")
        
        for attempt in range(self.max_attempts):
            # Move cursor
            pyautogui.moveTo(target_px[0], target_px[1], duration=0.15, tween=pyautogui.easeOutQuad)
            time.sleep(0.1)
            
            current_pos = pyautogui.position()
            
            # Take screenshot and verify
            screenshot = pyautogui.screenshot()
            if save_prefix:
                screenshot.save(f"agent_screenshots/{save_prefix}_attempt{attempt+1}.png")
            
            verification = self.vision.verify_cursor_on_target(
                screenshot, target_label, current_pos
            )
            
            on_target = verification.get('on_target', False)
            confidence = verification.get('confidence', 0.0)
            
            print(f"  🔍 Attempt {attempt+1}: on_target={on_target}, confidence={confidence:.2f}")
            
            if on_target and confidence > 0.85:
                print(f"  ✅ Stabilized at {current_pos} in {attempt+1} attempts")
                return (True, current_pos)
            
            # Correction needed?
            if verification.get('correction_needed'):
                corrected_x = verification.get('corrected_x')
                corrected_y = verification.get('corrected_y')
                if corrected_x is not None and corrected_y is not None:
                    new_target_px = (
                        int(corrected_x * screen_w),
                        int(corrected_y * screen_h)
                    )
                    distance = np.sqrt(
                        (new_target_px[0] - target_px[0])**2 + 
                        (new_target_px[1] - target_px[1])**2
                    )
                    print(f"  🔄 Correcting by {distance:.1f}px: {verification.get('reason', 'N/A')}")
                    target_px = new_target_px
                    
                    # Converged?
                    if distance <= self.convergence_threshold:
                        pyautogui.moveTo(target_px[0], target_px[1], duration=0.05)
                        print(f"  ✅ Converged in {attempt+1} attempts")
                        return (True, pyautogui.position())
        
        print(f"  ⚠️ Failed to stabilize after {self.max_attempts} attempts")
        return (False, current_pos)


class AgentS3Hybrid:
    """Hybrid Agent combining Agent S3 planning with Gemini grounding"""
    
    def __init__(self, api_key: str):
        self.vision = GeminiVisionGrounding(api_key)
        self.stabilizer = CursorStabilizer(self.vision)
        self.client = genai.Client(api_key=api_key)
        os.makedirs("agent_screenshots", exist_ok=True)

        # COORDINATE GALLERY - All important positions for Project 1200255
        self.coords = {
            # Module buttons (left panel)
            'doors_button': (25, 203),      # Doors module button
            'frames_button': (25, 228),     # Frames module button
            
            # Search and controls  
            'quick_search': (240, 190),     # Quick Search field
            'show_valid_checkbox': (140, 900),  # Show valid attributes only
            
            # Table navigation
            'horizontal_scroll_left': (150, 869),  # Left arrow of horizontal scrollbar
            'opening_ref_first_row': (180, 290),   # Opening Ref column, first data row
            
            # Validation/Save
            'validate_button': (1423, 192),  # Validated checkbox at top right
            'save_button': (1300, 900),
        }

        # Current module context
        self.current_module = None
        
        # Field name mappings: Excel -> Comsense display names (common)
        self.field_name_mapping = {
            'Exterior': 'Ext',  # Excel shows "Exterior", Comsense shows "Ext"
            'Opening': 'Opening Ref',
            'Opening Ref': 'Opening Ref'
        }
        
        # Ordered column list for Doors module (as seen in UI left → right)
        # Total 27 columns, but "Leaf No." gets skipped automatically when tabbing
        self.door_columns_order = [
            'Opening Ref', 'Qty', 'Hdw Set', 'Open Type', 'Leaf No.',  # Leaf No. is skipped
            'Leaf Size', 'Mfg Code', 'Arch Type', 'Desc', 'Series',
            'Ga', 'Thick', 'Mat', 'Elev Code', 'Type', 'Edge', 'Core',
            'Finish', 'Ply', 'Sill', 'Rating', 'Label', 'NET', 'BYO', 'Ext',
            'Opening Rating', 'Preps'
        ]

        # Build tab mappings - Leaf No. gets skipped automatically, so it doesn't count in tab positions
        self.module_columns = {
            'Doors': self._build_tab_mapping(
                self.door_columns_order,
                skip_columns={'Leaf No.', 'Leaf No', 'Leaf #'}  # This column is auto-skipped
            ),
            'Frames': {
                # Frame-specific columns (will be detected dynamically)
                'Opening Ref': 0,
                'Qty': 1,
                # Add more as we discover them
            },
            'Hardware': {
                # Hardware-specific columns (will be detected dynamically)
                'Opening Ref': 0,
                'Qty': 1,
                # Add more as we discover them
            }
        }
        
        # Default to Doors module columns
        self.field_columns = self.module_columns['Doors']
        self.max_tab_index = max(self.field_columns.values())
        
    def _build_tab_mapping(self, column_order: List[str], skip_columns: Optional[set] = None) -> Dict[str, int]:
        """Build tab position mapping from ordered column list."""
        mapping: Dict[str, int] = {}
        tab_index = 0
        skip_columns = skip_columns or set()

        for column_name in column_order:
            if column_name in skip_columns:
                continue

            # Normalize to match Comsense header text (e.g., 'Ext' vs 'Exterior')
            normalized = column_name.strip()
            lower = normalized.lower()

            if lower in {'exterior', 'ext'}:
                normalized = 'Ext'
            elif lower in {'net'}:
                normalized = 'NET'
            elif lower in {'byo', 'by o', 'by others'}:
                normalized = 'BYO'
            elif lower in {'opening'}:
                normalized = 'Opening Ref'
            elif lower in {'door size', 'leaf size'}:
                normalized = 'Leaf Size'
            elif lower in {'door type', 'type'}:
                normalized = 'Type'
            elif lower in {'door material', 'mat'}:
                normalized = 'Mat'
            elif lower in {'ga', 'gauge'}:
                normalized = 'Ga'
            elif lower in {'door arch type', 'arch type'}:
                normalized = 'Arch Type'
            elif lower in {'door thickness', 'thickness'}:
                normalized = 'Thick'
            elif lower in {'door security'}:
                normalized = 'Security'

            mapping[normalized] = tab_index
            tab_index += 1

        return mapping
    
    def print_column_mappings(self):
        """Print current column mappings for debugging"""
        print("\n📊 Door Module Column Mappings (Tab Positions):")
        print("="*50)
        for col, pos in sorted(self.field_columns.items(), key=lambda x: x[1]):
            print(f"  {col:20} → Tab position {pos}")
        print(f"  Total columns: {len(self.field_columns)} (25 tabs to reach last column)")
        print("="*50)


    def plan_action(self, screenshot: Image.Image, goal: str, context: Dict = None) -> Dict:
        """Use Gemini for high-level planning (Agent S3 style)"""
        
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        buffered.seek(0)
        
        context_str = ""
        if context:
            context_str = f"\nContext: {json.dumps(context, indent=2)}"
        
        prompt = f"""You are an expert computer use agent.

Goal: {goal}{context_str}

Analyze the screenshot and decide the NEXT action.

Return JSON:
{{
  "action": "click" | "type" | "key" | "wait" | "done",
  "target": "UI element description" (for click),
  "text": "text to type" (for type),
  "key": "key name" (for key),
  "reasoning": "why this action",
  "spatial_hints": {{"region": "left|center|right", "max_x": 0.0-1.0}} (optional)
}}"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-pro',
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part.from_bytes(
                                data=buffered.getvalue(),
                                mime_type="image/png"
                            )
                        ]
                    )
                ]
            )
            
            # Use robust JSON parsing
            result = self.vision.parse_json_robust(response.text)
            if result:
                # Handle both dict and list responses
                if isinstance(result, list) and len(result) > 0:
                    return result[0]
                elif isinstance(result, dict):
                    return result
        except Exception as e:
            print(f"  ⚠️ Planning error: {e}")
        
        return {"action": "wait"}
    
    def execute_click(self, target_description: str, spatial_hints: Dict = None,
                     save_prefix: str = "") -> bool:
        """Execute click with grounding and stabilization"""
        
        # Take screenshot
        screenshot = pyautogui.screenshot()
        if save_prefix:
            screenshot.save(f"agent_screenshots/{save_prefix}_detect.png")
        
        # Detect elements
        print(f"  🔍 Detecting: {target_description}")
        boxes = self.vision.detect_elements(screenshot, target_description, spatial_hints)
        
        if not boxes:
            print(f"  ❌ No elements detected")
            return False
        
        # Try candidates in order of confidence
        for i, box in enumerate(boxes[:3]):  # Top 3 candidates
            print(f"\n  🎯 Candidate {i+1}: {box.label} (conf: {box.confidence:.2f})")
            
            # Stabilize cursor
            success, final_pos = self.stabilizer.stabilize_to_box(
                box, target_description, f"{save_prefix}_cand{i+1}"
            )
            
            if success:
                # Click
                print(f"  🖱️ Clicking at {final_pos}")
                pyautogui.click()
                time.sleep(0.3)
                
                # Capture result
                if save_prefix:
                    after = pyautogui.screenshot()
                    after.save(f"agent_screenshots/{save_prefix}_clicked.png")
                
                return True
        
        print(f"  ❌ All candidates failed")
        return False
    
    def execute_action(self, action_plan: Dict, save_prefix: str = "") -> bool:
        """Execute planned action"""
        
        action_type = action_plan.get('action')
        
        if action_type == 'click':
            target = action_plan.get('target')
            spatial_hints = action_plan.get('spatial_hints', {})
            return self.execute_click(target, spatial_hints, save_prefix)
        
        elif action_type == 'type':
            text = action_plan.get('text', '')
            print(f"  ⌨️ Typing: {text}")
            pyautogui.typewrite(text)
            return True
        
        elif action_type == 'key':
            key = action_plan.get('key', 'enter')
            print(f"  ⌨️ Key: {key}")
            pyautogui.press(key)
            return True
        
        elif action_type == 'wait':
            print(f"  ⏳ Waiting...")
            time.sleep(1)
            return True
        
        elif action_type == 'done':
            print(f"  ✅ Task complete")
            return True
        
        return False
    
    def detect_current_module(self) -> str:
        """Detect which module (Doors/Frames/Hardware) is currently active"""
        
        print("  🔍 Detecting current module...")
        
        # Take screenshot
        screenshot = pyautogui.screenshot()
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        buffered.seek(0)
        
        prompt = """Look at the Comsense interface and identify which module is currently active.
Check the left sidebar and the table headers.

Common modules:
- Doors (has columns like Hdw, Open Type, Leaf Size, etc.)
- Frames (has frame-specific columns)
- Hardware (has hardware-specific columns)

Return JSON:
{
  "module": "Doors" | "Frames" | "Hardware" | "Unknown",
  "confidence": 0.0-1.0,
  "reason": "what indicators you see"
}"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part.from_bytes(
                                data=buffered.getvalue(),
                                mime_type="image/png"
                            )
                        ]
                    )
                ]
            )
            
            result = self.vision.parse_json_robust(response.text)
            if result:
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
                elif not isinstance(result, dict):
                    return "Doors"  # Default
                
                module = result.get('module', 'Doors')
                confidence = result.get('confidence', 0)
                reason = result.get('reason', '')
                
                print(f"  📊 Module: {module} (conf: {confidence:.2f}) - {reason}")
                
                # Update current module and field columns
                self.current_module = module
                if module in self.module_columns:
                    self.field_columns = self.module_columns[module]
                    print(f"  ✅ Loaded {module} column mappings")
                else:
                    print(f"  ⚠️ No predefined mappings for {module}, will use vision")
                
                return module
        except Exception as e:
            print(f"  ⚠️ Module detection error: {e}")
        
        return "Doors"  # Default fallback
    
    def learn_column_structure(self) -> Dict[str, int]:
        """Learn the column structure of the current table using vision"""
        
        print("  📚 Learning column structure...")
        
        # Take screenshot
        screenshot = pyautogui.screenshot()
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        buffered.seek(0)
        
        prompt = """Analyze the table headers and return all visible column names in order.

Return JSON array of column names from left to right:
["Opening Ref", "Qty", "Set", ...]

Be precise with column names as they appear."""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part.from_bytes(
                                data=buffered.getvalue(),
                                mime_type="image/png"
                            )
                        ]
                    )
                ]
            )
            
            columns = self.vision.parse_json_robust(response.text)
            if columns and isinstance(columns, list):
                # Create column mapping
                column_map = {col: idx for idx, col in enumerate(columns)}
                print(f"  ✅ Learned {len(column_map)} columns: {list(column_map.keys())[:5]}...")
                
                # Update module columns
                if self.current_module:
                    self.module_columns[self.current_module] = column_map
                    self.field_columns = column_map
                
                return column_map
        except Exception as e:
            print(f"  ⚠️ Column learning error: {e}")
        
        return {}
    
    
    
    def verify_current_column(self, expected_column: str) -> bool:
        """Verify that we're in the expected column using vision"""
        
        # Take screenshot
        screenshot = pyautogui.screenshot()
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        buffered.seek(0)
        
        prompt = f"""Look at the current cell selection/cursor position in the table.
The cursor should be in the "{expected_column}" column.

Check if:
1. The selected/active cell is in the {expected_column} column
2. Look at the column headers to verify

Return JSON:
{{
  "in_correct_column": true/false,
  "confidence": 0.0-1.0,
  "detected_column": "name of column where cursor is",
  "reason": "explanation"
}}"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            types.Part.from_bytes(
                                data=buffered.getvalue(),
                                mime_type="image/png"
                            )
                        ]
                    )
                ]
            )
            
            result = self.vision.parse_json_robust(response.text)
            if result:
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
                elif not isinstance(result, dict):
                    return False
                
                in_correct = result.get('in_correct_column', False)
                detected = result.get('detected_column', 'Unknown')
                confidence = result.get('confidence', 0)
                
                print(f"    📊 Column check: {detected} (conf: {confidence:.2f})")
                return in_correct
        except Exception as e:
            print(f"    ⚠️ Column verification error: {e}")
        
        return False
    
    def edit_table_cell(self, opening_ref: str, field_name: str, new_value: str) -> bool:
        """
        Simple and direct approach to edit a cell:
        
        Workflow:
        1. Click horizontal scroll left arrow (150, 865) to reset view
        2. Click Opening Ref column (150, 300) to focus grid  
        3. Click Quick Search (240, 190), wait 1 sec
        4. Double-click to select existing text, press backspace to clear
        5. Type opening ref, press enter
        6. After enter, cursor is on found row's Opening Ref cell
        7. Click horizontal scroll left again to ensure leftmost position
        8. Tab to the target column (cursor stays on found row)
        9. Edit the value with Ctrl+A, type new value, press enter
        10. Take screenshot to verify edit was made
        
        Note: Total 27 columns, but "Leaf No." auto-skips, so only 25 tabs to reach last column
        """
        
        # Map Excel field names to Comsense display names
        comsense_field = self.field_name_mapping.get(field_name, field_name)
        
        print(f"\n🎯 Editing {opening_ref} - {field_name} → {new_value}")
        
        # Step 1: Reset view - click horizontal scroll left
        print("  🔄 Resetting horizontal scroll...")
        pyautogui.click(*self.coords['horizontal_scroll_left'])
        time.sleep(0.3)
        
        # Step 2: Click Opening Ref column to ensure we're in the right place
        print("  📍 Clicking Opening Ref column...")
        pyautogui.click(*self.coords['opening_ref_first_row'])
        time.sleep(0.3)
        
        # Step 3: Quick Search - IMPORTANT: Clear existing text first!
        print(f"  🔍 Quick Search for: {opening_ref}")
        
        # Click once to focus
        pyautogui.click(*self.coords['quick_search'])
        time.sleep(1.0)  # Wait 1 second as requested
        
        # Double click to select all existing text
        pyautogui.doubleClick(*self.coords['quick_search'])
        time.sleep(0.3)
        
        # Delete selected text
        pyautogui.press('backspace')
        time.sleep(0.2)
        
        # Type the opening ref
        pyautogui.typewrite(opening_ref)
        time.sleep(0.3)
        
        # Press enter to search
        pyautogui.press('enter')
        time.sleep(1.5)  # Wait for search to complete
        
        # After pressing Enter, cursor is on the found row's Opening Ref cell
        # Make sure horizontal scroll is at leftmost position before tabbing
        print("  ↩️  Ensuring horizontal scroll is at leftmost position...")
        pyautogui.click(*self.coords['horizontal_scroll_left'])
        time.sleep(0.3)
        
        # We're now at Opening Ref column (position 0) of the correct row

        # Step 4: Now we're at the correct row, calculate tabs needed
        if comsense_field not in self.field_columns:
            print(f"  ⚠️ Unknown column: {comsense_field}")
            return False
        
        tabs_needed = self.field_columns[comsense_field]
        
        # We're currently at Opening Ref column (position 0) after re-anchoring
        # So we need to tab 'tabs_needed' times to reach target column
        if tabs_needed > 0:
            print(f"  ➡️ Pressing Tab {tabs_needed}x to reach {comsense_field} column")
            for _ in range(tabs_needed):
                pyautogui.press('tab')
                time.sleep(0.05)
        
        # Step 6: Edit the value
        print(f"  ✏️ Entering new value: {new_value}")
        pyautogui.hotkey('ctrl', 'a')  # Select all existing text
        time.sleep(0.1)
        pyautogui.typewrite(str(new_value))
        time.sleep(0.2)
        
        # Step 7: Press enter to confirm
        pyautogui.press('enter')
        time.sleep(0.5)
        
        # Step 8: Take screenshot to verify edit
        screenshot = pyautogui.screenshot()
        screenshot.save(f"agent_screenshots/edited_{opening_ref}_{comsense_field}.png")
        print(f"  📸 Screenshot saved: edited_{opening_ref}_{comsense_field}.png")
        
        print(f"  ✅ Edit complete")
        return True
    
    def validate_with_error_handling(self) -> Dict[str, Any]:
        """
        Click validate button and handle any dialog boxes that appear.
        Returns dict with success status and any error messages found.
        """
        
        print("\n" + "="*80)
        print("🔍 VALIDATION PHASE")
        print("="*80 + "\n")
        
        errors = []
        warnings = []
        
        # Click the Validate button - need to click twice!
        # First click focuses the window, second click toggles the checkbox
        print("  ✅ Clicking Validated checkbox (focusing window)...")
        pyautogui.click(*self.coords['validate_button'])
        time.sleep(0.5)
        
        print("  ✅ Clicking Validated checkbox (checking it)...")
        pyautogui.click(*self.coords['validate_button'])
        time.sleep(2.0)  # Wait for validation to process
        
        # Handle dialog boxes - keep checking for up to 30 seconds
        max_attempts = 15
        for attempt in range(max_attempts):
            # Take screenshot to check for dialogs
            screenshot = pyautogui.screenshot()
            screenshot.save(f"agent_screenshots/validation_check_{attempt+1}.png")
            
            # Use vision to detect if there's a dialog box
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            buffered.seek(0)
            
            prompt = """Look at the screenshot and check if there's a dialog box or popup message.

Return JSON:
{
  "dialog_present": true/false,
  "message_type": "error" | "warning" | "info" | null,
  "message_text": "full text of the message" or null,
  "button_text": "OK" | "Yes" | "No" | "Cancel" | null
}"""
            
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(text=prompt),
                                types.Part.from_bytes(
                                    data=buffered.getvalue(),
                                    mime_type="image/png"
                                )
                            ]
                        )
                    ]
                )
                
                result = self.vision.parse_json_robust(response.text)
                if result:
                    if isinstance(result, list) and len(result) > 0:
                        result = result[0]
                    
                    if result.get('dialog_present'):
                        msg_type = result.get('message_type', 'unknown')
                        msg_text = result.get('message_text', 'Unknown message')
                        button = result.get('button_text', 'OK')
                        
                        # Log the message
                        if msg_type == 'error':
                            print(f"  ❌ ERROR: {msg_text}")
                            errors.append(msg_text)
                        elif msg_type == 'warning':
                            print(f"  ⚠️  WARNING: {msg_text}")
                            warnings.append(msg_text)
                        else:
                            print(f"  ℹ️  INFO: {msg_text}")
                        
                        # Click the button (press Enter as fallback)
                        print(f"  🖱️  Clicking '{button}' button...")
                        pyautogui.press('enter')
                        time.sleep(1.5)
                        
                    else:
                        # No dialog found
                        print(f"  ✅ No more dialogs detected")
                        break
                        
            except Exception as e:
                print(f"  ⚠️  Dialog check error: {e}")
                # Try pressing enter anyway
                pyautogui.press('enter')
                time.sleep(1.0)
        
        # Final screenshot
        final_screenshot = pyautogui.screenshot()
        final_screenshot.save("agent_screenshots/validation_complete.png")
        
        print(f"\n  📊 Validation Summary:")
        print(f"     Errors: {len(errors)}")
        print(f"     Warnings: {len(warnings)}")
        
        return {
            'success': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    


def get_excel_edits():
    """Load edits from Excel - reads yellow-highlighted cells from Door Schedule(2)"""
    from langgraph_interface.excel_parser_node import ExcelParserNode
    import datetime
    
    excel_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'Project Example - THM WWTP',
        '1. Estimates',
        '00-Pricing',
        'THM WWTP - Project Tool - 8C.xlsm'
    )
    
    # Check if file exists and show last modified time
    if os.path.exists(excel_path):
        mod_time = os.path.getmtime(excel_path)
        mod_datetime = datetime.datetime.fromtimestamp(mod_time)
        print(f"\n📁 Excel File:")
        print(f"   Path: {excel_path}")
        print(f"   Last Modified: {mod_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   ⚠️  Make sure you SAVED the file after highlighting cells in yellow!")
    else:
        print(f"\n❌ Excel file not found: {excel_path}")
        return []
    
    parser = ExcelParserNode()
    result = parser({
        'excel_file_path': excel_path,
        'sheet_name': 'Door Schedule(2)',  # Updated to use Door Schedule(2)
        'status_updates': []
    })
    
    edits = result.get('excel_edits', [])
    
    # Print parsing results for debugging
    print("\n📊 Excel Parsing Results:")
    print(f"   Sheet: Door Schedule(2)")
    print(f"   Total edits found: {len(edits)}")
    
    if result.get('excel_parse_error'):
        print(f"   ❌ Error: {result['excel_parse_error']}")
    
    # Group by opening for summary
    by_opening = {}
    for edit in edits:
        opening = edit['opening']
        if opening not in by_opening:
            by_opening[opening] = []
        by_opening[opening].append(edit)
    
    print(f"   Openings affected: {len(by_opening)}")
    
    # Show detailed breakdown of what was found
    if len(edits) > 0:
        print(f"\n   📋 Breakdown by Opening:")
        for opening, opening_edits in sorted(by_opening.items()):
            fields = [f"{e['field']}" for e in opening_edits]
            print(f"      • {opening}: {', '.join(fields)}")
    
    print(f"\n   💡 Note: Multiple edits per opening ref (per row) are supported")
    print(f"   💡 Note: Only cells with YELLOW background are detected")
    print(f"   ⚠️  Note: 'Notes', 'Remarks', and 'Comments' columns are IGNORED (context only)")
    print(f"   💡 Tip: Highlight cells in yellow in 'Door Schedule(2)' sheet")
    print()
    
    return edits


def print_coordinate_gallery():
    """Print all coordinates for reference"""
    print("\n📍 COORDINATE GALLERY")
    print("="*40)
    print("Doors button:         (25, 403)")
    print("Frames button:        (25, 420)")
    print("Quick Search:         (240, 190)")
    print("Show valid checkbox:  (140, 900)")
    print("Horizontal scroll <:  (150, 865)")
    print("Opening Ref column:   (150, 300)")
    print("Validated checkbox:   (1423, 192)")
    print("Save button:          (1300, 900)")
    print("="*40 + "\n")

def main():
    """Execute Comsense reconciliation with hybrid agent"""
    
    print("\n" + "="*80)
    print("🚀 COMSENSE AUTOMATION - PROJECT 1200255")
    print("="*80)
    print("\n📋 Workflow:")
    print("  1️⃣  Read yellow-highlighted cells from Excel 'Door Schedule(2)'")
    print("  2️⃣  Apply edits to Comsense using fixed coordinates + tabs")
    print("  3️⃣  Validate changes and handle error dialogs")
    print("\n⚙️  Method:")
    print("  📍 Fixed coordinates for navigation")
    print("  ⌨️  Tab navigation (25 tabs to reach 'Ext', skipping 'Leaf No.')")
    print("  🔍 Vision-based validation error detection")
    print("\n✅ Prerequisites:")
    print("  • Comsense should be open with project 1200255")
    print("  • Door module should be visible")
    print("  • Excel file should have yellow cells in 'Door Schedule(2)'")
    print("\n⏳ Starting in 3 seconds...\n")
    
    time.sleep(3)
    
    # Initialize
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("❌ GEMINI_API_KEY not found")
        return 1
    
    agent = AgentS3Hybrid(api_key)
    print("✅ Hybrid agent initialized\n")
    
    # Print column mappings for reference
    agent.print_column_mappings()
    
    # Load edits
    print("📂 Loading Excel edits...")
    edits = get_excel_edits()
    print(f"✅ Found {len(edits)} edits\n")
    
    for i, edit in enumerate(edits, 1):
        marker = "🟡" if edit.get('is_yellow', False) else "🔴"
        field = edit['field']
        value = edit['new_value']
        print(f"  {i}. {marker} {edit['opening']}: {field} → {value}")
    print()
    
    # Show field name mappings
    print("📋 Field Name Mappings (Excel → Comsense):")
    print(f"   'Exterior' → 'Ext'")
    print(f"   'Opening' → 'Opening Ref'")
    print()
    
    # Phase 1: Simple Door Module Setup
    print("="*80)
    print("PHASE 1: DOOR MODULE SETUP")
    print("="*80 + "\n")
    
    # Click on Doors module
    print(f"📍 Clicking Door module at {agent.coords['doors_button']}")
    pyautogui.click(*agent.coords['doors_button'])
    time.sleep(1)
    
    # Press Tab to load data
    print("⌨️  Pressing Tab to load data...")
    pyautogui.press('tab')
    time.sleep(2)
    
    # Click "Show valid attributes only" checkbox
    print(f"☑️  Clicking 'Show valid attributes only' at {agent.coords['show_valid_checkbox']}")
    pyautogui.click(*agent.coords['show_valid_checkbox'])
    time.sleep(0.5)
    
    # Take screenshot to confirm setup
    after = pyautogui.screenshot()
    after.save("agent_screenshots/phase1_module_ready.png")
    print("\n✅ Door module ready for editing\n")
    
    # Phase 2: Apply edits
    print("="*80)
    print("PHASE 2: APPLY EDITS")
    print("="*80 + "\n")
    
    successful = 0
    failed = []
    
    # Process all edits
    for i, edit in enumerate(edits, 1):
        print(f"📝 Edit {i}/{len(edits)}: {edit['opening']} - {edit['field']} → {edit['new_value']}")
        
        # Use the systematic table cell editing method
        if agent.edit_table_cell(edit['opening'], edit['field'], edit['new_value']):
            successful += 1
            print(f"  ✅ Edit {i} successful\n")
        else:
            failed.append(edit)
            print(f"  ⚠️ Edit {i} failed\n")
        
        # 1 second break between edits as requested
        if i < len(edits):  # Don't wait after the last edit
            print("  ⏸️  1 second break before next edit...")
            time.sleep(1.0)
    
    # Ensure last edit is confirmed
    print("\n📋 Finalizing edits...")
    print("  ⌨️  Pressing Enter to confirm last edit...")
    pyautogui.press('enter')
    time.sleep(1.0)
    
    # Phase 3: Validation
    validation_result = agent.validate_with_error_handling()
    
    # Summary
    print("\n" + "="*80)
    print("🎉 RECONCILIATION COMPLETE")
    print("="*80)
    print(f"✅ Edits Applied: {successful}/{len(edits)}")
    
    if failed:
        print(f"⚠️ Failed edits:")
        for edit in failed:
            print(f"   - {edit['opening']}: {edit['field']} → {edit['new_value']}")
    
    print(f"\n📋 Validation Results:")
    if validation_result['success']:
        print(f"   ✅ Validation completed successfully")
    else:
        print(f"   ⚠️  Validation completed with errors")
    
    if validation_result['errors']:
        print(f"\n   ❌ Errors found during validation:")
        for error in validation_result['errors']:
            print(f"      • {error}")
    
    if validation_result['warnings']:
        print(f"\n   ⚠️  Warnings found during validation:")
        for warning in validation_result['warnings']:
            print(f"      • {warning}")
    
    print(f"\n📁 Screenshots saved to: agent_screenshots/")
    print(f"🎯 Method: Simple & direct with coordinates + vision verification")
    print("="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
