"""
SQLite-based logging system for agent decisions and actions.
Provides full audit trail for the validation workflow.
"""
import sqlite3
import json
import os
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ValidationLogger:
    """
    Logs all agent decisions and actions to SQLite.
    Supports querying by project, agent, time range, etc.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "validation_logs.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project_id TEXT,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                level TEXT NOT NULL,
                details TEXT,
                context TEXT
            )
        """)
        
        # Index for fast queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project ON agent_logs(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON agent_logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent ON agent_logs(agent)")
        
        # Rule decisions table (tracks human preferences)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rule_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project_id TEXT NOT NULL,
                conflict_id TEXT,
                tdc_rule_id TEXT,
                project_rule_id TEXT,
                decision TEXT NOT NULL,
                reason TEXT,
                decided_by TEXT
            )
        """)
        
        # Validation runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                project_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                spec_pdf_path TEXT,
                door_schedule_path TEXT,
                total_issues INTEGER DEFAULT 0,
                summary TEXT
            )
        """)
        
        # Session state table - persists full validation session
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT UNIQUE NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                session_data TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def log(self, project_id: str, agent: str, action: str, 
            details: Dict[str, Any] = None, level: LogLevel = LogLevel.INFO,
            context: Dict[str, Any] = None):
        """
        Log an agent action or decision.
        
        Args:
            project_id: The project being worked on
            agent: Name of the agent (e.g., "RuleExtractor", "Validator", "HumanInLoop")
            action: The action taken (e.g., "extracted_rules", "found_conflict")
            details: Structured details about the action
            level: Log level
            context: Additional context (e.g., current state, inputs)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO agent_logs (timestamp, project_id, agent, action, level, details, context)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            project_id,
            agent,
            action,
            level.value,
            json.dumps(details) if details else None,
            json.dumps(context) if context else None
        ))
        
        conn.commit()
        conn.close()
        
        # Also print for debugging
        print(f"[{level.value}] [{agent}] {action}: {details}")
    
    def log_rule_decision(self, project_id: str, conflict_id: str,
                          tdc_rule_id: str, project_rule_id: str,
                          decision: str, reason: str = None, decided_by: str = "human"):
        """Log a rule preference decision."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO rule_decisions 
            (timestamp, project_id, conflict_id, tdc_rule_id, project_rule_id, decision, reason, decided_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            project_id,
            conflict_id,
            tdc_rule_id,
            project_rule_id,
            decision,
            reason,
            decided_by
        ))
        
        conn.commit()
        conn.close()
    
    def start_validation_run(self, run_id: str, project_id: str, 
                              spec_pdf_path: str, door_schedule_path: str):
        """Record the start of a validation run."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO validation_runs 
            (run_id, project_id, started_at, status, spec_pdf_path, door_schedule_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            project_id,
            datetime.now().isoformat(),
            "started",
            spec_pdf_path,
            door_schedule_path
        ))
        
        conn.commit()
        conn.close()
    
    def complete_validation_run(self, run_id: str, status: str, 
                                 total_issues: int, summary: Dict = None):
        """Record the completion of a validation run."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE validation_runs 
            SET completed_at = ?, status = ?, total_issues = ?, summary = ?
            WHERE run_id = ?
        """, (
            datetime.now().isoformat(),
            status,
            total_issues,
            json.dumps(summary) if summary else None,
            run_id
        ))
        
        conn.commit()
        conn.close()
    
    def get_logs(self, project_id: str = None, agent: str = None,
                 level: LogLevel = None, limit: int = 100) -> List[Dict]:
        """
        Query logs with optional filters.
        
        Returns logs in reverse chronological order.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM agent_logs WHERE 1=1"
        params = []
        
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        
        if agent:
            query += " AND agent = ?"
            params.append(agent)
        
        if level:
            query += " AND level = ?"
            params.append(level.value)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        columns = ["id", "timestamp", "project_id", "agent", "action", "level", "details", "context"]
        logs = []
        for row in rows:
            log = dict(zip(columns, row))
            if log["details"]:
                log["details"] = json.loads(log["details"])
            if log["context"]:
                log["context"] = json.loads(log["context"])
            logs.append(log)
        
        return logs
    
    def get_rule_decisions(self, project_id: str) -> List[Dict]:
        """Get all rule decisions for a project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM rule_decisions 
            WHERE project_id = ? 
            ORDER BY timestamp DESC
        """, (project_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        columns = ["id", "timestamp", "project_id", "conflict_id", 
                   "tdc_rule_id", "project_rule_id", "decision", "reason", "decided_by"]
        return [dict(zip(columns, row)) for row in rows]
    
    def get_validation_history(self, project_id: str = None, limit: int = 20) -> List[Dict]:
        """Get validation run history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT * FROM validation_runs 
                WHERE project_id = ? 
                ORDER BY started_at DESC LIMIT ?
            """, (project_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM validation_runs 
                ORDER BY started_at DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        columns = ["id", "run_id", "project_id", "started_at", "completed_at",
                   "status", "spec_pdf_path", "door_schedule_path", "total_issues", "summary"]
        results = []
        for row in rows:
            result = dict(zip(columns, row))
            if result["summary"]:
                result["summary"] = json.loads(result["summary"])
            results.append(result)
        
        return results
    
    # ========================================================================
    # Session Persistence
    # ========================================================================
    
    def save_session(self, project_id: str, session_data: Dict[str, Any]):
        """
        Persist a validation session to disk.
        This allows sessions to survive server restarts.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Upsert - insert or replace
        cursor.execute("""
            INSERT OR REPLACE INTO session_state (project_id, updated_at, status, session_data)
            VALUES (?, ?, ?, ?)
        """, (
            project_id,
            datetime.now().isoformat(),
            session_data.get("status", "unknown"),
            json.dumps(session_data)
        ))
        
        conn.commit()
        conn.close()
    
    def load_session(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a previously saved session.
        Returns None if no session exists.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT session_data FROM session_state WHERE project_id = ?
        """, (project_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def load_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all saved sessions.
        Returns a dict mapping project_id -> session_data.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT project_id, session_data FROM session_state")
        rows = cursor.fetchall()
        conn.close()
        
        sessions = {}
        for project_id, session_json in rows:
            try:
                sessions[project_id] = json.loads(session_json)
            except:
                pass
        
        return sessions
    
    def delete_session(self, project_id: str):
        """Delete a saved session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_state WHERE project_id = ?", (project_id,))
        conn.commit()
        conn.close()

    def get_context_for_query(self, project_id: str, query: str) -> str:
        """
        Build context string from logs for answering user queries.
        This is used by the BigBrain chatbot to answer questions about agent decisions.
        """
        logs = self.get_logs(project_id=project_id, limit=50)
        decisions = self.get_rule_decisions(project_id)
        history = self.get_validation_history(project_id, limit=5)
        
        context_parts = []
        
        if history:
            context_parts.append("## Recent Validation Runs")
            for run in history[:3]:
                context_parts.append(
                    f"- Run {run['run_id'][:8]}: {run['status']} at {run['started_at']}, "
                    f"found {run['total_issues']} issues"
                )
        
        if decisions:
            context_parts.append("\n## Rule Decisions Made")
            for dec in decisions[:5]:
                context_parts.append(
                    f"- {dec['timestamp']}: Chose {dec['decision']} for conflict {dec['conflict_id']}"
                )
        
        if logs:
            context_parts.append("\n## Recent Agent Actions")
            for log in logs[:10]:
                context_parts.append(
                    f"- [{log['level']}] {log['agent']}: {log['action']}"
                )
        
        return "\n".join(context_parts)


if __name__ == "__main__":
    # Test the logger
    logger = ValidationLogger()
    
    # Test logging
    logger.log("TEST-001", "TestAgent", "test_action", 
               {"test": "data"}, LogLevel.INFO)
    
    # Retrieve logs
    logs = logger.get_logs()
    print(f"Found {len(logs)} logs")
    for log in logs[:3]:
        print(log)

