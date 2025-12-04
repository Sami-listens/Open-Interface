"""
Script to extract Project Specific Rules from the PDF specification.
"""
import os
import json
import sys
from spec_parser import SpecSectionParser
from project_rule_generator import ProjectRuleGenerator

def extract_project_rules(pdf_path: str, output_path: str = "project_rules.json"):
    print(f"Starting extraction from: {pdf_path}")
    
    # 1. Parse PDF Sections
    try:
        parser = SpecSectionParser(pdf_path)
        sections = parser.extract_all_sections()
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return

    if not sections:
        print("No target sections found (081113, 081216, 081416, 087100).")
        return

    print(f"Found {len(sections)} relevant sections.")
    for sec_id, text in sections.items():
        print(f"  - {sec_id}: {len(text)} chars")

    # 2. Generate Rules using Gemini
    print("\nAnalyzing text with Gemini to extract rules...")
    generator = ProjectRuleGenerator()
    rules = generator.generate_rules(sections)
    
    if rules:
        print(f"Successfully extracted {len(rules)} rules.")
        
        # Save to file
        with open(output_path, "w") as f:
            json.dump(rules, f, indent=2)
        print(f"Rules saved to: {output_path}")
        
        # Print preview
        print("\n--- Extracted Rules Preview ---")
        for r in rules[:3]:
            print(f"[{r.get('id')}] {r.get('category')}: {r.get('description')}")
    else:
        print("No rules were extracted.")

if __name__ == "__main__":
    # Default path based on user query
    default_pdf = "../Project Example - THM WWTP/2. ProjDocs/00-BidDocs/00-Specs/THM WWTP Div 01, 08.pdf"
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), default_pdf))
        
    extract_project_rules(pdf_path)

