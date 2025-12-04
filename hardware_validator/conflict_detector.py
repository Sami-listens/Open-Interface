"""
LLM-based Conflict Detector for TDC vs Project Rules.
Uses structured output with Pydantic models for reliable, intelligent conflict identification.
"""
import os
import json
import time
import random
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        try:
            load_dotenv(env_path)
        except PermissionError:
            pass
    else:
        try:
            load_dotenv()
        except PermissionError:
            pass
except ImportError:
    pass

# Import Google GenAI
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("Warning: google-genai not installed. LLM conflict detection disabled.")

# Model fallback chain
FALLBACK_MODELS = [
    "gemini-2.5-flash",  # Fast for this task
    "gemini-2.0-flash",  # Stable fallback
]


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class ConflictDetail(BaseModel):
    """A single identified conflict between TDC and Project rules."""
    tdc_rule_id: str = Field(description="ID of the conflicting TDC rule (e.g., 'TDC-A1')")
    project_rule_id: str = Field(description="ID of the conflicting project rule (e.g., 'HMD-01')")
    conflict_category: str = Field(description="Category: 'Frame', 'Hinge', 'Door', 'Fastener', 'Fire Rating', 'Exit Device', 'Lock', 'Closer', 'Exterior', 'Other'")
    severity: str = Field(description="'high' = direct contradiction, 'medium' = project adds constraint, 'low' = minor difference")
    tdc_requirement: str = Field(description="What TDC rule requires (1-2 sentences)")
    project_requirement: str = Field(description="What project rule requires (1-2 sentences)")
    conflict_reason: str = Field(description="Clear explanation of WHY these conflict (2-3 sentences)")
    recommendation: str = Field(description="'project' if project should override, 'tdc' if TDC standard should apply, 'merge' if both can coexist")
    action_needed: str = Field(description="What the estimator should verify or decide")


class ConflictAnalysisResult(BaseModel):
    """Complete conflict analysis result."""
    total_conflicts: int = Field(description="Total number of genuine conflicts found")
    conflicts: List[ConflictDetail] = Field(description="List of identified conflicts")
    compatible_rules: List[str] = Field(description="Project rule IDs that don't conflict with any TDC rule")
    analysis_notes: str = Field(description="Brief summary of the analysis (2-3 sentences)")


# ============================================================================
# LLM-based Conflict Detector
# ============================================================================

class ConflictDetector:
    """
    Uses LLM to intelligently identify actual conflicts between rule sets.
    Returns structured Pydantic models for reliable parsing.
    """
    
    def __init__(self, model_name: str = "gemini-2.5-flash-preview-05-20"):
        self.client = None
        self.model_name = model_name
        self.max_retries = 3
        self.base_delay = 2
        
        if HAS_GENAI:
            api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
            if api_key:
                self.client = genai.Client(api_key=api_key)
            else:
                print("Warning: No API key found for conflict detector")
    
    def detect_conflicts(self, tdc_rules: List[Dict], project_rules: List[Dict]) -> Dict[str, Any]:
        """
        Analyze both rule sets and identify genuine conflicts.
        Returns structured conflict analysis.
        """
        if not self.client:
            print("  ⚠ LLM not available, using fallback conflict detection")
            return self._fallback_detection(tdc_rules, project_rules)
        
        if not project_rules:
            return {
                "total_conflicts": 0,
                "conflicts": [],
                "compatible_rules": [],
                "analysis_notes": "No project-specific rules to analyze."
            }
        
        # Build the prompt
        prompt = self._build_analysis_prompt(tdc_rules, project_rules)
        
        # Try each model with retries
        models_to_try = [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]
        
        for model in models_to_try:
            for attempt in range(self.max_retries):
                try:
                    print(f"  [ConflictDetector] Analyzing with {model}...")
                    
                    response = self.client.models.generate_content(
                        model=model,
                        contents=[
                            types.Content(
                                role="user",
                                parts=[types.Part(text=prompt)]
                            )
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                        )
                    )
                    
                    # Parse response
                    result_text = response.text.strip()
                    if result_text.startswith("```"):
                        result_text = result_text.split("```")[1]
                        if result_text.startswith("json"):
                            result_text = result_text[4:]
                    
                    result = json.loads(result_text)
                    
                    # Validate and enrich the result
                    conflicts = self._enrich_conflicts(result.get("conflicts", []), tdc_rules, project_rules)
                    
                    print(f"  ✓ Found {len(conflicts)} genuine conflicts")
                    
                    return {
                        "total_conflicts": len(conflicts),
                        "conflicts": conflicts,
                        "compatible_rules": result.get("compatible_rules", []),
                        "analysis_notes": result.get("analysis_notes", "Analysis complete.")
                    }
                    
                except Exception as e:
                    error_str = str(e)
                    if any(code in error_str for code in ['503', '429', 'UNAVAILABLE', 'overloaded']):
                        delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                        print(f"  [Retry {attempt + 1}/{self.max_retries}] Waiting {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        print(f"  ✗ Model {model} failed: {e}")
                        break
            
            print(f"  → Trying next model...")
        
        # All models failed - use fallback
        print("  ⚠ All LLM attempts failed, using keyword-based fallback")
        return self._fallback_detection(tdc_rules, project_rules)
    
    def _build_analysis_prompt(self, tdc_rules: List[Dict], project_rules: List[Dict]) -> str:
        """Build the analysis prompt for the LLM."""
        
        # Format TDC rules
        tdc_formatted = []
        for rule in tdc_rules:
            details = rule.get('details', [])
            details_str = "\n    - ".join(details[:5]) if details else "No details"
            tdc_formatted.append(f"""
**{rule.get('id', 'TDC-?')}**: {rule.get('title', 'Unknown')}
  Category: {rule.get('category', 'General')}
  Details:
    - {details_str}
""")
        
        # Format Project rules
        proj_formatted = []
        for rule in project_rules:
            proj_formatted.append(f"""
**{rule.get('id', 'PR-?')}**: {rule.get('description', 'No description')}
  Category: {rule.get('category', 'General')}
  Applies to: {rule.get('match_criteria', 'All')}
  Check: {rule.get('check_logic', 'Verify compliance')}
""")
        
        prompt = f"""You are an expert Architectural Hardware Consultant (AHC) for The Door Company.

Your task is to analyze TDC company-wide rules against project-specific rules and identify GENUINE CONFLICTS.

## IMPORTANT GUIDELINES:
1. A conflict exists ONLY when rules contradict each other or when following both is impossible
2. Project rules that ADD requirements (don't contradict TDC) are NOT conflicts - they're additions
3. If project rule is MORE SPECIFIC than TDC (e.g., "18 gauge" when TDC says "appropriate gauge"), it's a REFINEMENT, not a conflict
4. Only flag conflicts that an estimator MUST resolve before validation

## TDC COMPANY RULES:
{"".join(tdc_formatted)}

## PROJECT-SPECIFIC RULES:
{"".join(proj_formatted)}

## YOUR TASK:
Analyze these rule sets and return a JSON object with this exact structure:

{{
  "total_conflicts": <number of genuine conflicts>,
  "conflicts": [
    {{
      "tdc_rule_id": "TDC-XX",
      "project_rule_id": "PR-XX",
      "conflict_category": "Frame|Hinge|Door|Fastener|Fire Rating|Exit Device|Lock|Closer|Exterior|Other",
      "severity": "high|medium|low",
      "tdc_requirement": "What TDC requires...",
      "project_requirement": "What project requires...",
      "conflict_reason": "Clear explanation of the conflict...",
      "recommendation": "project|tdc|merge",
      "action_needed": "What estimator should decide..."
    }}
  ],
  "compatible_rules": ["PR-01", "PR-05", ...],
  "analysis_notes": "Brief summary..."
}}

BE CONSERVATIVE - only report GENUINE conflicts where rules actually contradict.
Project rules that are MORE STRICT than TDC are usually NOT conflicts.

Return ONLY the JSON object, no additional text.
"""
        return prompt
    
    def _enrich_conflicts(self, conflicts: List[Dict], tdc_rules: List[Dict], project_rules: List[Dict]) -> List[Dict]:
        """Enrich conflict data with full rule details for UI display."""
        
        # Build lookup maps
        tdc_map = {r.get('id'): r for r in tdc_rules}
        proj_map = {r.get('id'): r for r in project_rules}
        
        enriched = []
        for i, conflict in enumerate(conflicts):
            tdc_id = conflict.get('tdc_rule_id', '')
            proj_id = conflict.get('project_rule_id', '')
            
            tdc_rule = tdc_map.get(tdc_id, {})
            proj_rule = proj_map.get(proj_id, {})
            
            enriched.append({
                "id": f"conflict_{i+1}",
                "category": conflict.get('conflict_category', 'Other'),
                "severity": conflict.get('severity', 'medium'),
                "tdc_rule": tdc_rule,
                "project_rule": proj_rule,
                "tdc_requirement": conflict.get('tdc_requirement', ''),
                "project_requirement": conflict.get('project_requirement', ''),
                "reason": conflict.get('conflict_reason', ''),
                "recommendation": conflict.get('recommendation', 'project'),
                "action_needed": conflict.get('action_needed', 'Review and decide'),
                "conflict_type": "genuine_conflict"
            })
        
        return enriched
    
    def _fallback_detection(self, tdc_rules: List[Dict], project_rules: List[Dict]) -> Dict[str, Any]:
        """
        Fallback keyword-based detection when LLM is unavailable.
        Only flags high-confidence potential conflicts.
        """
        conflicts = []
        seen = set()
        
        # High-specificity keywords that indicate same topic
        topic_keywords = {
            "frame": ["frame", "hmf", "jamb", "throat"],
            "hinge": ["hinge", "pivot", "nrp"],
            "door": ["door", "hmd", "gauge"],
            "exterior": ["exterior", "galvanneal", "weather"],
            "fire": ["fire", "rated", "label"],
        }
        
        for pr in project_rules:
            pr_text = f"{pr.get('description', '')} {pr.get('match_criteria', '')}".lower()
            
            best_match = None
            best_topic = None
            
            for tdc in tdc_rules:
                tdc_text = f"{tdc.get('title', '')} {' '.join(tdc.get('details', []))}".lower()
                
                for topic, keywords in topic_keywords.items():
                    pr_matches = sum(1 for kw in keywords if kw in pr_text)
                    tdc_matches = sum(1 for kw in keywords if kw in tdc_text)
                    
                    if pr_matches >= 2 and tdc_matches >= 2:
                        pair_key = (pr.get('id'), tdc.get('id'))
                        if pair_key not in seen:
                            seen.add(pair_key)
                            conflicts.append({
                                "id": f"conflict_{len(conflicts)+1}",
                                "category": topic.title(),
                                "severity": "medium",
                                "tdc_rule": tdc,
                                "project_rule": pr,
                                "tdc_requirement": tdc.get('details', [''])[0] if tdc.get('details') else tdc.get('title', ''),
                                "project_requirement": pr.get('description', ''),
                                "reason": f"Both rules address {topic} specifications. Review to ensure compatibility.",
                                "recommendation": "project",
                                "action_needed": "Verify project requirement doesn't contradict TDC standard",
                                "conflict_type": "potential_overlap"
                            })
                            break
        
        return {
            "total_conflicts": len(conflicts),
            "conflicts": conflicts,
            "compatible_rules": [pr.get('id') for pr in project_rules if pr.get('id') not in [c['project_rule'].get('id') for c in conflicts]],
            "analysis_notes": "Fallback analysis based on keyword matching. Review each conflict manually."
        }


# Singleton instance
_detector_instance = None

def get_conflict_detector() -> ConflictDetector:
    """Get or create the conflict detector singleton."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ConflictDetector()
    return _detector_instance

