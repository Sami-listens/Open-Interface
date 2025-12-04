"""
Generates project-specific validation rules from specification text using Gemini.
Includes retry logic with exponential backoff and model fallback for resilience.
"""
import os
import json
import re
import time
import random
from typing import Dict, List, Any
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from pathlib import Path
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

# Model fallback chain - try these in order if primary fails
FALLBACK_MODELS = [
    "gemini-2.5-pro",  # Primary
    "gemini-2.5-flash",  # Fast fallback
    "gemini-2.0-flash",  # Stable fallback
]

class ProjectRuleGenerator:
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        if not genai:
            raise ImportError("google-genai is required.")
            
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment")
            
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.max_retries = 3
        self.base_delay = 2  # seconds

    def _call_model_with_retry(self, model_name: str, prompt: str) -> str:
        """
        Call a model with exponential backoff retry logic.
        Returns the response text or raises exception after all retries fail.
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
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
                return response.text.strip()
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # Check if it's a retryable error (503, 429, etc.)
                if any(code in error_str for code in ['503', '429', 'UNAVAILABLE', 'overloaded', 'rate limit']):
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"  [Retry {attempt + 1}/{self.max_retries}] Model {model_name} returned transient error. Waiting {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    # Non-retryable error, raise immediately
                    raise e
        
        # All retries exhausted
        raise last_error

    def generate_rules(self, spec_text: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Takes a dict of {section_id: text} and returns a list of rule objects.
        Includes model fallback and retry logic for resilience.
        """
        
        # Combine text for the prompt, keeping sections distinct
        combined_text = ""
        for sec_id, text in spec_text.items():
            combined_text += f"\n\n=== SECTION {sec_id} ===\n{text[:50000]}..." # Truncate if massive
            
        prompt = f"""
You are an expert Architectural Hardware Consultant (AHC).
Analyze the following project specification sections to extract SPECIFIC HARDWARE VALIDATION RULES.

Your goal is to find "Performance Requirements" and specific constraints that would invalidate a hardware set or door configuration.
Focus on:
1. Material constraints (e.g., "Exterior doors must be HMD", "Aluminum frames require 1.5 inch strikes")
2. Sizing rules (e.g., "Doors > 36 inch require 5 inch hinges")
3. Component requirements (e.g., "Machine screws required for HMF", "Spacers required for through-bolts")
4. Location-specific rules (e.g., "Exterior outswinging doors require NRP hinges")

Do NOT extract generic administrative requirements (e.g., "Submit 3 copies", "Warranty 2 years") unless they directly affect the hardware product selection.

SOURCE TEXT:
{combined_text}

OUTPUT FORMAT:
Return a JSON array of rule objects. Each object should have:
- "id": A short unique code (e.g., "PR-01")
- "category": Rule category (e.g., "Hinges", "Fasteners", "Frame")
- "description": The rule description
- "match_criteria": A short text describing when this rule applies (e.g., "Exterior Doors", "Aluminum Frames")
- "check_logic": A description of what to check for (e.g., "Verify hinge height is 5 inches")

Example JSON:
[
  {{
    "id": "PR-01",
    "category": "Fasteners",
    "description": "Reinforced hollow metal frames require machine screws.",
    "match_criteria": "Hollow Metal Frames",
    "check_logic": "Ensure machine screws are specified, not wood screws."
  }}
]
"""
        
        # Try each model in the fallback chain
        models_to_try = [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]
        
        for model in models_to_try:
            try:
                print(f"Sending spec text to {model} for rule extraction...")
                text_resp = self._call_model_with_retry(model, prompt)
                
                # Clean up if markdown block is present
                if text_resp.startswith("```json"):
                    text_resp = text_resp[7:-3]
                elif text_resp.startswith("```"):
                    text_resp = text_resp[3:-3]
                    
                rules = json.loads(text_resp)
                print(f"  ✓ Successfully extracted {len(rules)} rules using {model}")
                return rules
                
            except Exception as e:
                print(f"  ✗ Model {model} failed: {e}")
                # Continue to next model in fallback chain
                continue
        
        # All models failed
        print("Error: All models in fallback chain failed to generate rules")
        return []

if __name__ == "__main__":
    # Test with dummy data
    generator = ProjectRuleGenerator()
    dummy_specs = {"08 71 00": "Performance Requirements: Provide 5 inch hinges for all doors over 3 feet width."}
    rules = generator.generate_rules(dummy_specs)
    print(json.dumps(rules, indent=2))

