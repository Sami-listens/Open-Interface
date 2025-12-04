"""
Memory and Learning System for Hardware Validation.
Stores human feedback and corrections to improve future validations.

Similar to the BigBrain memory system - learns from estimator corrections
and recalibrates rules over time.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

class FeedbackType(str, Enum):
    DISMISS = "dismiss"      # AI flagged something that isn't an issue
    CONFIRM = "confirm"      # AI correctly identified an issue
    ADD_ISSUE = "add_issue"  # Human found an issue AI missed
    MODIFY = "modify"        # Human modified AI's suggestion

class MemoryType(str, Enum):
    RULE_CORRECTION = "rule_correction"  # Correct a rule interpretation
    FALSE_POSITIVE = "false_positive"    # AI flagged incorrectly
    MISSED_ISSUE = "missed_issue"        # AI missed something
    CONTEXT_LEARNING = "context_learning" # General context to remember

class ValidationMemory:
    """
    Persistent memory system that learns from human feedback.
    Memories are used to improve future validations.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "validation_memory.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the memory database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main memories table - learned corrections and patterns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                category TEXT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT,
                source_project TEXT,
                source_opening TEXT,
                confidence REAL DEFAULT 1.0,
                usage_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Feedback table - raw feedback from estimators
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                project_id TEXT NOT NULL,
                opening_id TEXT,
                original_issue_id TEXT,
                feedback_type TEXT NOT NULL,
                estimator_comment TEXT,
                original_ai_message TEXT,
                corrected_message TEXT,
                category TEXT,
                is_processed INTEGER DEFAULT 0
            )
        """)
        
        # Index for fast queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_category ON memories(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_active ON memories(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_project ON feedback(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_processed ON feedback(is_processed)")
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Feedback Recording
    # ========================================================================
    
    def record_feedback(self, project_id: str, feedback_type: FeedbackType,
                        opening_id: str = None, original_issue_id: str = None,
                        estimator_comment: str = None, original_ai_message: str = None,
                        corrected_message: str = None, category: str = None) -> str:
        """
        Record feedback from an estimator about a validation result.
        
        Returns the feedback_id.
        """
        import uuid
        feedback_id = str(uuid.uuid4())[:8]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO feedback 
            (feedback_id, timestamp, project_id, opening_id, original_issue_id,
             feedback_type, estimator_comment, original_ai_message, corrected_message, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_id,
            datetime.now().isoformat(),
            project_id,
            opening_id,
            original_issue_id,
            feedback_type.value,
            estimator_comment,
            original_ai_message,
            corrected_message,
            category
        ))
        
        conn.commit()
        conn.close()
        
        # Process feedback to create/update memories
        self._process_feedback(feedback_id)
        
        return feedback_id
    
    def _process_feedback(self, feedback_id: str):
        """
        Process feedback to create or update memories.
        This is the learning mechanism.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM feedback WHERE feedback_id = ?", (feedback_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return
        
        columns = ["id", "feedback_id", "timestamp", "project_id", "opening_id",
                   "original_issue_id", "feedback_type", "estimator_comment",
                   "original_ai_message", "corrected_message", "category", "is_processed"]
        feedback = dict(zip(columns, row))
        
        import uuid
        memory_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        if feedback["feedback_type"] == FeedbackType.DISMISS.value:
            # Create a FALSE_POSITIVE memory
            self._create_memory(
                memory_id=memory_id,
                memory_type=MemoryType.FALSE_POSITIVE,
                category=feedback["category"],
                title=f"False Positive: {feedback['category']}",
                content=f"AI incorrectly flagged: {feedback['original_ai_message']}. "
                        f"Estimator notes: {feedback['estimator_comment']}",
                context=json.dumps({
                    "source_feedback": feedback_id,
                    "original_message": feedback["original_ai_message"]
                }),
                source_project=feedback["project_id"],
                source_opening=feedback["opening_id"]
            )
            
        elif feedback["feedback_type"] == FeedbackType.ADD_ISSUE.value:
            # Create a MISSED_ISSUE memory
            self._create_memory(
                memory_id=memory_id,
                memory_type=MemoryType.MISSED_ISSUE,
                category=feedback["category"],
                title=f"Missed Issue: {feedback['category']}",
                content=f"AI missed this issue: {feedback['corrected_message']}. "
                        f"Estimator notes: {feedback['estimator_comment']}",
                context=json.dumps({
                    "source_feedback": feedback_id
                }),
                source_project=feedback["project_id"],
                source_opening=feedback["opening_id"]
            )
            
        elif feedback["feedback_type"] == FeedbackType.MODIFY.value:
            # Create a RULE_CORRECTION memory
            self._create_memory(
                memory_id=memory_id,
                memory_type=MemoryType.RULE_CORRECTION,
                category=feedback["category"],
                title=f"Rule Correction: {feedback['category']}",
                content=f"Original: {feedback['original_ai_message']}. "
                        f"Corrected to: {feedback['corrected_message']}. "
                        f"Reason: {feedback['estimator_comment']}",
                context=json.dumps({
                    "source_feedback": feedback_id,
                    "original": feedback["original_ai_message"],
                    "corrected": feedback["corrected_message"]
                }),
                source_project=feedback["project_id"],
                source_opening=feedback["opening_id"]
            )
        
        # Mark feedback as processed
        cursor.execute("UPDATE feedback SET is_processed = 1 WHERE feedback_id = ?", (feedback_id,))
        conn.commit()
        conn.close()
    
    def _create_memory(self, memory_id: str, memory_type: MemoryType, category: str,
                       title: str, content: str, context: str = None,
                       source_project: str = None, source_opening: str = None):
        """Create a new memory entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO memories 
            (memory_id, created_at, updated_at, memory_type, category, title, content,
             context, source_project, source_opening)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory_id, now, now, memory_type.value, category, title, content,
            context, source_project, source_opening
        ))
        
        conn.commit()
        conn.close()
        
        print(f"[Memory] Created new {memory_type.value} memory: {title}")
    
    # ========================================================================
    # Memory Retrieval for Validation
    # ========================================================================
    
    def get_relevant_memories(self, category: str = None, limit: int = 20) -> List[Dict]:
        """
        Get memories relevant to a validation run.
        These will be injected into the AI prompt.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute("""
                SELECT * FROM memories 
                WHERE is_active = 1 AND (category = ? OR category IS NULL)
                ORDER BY confidence DESC, usage_count DESC
                LIMIT ?
            """, (category, limit))
        else:
            cursor.execute("""
                SELECT * FROM memories 
                WHERE is_active = 1
                ORDER BY confidence DESC, usage_count DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        columns = ["id", "memory_id", "created_at", "updated_at", "memory_type",
                   "category", "title", "content", "context", "source_project",
                   "source_opening", "confidence", "usage_count", "is_active"]
        
        return [dict(zip(columns, row)) for row in rows]
    
    def get_memories_for_prompt(self) -> str:
        """
        Build a prompt section containing learned memories.
        This is injected into the AI validation prompt.
        """
        memories = self.get_relevant_memories(limit=30)
        
        if not memories:
            return ""
        
        sections = {
            MemoryType.FALSE_POSITIVE.value: [],
            MemoryType.MISSED_ISSUE.value: [],
            MemoryType.RULE_CORRECTION.value: [],
            MemoryType.CONTEXT_LEARNING.value: []
        }
        
        for mem in memories:
            sections[mem["memory_type"]].append(mem)
        
        prompt_parts = ["\n=== LEARNED CORRECTIONS (From Previous Estimator Feedback) ===\n"]
        
        if sections[MemoryType.FALSE_POSITIVE.value]:
            prompt_parts.append("\n**DO NOT FLAG THESE (Previously marked as false positives):**")
            for mem in sections[MemoryType.FALSE_POSITIVE.value][:10]:
                prompt_parts.append(f"- [{mem['category']}] {mem['content']}")
        
        if sections[MemoryType.MISSED_ISSUE.value]:
            prompt_parts.append("\n**WATCH FOR THESE (Issues AI previously missed):**")
            for mem in sections[MemoryType.MISSED_ISSUE.value][:10]:
                prompt_parts.append(f"- [{mem['category']}] {mem['content']}")
        
        if sections[MemoryType.RULE_CORRECTION.value]:
            prompt_parts.append("\n**RULE CORRECTIONS (Apply these interpretations):**")
            for mem in sections[MemoryType.RULE_CORRECTION.value][:10]:
                prompt_parts.append(f"- [{mem['category']}] {mem['content']}")
        
        return "\n".join(prompt_parts)
    
    def increment_usage(self, memory_id: str):
        """Track when a memory is used in validation."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE memories 
            SET usage_count = usage_count + 1, updated_at = ?
            WHERE memory_id = ?
        """, (datetime.now().isoformat(), memory_id))
        conn.commit()
        conn.close()
    
    def deactivate_memory(self, memory_id: str):
        """Deactivate a memory (soft delete)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE memories SET is_active = 0 WHERE memory_id = ?", (memory_id,))
        conn.commit()
        conn.close()
    
    def get_all_memories(self, include_inactive: bool = False) -> List[Dict]:
        """Get all memories for management UI."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if include_inactive:
            cursor.execute("SELECT * FROM memories ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT * FROM memories WHERE is_active = 1 ORDER BY created_at DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        columns = ["id", "memory_id", "created_at", "updated_at", "memory_type",
                   "category", "title", "content", "context", "source_project",
                   "source_opening", "confidence", "usage_count", "is_active"]
        
        return [dict(zip(columns, row)) for row in rows]
    
    def get_feedback_history(self, project_id: str = None, limit: int = 50) -> List[Dict]:
        """Get feedback history for review."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT * FROM feedback 
                WHERE project_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (project_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM feedback 
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        columns = ["id", "feedback_id", "timestamp", "project_id", "opening_id",
                   "original_issue_id", "feedback_type", "estimator_comment",
                   "original_ai_message", "corrected_message", "category", "is_processed"]
        
        return [dict(zip(columns, row)) for row in rows]


# Singleton instance
_memory_instance = None

def get_memory() -> ValidationMemory:
    """Get the singleton memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ValidationMemory()
    return _memory_instance


if __name__ == "__main__":
    # Test the memory system
    memory = ValidationMemory()
    
    # Simulate feedback
    feedback_id = memory.record_feedback(
        project_id="TEST-001",
        feedback_type=FeedbackType.DISMISS,
        opening_id="Opening_2.1.001",
        original_issue_id="issue_001",
        estimator_comment="This is acceptable for this project because the architect approved it.",
        original_ai_message="Door is 42\" wide but has standard 4.5\" hinges",
        category="Hinge Size"
    )
    print(f"Created feedback: {feedback_id}")
    
    # Add a missed issue
    memory.record_feedback(
        project_id="TEST-001",
        feedback_type=FeedbackType.ADD_ISSUE,
        opening_id="Opening_2.1.005",
        estimator_comment="AI missed that this exterior door needs weatherstripping",
        corrected_message="Exterior door missing weatherstripping - required per spec section 08 71 00",
        category="Weatherstripping"
    )
    
    # Get memories for prompt
    prompt_section = memory.get_memories_for_prompt()
    print("\n--- Memories for Prompt ---")
    print(prompt_section)

