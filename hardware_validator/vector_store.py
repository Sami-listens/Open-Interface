"""
Real Vector Store implementation using BM25 for catalog retrieval.
Loads a pre-built index from disk for efficiency.
"""
import os
import pickle
from typing import List

class BM25VectorStoreClient:
    """
    Implements a local BM25 search index over PDF documents.
    """
    
    def __init__(self, index_path: str = None):
        if not index_path:
            index_path = os.path.join(os.path.dirname(__file__), "knowledge_index.pkl")
            
        self.index_path = index_path
        self.documents = []
        self.doc_names = []
        self.bm25 = None
        self._load_index()
        
    def _load_index(self):
        """
        Loads the pickled index.
        """
        if not os.path.exists(self.index_path):
            print(f"Warning: Index file not found at {self.index_path}. Search will be disabled.")
            return
            
        try:
            with open(self.index_path, "rb") as f:
                data = pickle.load(f)
                self.bm25 = data["bm25"]
                self.documents = data["documents"]
                self.doc_names = data.get("doc_names", [])
            print(f"Loaded Knowledge Base: {len(self.documents)} pages indexed.")
        except Exception as e:
            print(f"Failed to load index: {e}")

    def search(self, query: str, limit: int = 3) -> List[str]:
        """
        Performs BM25 search for the query.
        """
        if not self.bm25:
            return []
            
        tokenized_query = query.lower().split()
        # rank_bm25 returns the actual documents (text chunks)
        top_docs = self.bm25.get_top_n(tokenized_query, self.documents, n=limit)
        
        # If we want to return names too, we'd need to implement manual scoring or zipping
        # For now, just returning the text context is fine for the LLM
        return top_docs
