"""
Parser for extracting specific specification sections from Project PDFs.
Focuses on Division 08 sections: 08 11 13, 08 12 16, 08 14 16, 08 71 00.
"""
import re
from typing import Dict, List, Optional
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

class SpecSectionParser:
    TARGET_SECTIONS = {
        "08 11 13": "Hollow Metal Doors and Frames",
        "08 12 16": "Aluminum Frames",
        "08 14 16": "Flush Wood Doors",
        "08 71 00": "Door Hardware"
    }

    # Regex to find section headers like "SECTION 08 11 13" or "081113"
    # Handling variations with spaces/dashes
    SECTION_REGEX = re.compile(r'(?:SECTION\s+)?(08[\s-]?\d{2}[\s-]?\d{2})', re.IGNORECASE)

    def __init__(self, pdf_path: str):
        if not PdfReader:
            raise ImportError("PyPDF2 is required. Please install it.")
        self.pdf_path = pdf_path
        self.reader = PdfReader(pdf_path)
        self.full_text = [] # Cache of (page_num, text)

    def _normalize_section_id(self, raw_id: str) -> str:
        """Converts 081113 or 08-11-13 to 08 11 13"""
        clean = re.sub(r'[^\d]', '', raw_id)
        if len(clean) == 6:
            return f"{clean[0:2]} {clean[2:4]} {clean[4:6]}"
        return raw_id

    def extract_all_sections(self) -> Dict[str, str]:
        """
        Scans the PDF and extracts text for the target sections.
        Returns a dict: { "08 11 13": "full text...", ... }
        """
        extracted = {k: [] for k in self.TARGET_SECTIONS.keys()}
        current_section = None
        
        print(f"Scanning {len(self.reader.pages)} pages in {self.pdf_path}...")

        for i, page in enumerate(self.reader.pages):
            text = page.extract_text()
            if not text:
                continue
            
            # Check for section start ANYWHERE in the page
            # But prefer starts near the top.
            # However, if we are already in a section, we continue unless we see a NEW section.
            
            # Find all section headers in this page
            matches = list(self.SECTION_REGEX.finditer(text))
            
            if matches:
                # If we found headers, determining which one is "dominant" or if it switches
                # usually a page starts with a header if it's a new section.
                # Or it might be a reference in the text.
                # Heuristic: If "SECTION X" is found, it's likely a start.
                
                for match in matches:
                    found_id = self._normalize_section_id(match.group(1))
                    
                    # Is this a SECTION header or just a reference?
                    # "SECTION 08 11 13" is a header. "Refer to 08 11 13" is a reference.
                    # My regex handles (?:SECTION\s+)? so it captures both.
                    # We should prioritize "SECTION 08..." matches.
                    
                    context_start = max(0, match.start() - 10)
                    context_snippet = text[context_start:match.end()].upper()
                    
                    is_header_candidate = "SECTION" in context_snippet or match.start() < 500 # Top of page or explicit "SECTION"
                    
                    if is_header_candidate:
                        if found_id in self.TARGET_SECTIONS:
                            if current_section != found_id:
                                print(f"  -> Found START of {found_id} on page {i+1}")
                                current_section = found_id
                        else:
                            # Found a section NOT in our target list
                            if current_section is not None:
                                # We were capturing, but now we hit a new section we don't care about
                                # print(f"  -> Found START of {found_id} (ignored) on page {i+1} - Stopping capture of {current_section}")
                                current_section = None
            
            if current_section:
                extracted[current_section].append(text)

        # Join pages
        return {k: "\n".join(v) for k, v in extracted.items() if v}

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python spec_parser.py <pdf_path>")
        sys.exit(1)
        
    parser = SpecSectionParser(sys.argv[1])
    sections = parser.extract_all_sections()
    
    for sec_id, text in sections.items():
        print(f"=== {sec_id} ({len(text)} chars) ===")
        print(text[:200] + "...")
        print("="*40 + "\n")

