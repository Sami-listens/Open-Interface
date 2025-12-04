"""
Optimized AI Evaluator for Hardware Sets.
Uses a SINGLE LLM call with all rules in context to evaluate all hardware sets at once.
Includes retry logic with exponential backoff and model fallback for resilience.
"""
import sys
import os
import json
import re
import time
import random
from typing import List, Dict, Any
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        try:
            load_dotenv(env_path)
        except PermissionError:
            pass  # Skip if no permission, rely on existing env vars
    else:
        try:
            load_dotenv()
        except PermissionError:
            pass
except ImportError:
    pass

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .schema import HardwareSet, ValidationIssue

# Import Google GenAI directly
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    print("Warning: google-genai not installed. AI features will be disabled.")
    HAS_GENAI = False

# Import memory system for learned corrections
try:
    from .memory_system import get_memory
    HAS_MEMORY = True
except ImportError:
    HAS_MEMORY = False
    print("Warning: Memory system not available. Learned corrections disabled.")

# Model fallback chain - try these in order if primary fails
FALLBACK_MODELS = [
    "gemini-2.5-pro",  # Primary
    "gemini-2.5-flash",  # Fast fallback
    "gemini-2.0-flash",  # Stable fallback
]


# ============================================================================
# TDC HARDWARE VALIDATION RULES (Extracted from TDC Standards.xlsx & TDC Use Cases.xlsx)
# ============================================================================
TDC_HARDWARE_RULES = """
## THE DOOR COMPANY (TDC) - HARDWARE VALIDATION RULES

You are an expert Architectural Hardware Consultant (AHC) for The Door Company.
Your task is to review hardware sets and door schedule data to identify ONLY genuine issues 
that would cause problems in the field. Do NOT flag items that are correct or acceptable.

=== SECTION A: DOOR & FRAME MATERIAL RULES ===

**A1. EXTERIOR OPENING REQUIREMENTS**
- Exterior openings by TDC MUST be HMD (hollow metal door) in HMF (hollow metal frame)
- TDC does NOT do exterior aluminum - flag if aluminum is specified for exterior
- TDC manufacturer partners will NOT warranty wood in exterior condition - flag exterior wood doors
- Exterior doors & frames should be A60 Galvanneal finish
- Exterior HMD MUST have insulated core (polystyrene or polyurethane)
- Outswinging exterior doors REQUIRE NRP (Non-Removable Pin) hinges

**A2. INTERIOR DOOR/FRAME SPECIFICATIONS**
- Interior doors & frames should be cold-rolled steel (CRS)
- Interior HMD should have honeycomb (HC) core
- HMD should be seamless (intermittently welded with bondo fill) UNO
- All rated HMF & HMD should be UL labeled with metal labels
- Schedule all doors 1-3/4" thick UNO

**A3. FRAME JAMB DEPTH RULES (CRITICAL)**
- HMF (Hollow Metal Frame) jamb depth = Wall thickness + 1"
- EXCEPTION: For 4-7/8" wall → Use 5-3/4" jamb depth (add 7/8" not 1")
- If wall size unknown, utilize 5-3/4" jamb depth for HMF
- HM throat = jamb depth - 1"
- Aluminum frame jamb depth = Wall thickness exactly (jamb = throat for ALF)
- Utilize Type II ALF (aluminum frame) UNO
- Frames should be full profile welded UNO

=== SECTION B: WOOD DOOR RULES ===

**B1. WOOD DOOR CORES**
- Non-rated wood doors: 5-ply with particleboard (PC) cores
- Fire-rated wood doors > 45min: REQUIRE mineral core (MC) or agrifiber core
- 45-minute rated wood doors: Can use agrifiber core
- Wood doors with full glass lites: REQUIRE SCLC (solid composite lumber core) or timber-stave core
- Oshkosh SCLC designation: GT5

**B2. WOOD DOOR LITES (VIEW KITS)**
- Hospitals, data centers, institutional environments: Use METAL view kits
- All other spaces: Use wood stop kits

=== SECTION C: HARDWARE SIZING & COMPATIBILITY ===

**C1. HINGE REQUIREMENTS**
- Doors > 36" wide: REQUIRE 5" hinges (heavyweight)
- Standard 4.5" hinges: Only acceptable for doors ≤ 36" wide
- Outswinging exterior doors: REQUIRE NRP (Non-Removable Pin) hinges

**C2. EXIT DEVICE SIZING**
- Exit devices on doors > 36" (3') wide: MUST add 48" or 4' modifier
- Standard exit devices are sized for 36" doors only

**C3. EXIT DEVICE HEIGHT EXTENSIONS**
- Doors exceeding 7'-6" in height with flushbolts or vertical rod exit devices:
  → 8' doors: Add 24" extension rods
  → 9' doors: Add 36" extension rods

**C4. HM PAIRED OPENINGS & EXIT DEVICES**
- HM paired openings CANNOT receive vertical rod exit devices
- Solution: Replace with rim exit devices AND add a mullion

**C5. NARROW STILE ALUMINUM DOORS**
- CANNOT use standard/typical mortise locks
- MUST use Adams Rite or similar narrow stile locks from Adams Rite catalog

**C6. STRIKE REQUIREMENTS FOR ALUMINUM FRAMES**
- ALF requires extended lip strikes: 1-1/2" or greater but less than 1-3/4"

=== SECTION D: ELECTRIFIED HARDWARE & WIRE HARNESS ===

**D1. WIRE HARNESS REQUIREMENTS (CRITICAL)**
- When electric hinge (EH) or electric power transfer (EPT) is scheduled:
  → MUST also have wire harness scheduled
  → Harness length = distance from EH/EPT to latching device + 6"
- TDC uses Molex connectors ONLY (use -CON modifier)
- NO pinned wire harnesses allowed

**D2. POWER SUPPLY REQUIREMENTS**
- All exit devices with latch retraction: REQUIRE power supply
- Von Duprin CHEXIT (CX) function devices REQUIRE power supplies:
  → Single openings: PS902 900-2RS
  → Pairs: PS904 900-2RS

=== SECTION E: SPECIAL CONFIGURATIONS ===

**E1. COORDINATOR ACCESSORIES**
- Each coordinator scheduled: Include filler bar AND two mounting brackets

**E2. CONCEALED CLOSERS WITH WILSON PARTITIONS**
- Wilson Partitions ALF + concealed closer: Use LCN 3130 series concealed closer

**E3. RACO 225 SERIES FRAMES**
- Raco's 225 Series ALF + rim exit device scheduled: Change to MORTISE exit device

**E4. MASONRY WALL ANCHORS**
- HMF at masonry walls: Require Masonry T anchor or Punch & Dimple steel post

=== SECTION F: HARDWARE SUPPLIER MATCHING ===

**F1. SUPPLIER COMPATIBILITY**
- Ceco frames → Pair with Assa Abloy hardware (same parent company)
- Republic frames → Pair with Allegion hardware (same parent company)
- Republic door series: DL series
- Republic frame series: ME series
- Ceco frame series: SU series

=== SECTION G: GENERAL SPECIFICATIONS ===

**G1. CONSTRUCTION CORES**
- Include 7-pin, SFIC, brass construction cores at all latching devices that receive cores UNO

**G2. EXCLUSIONS**
- Exclude all hardware designated by Division 28 (Electronic Safety & Security)

**G3. FIRE RATING**
- Ceco 90-minute rated door label: BU

**G4. AUSTIN PROJECTS**
- Austin, TX wood doors: No added urea formaldehyde (NAUF) cores required

=== WHAT NOT TO FLAG (IMPORTANT - DO NOT REPORT THESE) ===
- Standard configurations that are correct - DO NOT include in output
- Items that are industry-standard and acceptable - DO NOT include in output
- Missing optional items (unless required by opening context)
- Cosmetic preferences
- BYOT (By Others to Take) items - these are excluded from TDC scope
- Openings with no issues - DO NOT include in output at all

=== OUTPUT REQUIREMENTS (CRITICAL) ===

**ONLY OUTPUT ISSUES** - Do NOT include openings that pass validation.
If an opening has NO issues, it should NOT appear in your JSON response.

For EACH opening that HAS A GENUINE ISSUE, provide:
1. **level**: "ERROR" (critical issue) or "WARNING" (attention needed)
2. **category**: The type of issue (e.g., "Hinge Size", "Wire Harness", "Exit Device", etc.)
3. **message**: Clear description of the problem
4. **reason**: WHY this is a problem and what could go wrong in the field
5. **rule_reference**: Which TDC rule it violates (e.g., "C1", "D1", "A1")
6. **fix_suggestion**: Specific, actionable fix

Example of a properly formatted issue:
{
  "Opening_1.1.200": [
    {
      "level": "ERROR",
      "category": "Hinge Size",
      "message": "Door is 48\" wide but has standard 4.5\" hinges specified",
      "reason": "Doors exceeding 36\" width require 5\" heavyweight hinges to properly support the door weight and prevent sagging over time. Using undersized hinges can lead to door binding, premature wear, and security issues.",
      "rule_reference": "C1",
      "fix_suggestion": "Replace with 5\" heavyweight hinges (e.g., McKinney TA2714 5x5)"
    }
  ]
}

REMEMBER: Return an empty object {} if ALL openings pass validation.
"""


class DynamicEvaluator:
    """
    Optimized evaluator that sends ALL hardware sets in a SINGLE call
    with all rules embedded in context.
    """
    
    def __init__(self):
        self.client = None
        self.model_name = None
        
        if HAS_GENAI:
            try:
                api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
                
                if not api_key:
                    raise ValueError("CRITICAL: No API Key found. Set GEMINI_API_KEY in .env")
                
                # Initialize client
                self.client = genai.Client(api_key=api_key)
                
                # Use Gemini 3 Pro Preview as primary (matching test_gemini_api.py)
                self.model_name = os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")
                print(f"✓ AI Evaluator initialized with {self.model_name}")
                
            except Exception as e:
                print(f"⚠ AI Evaluator initialization warning: {e}")
                # Don't raise - allow fallback to rule-based only

    def evaluate_batch(self, hw_sets: List[HardwareSet], chunk_size: int = 25, project_rules: List[Dict] = None) -> Dict[str, List[ValidationIssue]]:
        """
        Evaluates hardware sets in optimized chunks to avoid API limits.
        Returns a dictionary mapping set_id -> list of issues.
        
        For large datasets, splits into chunks of chunk_size openings per API call.
        Only openings with genuine issues will have entries in the output.
        """
        if not self.client or not self.model_name:
            print("  ⚠ AI Evaluator not available, skipping AI validation")
            return {s.set_id: [] for s in hw_sets}
        
        if not hw_sets:
            return {}
        
        all_issues_map = {s.set_id: [] for s in hw_sets}
        
        # Split into chunks if dataset is large
        chunks = [hw_sets[i:i + chunk_size] for i in range(0, len(hw_sets), chunk_size)]
        total_chunks = len(chunks)
        
        if total_chunks > 1:
            print(f"\n[AI Evaluator] Large dataset detected - splitting into {total_chunks} chunks of ~{chunk_size} openings each")
        
        total_issues_found = 0
        
        for chunk_idx, chunk in enumerate(chunks):
            # Build comprehensive data representation for this chunk
            sets_data = []
            for s in chunk:
                ctx = s.opening_context
                comps = [{"qty": c.quantity, "desc": c.description, "cat": c.category, "line": c.source_line} 
                         for c in s.components]
                
                sets_data.append({
                    "id": s.set_id,
                    "context": {
                        "width": ctx.width_inches,
                        "height": ctx.height_inches,
                        "exterior": ctx.is_exterior,
                        "fire_rated": ctx.fire_rated,
                        "is_pair": ctx.is_pair,
                        "leaf_count": ctx.leaf_count
                    },
                    "components": comps
                })
            
            # Create the prompt for this chunk
            prompt = self._build_evaluation_prompt(sets_data, project_rules)
            
            if total_chunks > 1:
                print(f"\n[AI Evaluator] Processing chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} openings)...")
            else:
                print(f"\n[AI Evaluator] Analyzing {len(hw_sets)} openings in single batch...")
            
            chunk_issues = self._call_ai_api(prompt, all_issues_map, chunk)
            total_issues_found += chunk_issues
            
            # Small delay between chunks to avoid rate limiting
            if chunk_idx < total_chunks - 1:
                import time
                time.sleep(1)
        
        print(f"  ✓ AI analysis complete: {total_issues_found} issues found across {sum(1 for v in all_issues_map.values() if v)} openings")
        return all_issues_map

    def _call_ai_api(self, prompt: str, all_issues_map: Dict[str, List[ValidationIssue]], 
                     chunk: List[HardwareSet], retry_count: int = 0, model_index: int = 0) -> int:
        """
        Makes the actual API call with retry logic and model fallback.
        Returns count of issues found in this call.
        """
        issues_found = 0
        max_retries = 3
        base_delay = 2  # seconds
        
        # Build list of models to try
        models_to_try = [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]
        
        for model_idx, model in enumerate(models_to_try):
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=[
                            types.Content(
                                role="user",
                                parts=[types.Part(text=prompt)]
                            )
                        ],
                        config=types.GenerateContentConfig()
                    )
                    
                    result_text = response.text.strip()
                    issues_data = self._parse_json_from_text(result_text)
                    
                    # Process results
                    if isinstance(issues_data, dict):
                        for set_id, issues_list in issues_data.items():
                            if set_id in all_issues_map and issues_list:
                                for issue in issues_list:
                                    # Find the source_line from the matching set
                                    source_line = None
                                    for s in chunk:
                                        if s.set_id == set_id and s.components:
                                            source_line = s.components[0].source_line
                                            break
                                    
                                    # Build comprehensive message with reason
                                    message = issue.get("message", "Unknown Issue")
                                    reason = issue.get("reason", "")
                                    rule_ref = issue.get("rule_reference", "")
                                    
                                    # Combine message with reason for full context
                                    full_message = message
                                    if reason:
                                        full_message = f"{message} | Reason: {reason}"
                                    if rule_ref:
                                        full_message = f"[{rule_ref}] {full_message}"
                                    
                                    all_issues_map[set_id].append(ValidationIssue(
                                        level=issue.get("level", "WARNING"),
                                        category=f"AI: {issue.get('category', 'TDC Validation')}",
                                        message=full_message,
                                        fix_suggestion=issue.get("fix_suggestion"),
                                        source_line=source_line
                                    ))
                                    issues_found += 1
                        
                        if model != self.model_name:
                            print(f"  ✓ Successfully used fallback model: {model}")
                        return issues_found
                    else:
                        print(f"  ⚠ Unexpected response format, no issues extracted")
                        return issues_found
                        
                except Exception as e:
                    error_str = str(e)
                    
                    # Check if it's a retryable error (503, 429, etc.)
                    if any(code in error_str for code in ['503', '429', 'UNAVAILABLE', 'overloaded', 'rate limit']):
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        print(f"  [Retry {attempt + 1}/{max_retries}] Model {model} returned transient error. Waiting {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        # Non-retryable error for this model, try next model
                        print(f"  ✗ Model {model} failed: {e}")
                        break  # Break retry loop, try next model
            
            # If we get here, all retries for this model failed
            if model_idx < len(models_to_try) - 1:
                print(f"  → Falling back to next model...")
        
        # All models and retries exhausted
        print(f"  ✗ All models failed. AI evaluation skipped for this chunk.")
        return issues_found

    def _build_evaluation_prompt(self, sets_data: List[Dict], project_rules: List[Dict] = None) -> str:
        """
        Builds a comprehensive prompt with all rules and all data.
        Includes learned corrections from estimator feedback.
        """
        # Format the hardware sets as readable text
        sets_text = json.dumps(sets_data, indent=2)
        
        # Incorporate Project Specific Rules
        project_rules_text = ""
        if project_rules:
            formatted_rules = []
            for r in project_rules:
                formatted_rules.append(f"**{r.get('id', 'PR')} - {r.get('category', 'Project Rule')}**\n"
                                     f"- Rule: {r.get('description')}\n"
                                     f"- Applies to: {r.get('match_criteria')}\n"
                                     f"- Check: {r.get('check_logic')}")
            
            project_rules_text = "\n\n=== PROJECT SPECIFIC RULES (OVERRIDE TDC RULES IF CONFLICT) ===\n" + "\n".join(formatted_rules)

        # Incorporate learned corrections from memory system
        learned_corrections_text = ""
        if HAS_MEMORY:
            try:
                memory = get_memory()
                learned_corrections_text = memory.get_memories_for_prompt()
                if learned_corrections_text:
                    print(f"  [Memory] Injecting {len(memory.get_relevant_memories())} learned corrections into prompt")
            except Exception as e:
                print(f"  [Memory] Warning: Could not load memories: {e}")

        prompt = f"""{TDC_HARDWARE_RULES}

{project_rules_text}

{learned_corrections_text}

---

## HARDWARE SETS TO EVALUATE:

```json
{sets_text}
```

---

## YOUR TASK:

1. Review EACH opening against the TDC rules above
2. Identify ONLY genuine issues that would cause problems
3. Do NOT flag openings that are correctly configured
4. For each issue found, provide clear reasoning

## OUTPUT FORMAT (JSON):

Return a JSON object where:
- Keys are the opening IDs (e.g., "Opening_2.1.001")
- Values are arrays of issues (empty array if no issues)
- ONLY include openings that have actual issues

Example:
```json
{{
  "Opening_2.1.003": [
    {{
      "level": "ERROR",
      "category": "Electrified Hardware",
      "message": "Electric strike specified but no wire harness (CON-*) found in hardware set",
      "fix_suggestion": "Add CON-6W wire harness for electric strike connection"
    }}
  ],
  "Opening_2.1.015": [
    {{
      "level": "WARNING",
      "category": "Exterior Requirements",
      "message": "Exterior door missing threshold",
      "fix_suggestion": "Add appropriate threshold for exterior application"
    }}
  ]
}}
```

If ALL openings are correctly configured, return an empty object: {{}}

Respond with ONLY the JSON object, no additional text.
"""
        return prompt

    def evaluate(self, hw_set: HardwareSet) -> List[ValidationIssue]:
        """
        Legacy single evaluation (wraps batch).
        """
        return self.evaluate_batch([hw_set]).get(hw_set.set_id, [])
    
    def _parse_json_from_text(self, text: str) -> Any:
        """Extract JSON from LLM text response."""
        # Try to find JSON block in code fence
        code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except:
                pass
        
        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        
        # Try parsing entire text
        try:
            return json.loads(text)
        except:
            return {}
