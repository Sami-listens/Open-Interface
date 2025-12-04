"""
Standalone script to build and persist the BM25 index from the Knowledgebase.
Uses Context-Aware Chunking to improve retrieval relevance.
"""
import os
import glob
import pickle
import sys
import re

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from rank_bm25 import BM25Okapi
    from PyPDF2 import PdfReader
except ImportError:
    print("Error: Missing dependencies. Run: pip install rank_bm25 PyPDF2")
    sys.exit(1)

def clean_text(text):
    """Remove excess whitespace and noise."""
    text = re.sub(r'\s+', ' ', text) # Collapse whitespace
    text = re.sub(r'\.{4,}', '', text) # Remove leader dots (TOC)
    return text.strip()

def extract_context_chunks(reader, filename):
    """
    Intelligent chunking strategy:
    1. Page-level Context: Most hardware catalogs are dense; pages often equal sections.
    2. Header Detection: We look for capitalized headers to prepend to subsequent chunks.
    3. Overlap: We provide a sliding window if needed, but page-based with Header Context is best for catalogs.
    
    Strategy:
    - Treat each PAGE as a base unit.
    - If a page starts with a likely continuation, prepend context from previous page's footer? No, risky.
    - Instead: Identify the "Product Series" (e.g. "L Series") from the filename or first few pages and inject that into every chunk.
    """
    chunks = []
    doc_names = []
    
    # Extract Global Context from Filename (e.g. "Schlage_L_Series" -> "Schlage L Series")
    global_context = filename.replace('.pdf', '').replace('_', ' ')
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if not text or len(text.strip()) < 100: continue
        
        clean_content = clean_text(text)
        
        # Smart Chunking: Inject Metadata
        # We prepend the Filename/Series to the text so BM25 matches "Schlage Lock" to this chunk even if the text only says "Mortise Lock"
        augmented_text = f"Source: {global_context} | Page {i+1} | Content: {clean_content}"
        
        # Heuristic: Product Codes
        # Scan for patterns like "L9010", "ND80", "9947" to tag this chunk
        # This helps retrieval when querying specific part numbers
        product_codes = re.findall(r'\b[A-Z]{1,3}\d{3,4}[A-Z]{0,3}\b', clean_content)
        if product_codes:
            augmented_text += f" | Keywords: {' '.join(product_codes[:10])}"

        chunks.append(augmented_text)
        doc_names.append(f"{filename} (Page {i+1})")
        
    return chunks, doc_names

def build_and_save_index(kb_path: str, output_file: str):
    print(f"Scanning Knowledgebase at: {kb_path}")
    
    if not os.path.exists(kb_path):
        print(f"Error: Path not found: {kb_path}")
        return

    documents = []
    doc_names = []
    
    pdf_files = glob.glob(os.path.join(kb_path, "**/*.pdf"), recursive=True)
    print(f"Found {len(pdf_files)} PDF catalogs.")
    
    for pdf_path in pdf_files:
        try:
            print(f"Indexing: {os.path.basename(pdf_path)}...")
            reader = PdfReader(pdf_path)
            filename = os.path.basename(pdf_path)
            
            chunks, names = extract_context_chunks(reader, filename)
            documents.extend(chunks)
            doc_names.extend(names)
            
        except Exception as e:
            print(f"Failed to read {pdf_path}: {e}")

    if not documents:
        print("No valid text found to index.")
        return

    print(f"\nBuilding BM25 Index over {len(documents)} smart chunks...")
    tokenized_corpus = [doc.lower().split() for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    
    index_data = {
        "bm25": bm25,
        "documents": documents,
        "doc_names": doc_names
    }
    
    with open(output_file, "wb") as f:
        pickle.dump(index_data, f)
        
    print(f"Success! Index saved to: {output_file}")
    print(f"Size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    base_kb_path = os.path.abspath(os.path.join(os.getcwd(), "../../Knowledgebase/03 Manufacturer Catalogs - Hardware"))
    if len(sys.argv) > 1:
        base_kb_path = sys.argv[1]
        
    output_path = os.path.join(os.path.dirname(__file__), "knowledge_index.pkl")
    build_and_save_index(base_kb_path, output_path)
