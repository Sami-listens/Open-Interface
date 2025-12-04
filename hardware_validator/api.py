"""
Hardware Validation Dashboard API
FastAPI backend that serves the validation workflow.

Endpoints:
- POST /api/projects/{project_id}/start - Start validation for a project
- GET /api/projects/{project_id}/rules - Get TDC + Project rules with conflicts
- POST /api/projects/{project_id}/rules/approve - Submit rule preferences
- GET /api/projects/{project_id}/validation - Get validation results
- GET /api/projects/{project_id}/logs - Get agent decision logs
"""
import os
import sys
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# Local imports
from hardware_validator.spec_parser import SpecSectionParser
from hardware_validator.project_rule_generator import ProjectRuleGenerator
from hardware_validator.ai_evaluator import DynamicEvaluator, TDC_HARDWARE_RULES
from hardware_validator.parser import HardwareExportParser
from hardware_validator.logging_db import ValidationLogger, LogLevel
from hardware_validator.memory_system import ValidationMemory, FeedbackType, get_memory
from hardware_validator.conflict_detector import get_conflict_detector

app = FastAPI(
    title="The Door Company - Hardware Validation Dashboard",
    description="AI-powered hardware validation system",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize logger and memory
logger = ValidationLogger()
memory = get_memory()

# In-memory session store - now with persistence!
validation_sessions: Dict[str, Dict] = {}

# Load persisted sessions on startup
def _load_persisted_sessions():
    """Load any previously saved sessions from disk."""
    global validation_sessions
    try:
        saved = logger.load_all_sessions()
        if saved:
            validation_sessions.update(saved)
            print(f"✓ Loaded {len(saved)} persisted session(s): {list(saved.keys())}")
    except Exception as e:
        print(f"⚠ Could not load persisted sessions: {e}")

_load_persisted_sessions()

def _persist_session(project_id: str):
    """Save session state to disk for persistence."""
    if project_id in validation_sessions:
        try:
            logger.save_session(project_id, validation_sessions[project_id])
        except Exception as e:
            print(f"⚠ Could not persist session {project_id}: {e}")

# ============================================================================
# Pydantic Models
# ============================================================================

class ProjectStartRequest(BaseModel):
    spec_pdf_path: str
    door_schedule_path: str
    project_name: Optional[str] = None

class RuleApprovalRequest(BaseModel):
    approved_rules: List[str]  # List of rule IDs to use
    rule_preferences: Dict[str, str]  # {conflict_id: "tdc" or "project"}

class ValidationStatus(BaseModel):
    status: str  # "pending", "extracting_rules", "awaiting_approval", "validating", "complete", "error"
    message: str
    progress: int  # 0-100

class IssueFeedbackRequest(BaseModel):
    opening_id: str
    issue_id: Optional[str] = None
    feedback_type: str  # "dismiss", "confirm", "add_issue", "modify"
    comment: str
    original_message: Optional[str] = None
    corrected_message: Optional[str] = None
    category: Optional[str] = None

class AddIssueRequest(BaseModel):
    opening_id: str
    category: str
    message: str
    comment: str
    level: str = "WARNING"

# ============================================================================
# Helper Functions
# ============================================================================

def parse_tdc_rules_to_json() -> List[Dict]:
    """Parse the TDC_HARDWARE_RULES string into structured JSON format."""
    rules = []
    current_section = ""
    rule_id_counter = 0
    
    lines = TDC_HARDWARE_RULES.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('=== SECTION'):
            current_section = line.replace('===', '').strip()
        elif line.startswith('**') and '.' in line:
            # This is a rule header like "**A1. EXTERIOR OPENING REQUIREMENTS**"
            parts = line.replace('**', '').strip().split('.')
            if len(parts) >= 2:
                rule_id = parts[0].strip()
                rule_title = '.'.join(parts[1:]).strip()
                rules.append({
                    "id": f"TDC-{rule_id}",
                    "category": current_section,
                    "title": rule_title,
                    "description": "",
                    "details": [],
                    "source": "TDC Standards"
                })
        elif line.startswith('-') and rules:
            # This is a detail bullet under the current rule
            detail = line[1:].strip()
            if detail:
                rules[-1]["details"].append(detail)
                if not rules[-1]["description"]:
                    rules[-1]["description"] = detail
    
    return rules

def find_rule_conflicts(tdc_rules: List[Dict], project_rules: List[Dict]) -> List[Dict]:
    """
    Identify potential conflicts between TDC and Project rules.
    Uses smart matching to find the MOST RELEVANT TDC rule for each project rule.
    Explains WHY there's a conflict.
    """
    conflicts = []
    seen_pairs = set()  # Prevent duplicates
    
    # Topic categories with weighted keywords (more specific = higher weight)
    topic_keywords = {
        "hinge": {
            "primary": ["hinge", "pivot", "continuous hinge"],
            "secondary": ["nrp", "non-removable pin", "ball bearing", "5 inch", "4.5 inch"]
        },
        "frame": {
            "primary": ["frame", "hmf", "hollow metal frame", "aluminum frame"],
            "secondary": ["jamb", "throat", "welded", "knock-down", "kd"]
        },
        "door": {
            "primary": ["door", "hmd", "hollow metal door", "wood door"],
            "secondary": ["gauge", "core", "seamless", "18 gauge", "16 gauge"]
        },
        "fastener": {
            "primary": ["screw", "bolt", "fastener"],
            "secondary": ["machine screw", "through-bolt", "sex bolt", "anchor"]
        },
        "exterior": {
            "primary": ["exterior", "outside", "outdoor"],
            "secondary": ["galvanneal", "weather", "insulated", "a60"]
        },
        "fire_rating": {
            "primary": ["fire", "rated", "fire-rated"],
            "secondary": ["90 minute", "60 minute", "45 minute", "ul labeled", "mineral core"]
        },
        "exit_device": {
            "primary": ["exit device", "panic", "egress"],
            "secondary": ["rim", "svr", "cvr", "touch bar"]
        },
        "closer": {
            "primary": ["closer", "door closer"],
            "secondary": ["overhead", "concealed", "ada"]
        },
        "lock": {
            "primary": ["lock", "lockset", "cylindrical"],
            "secondary": ["mortise", "lever", "thumbturn"]
        },
        "threshold": {
            "primary": ["threshold", "sill"],
            "secondary": ["ada", "saddle"]
        },
        "astragal": {
            "primary": ["astragal", "meeting stile"],
            "secondary": ["overlapping", "pair"]
        },
        "glass": {
            "primary": ["glass", "lite", "glazing", "vision"],
            "secondary": ["tempered", "wired", "fire-rated glass"]
        }
    }
    
    def get_topic_scores(text: str) -> Dict[str, float]:
        """Calculate relevance scores for each topic."""
        text = text.lower()
        scores = {}
        for topic, keywords in topic_keywords.items():
            score = 0
            for kw in keywords.get("primary", []):
                if kw in text:
                    score += 3  # Primary keywords worth more
            for kw in keywords.get("secondary", []):
                if kw in text:
                    score += 1  # Secondary keywords
            if score > 0:
                scores[topic] = score
        return scores
    
    def find_best_tdc_match(pr: Dict, tdc_rules: List[Dict]) -> tuple:
        """Find the best matching TDC rule for a project rule."""
        pr_text = f"{pr.get('description', '')} {pr.get('match_criteria', '')} {pr.get('check_logic', '')}"
        pr_topics = get_topic_scores(pr_text)
        
        if not pr_topics:
            return None, None, 0
        
        best_match = None
        best_topic = None
        best_score = 0
        
        for tdc in tdc_rules:
            tdc_text = f"{tdc.get('title', '')} {' '.join(tdc.get('details', []))}"
            tdc_topics = get_topic_scores(tdc_text)
            
            # Find overlapping topics
            for topic in pr_topics:
                if topic in tdc_topics:
                    combined_score = pr_topics[topic] + tdc_topics[topic]
                    if combined_score > best_score:
                        best_score = combined_score
                        best_match = tdc
                        best_topic = topic
        
        return best_match, best_topic, best_score
    
    def generate_conflict_reason(pr: Dict, tdc: Dict, topic: str) -> str:
        """Generate a human-readable explanation of why there might be a conflict."""
        pr_desc = pr.get('description', '')[:100]
        tdc_details = tdc.get('details', [])
        tdc_first_detail = tdc_details[0][:80] if tdc_details else tdc.get('title', '')
        
        reasons = {
            "hinge": f"Project specifies hinge requirements that may differ from TDC standards.",
            "frame": f"Frame specifications may override TDC defaults.",
            "door": f"Door material/construction may differ from TDC standards.",
            "fastener": f"Fastener requirements may differ from TDC specifications.",
            "exterior": f"Exterior opening requirements may have project-specific constraints.",
            "fire_rating": f"Fire rating requirements may override TDC defaults.",
            "exit_device": f"Exit device specifications may differ.",
            "closer": f"Door closer requirements may differ.",
            "lock": f"Lock/hardware specifications may differ.",
            "threshold": f"Threshold requirements may differ.",
            "astragal": f"Astragal/pair door requirements may differ.",
            "glass": f"Glazing requirements may differ.",
        }
        
        base_reason = reasons.get(topic, "Rules may have overlapping scope.")
        return f"{base_reason}\n\n**TDC says:** \"{tdc_first_detail}\"\n**Project says:** \"{pr_desc}\""
    
    # Process each project rule
    for pr in project_rules:
        best_tdc, topic, score = find_best_tdc_match(pr, tdc_rules)
        
        if best_tdc and score >= 4:  # Threshold: need meaningful overlap
            pair_key = (pr.get('id'), best_tdc.get('id'))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                
                conflicts.append({
                    "id": f"conflict_{len(conflicts)+1}",
                    "category": topic.replace('_', ' ').title(),
                    "tdc_rule": best_tdc,
                    "project_rule": pr,
                    "conflict_type": "potential_override",
                    "reason": generate_conflict_reason(pr, best_tdc, topic),
                    "relevance_score": score,
                    "recommendation": "project"  # Default to project-specific
                })
    
    # Sort by relevance score (most relevant first)
    conflicts.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    return conflicts

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve the dashboard HTML."""
    dashboard_path = Path(__file__).parent / "dashboard" / "index.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    return {"message": "Hardware Validation API", "docs": "/docs"}

@app.post("/api/projects/{project_id}/start")
async def start_validation(project_id: str, request: ProjectStartRequest, background_tasks: BackgroundTasks):
    """
    Start the validation workflow for a project.
    1. Extract rules from PDF
    2. Compare with TDC rules
    3. Return status for UI polling
    """
    session_id = str(uuid.uuid4())
    
    # Initialize session
    validation_sessions[project_id] = {
        "session_id": session_id,
        "status": "extracting_rules",
        "progress": 10,
        "project_name": request.project_name or project_id,
        "spec_pdf_path": request.spec_pdf_path,
        "door_schedule_path": request.door_schedule_path,
        "tdc_rules": [],
        "project_rules": [],
        "conflicts": [],
        "approved_rules": [],
        "validation_results": [],
        "created_at": datetime.now().isoformat()
    }
    
    # Log the start
    logger.log(
        project_id=project_id,
        agent="ValidationAPI",
        action="start_validation",
        details={"spec_pdf": request.spec_pdf_path, "door_schedule": request.door_schedule_path},
        level=LogLevel.INFO
    )
    
    # Run extraction in background
    background_tasks.add_task(extract_rules_task, project_id, request.spec_pdf_path)
    
    return {"session_id": session_id, "status": "extracting_rules", "message": "Validation started"}

async def extract_rules_task(project_id: str, spec_pdf_path: str):
    """Background task to extract rules from PDF."""
    try:
        session = validation_sessions.get(project_id)
        if not session:
            return
        
        # Parse TDC rules
        tdc_rules = parse_tdc_rules_to_json()
        session["tdc_rules"] = tdc_rules
        session["progress"] = 30
        
        logger.log(project_id, "RuleExtractor", "parsed_tdc_rules", 
                   {"count": len(tdc_rules)}, LogLevel.INFO)
        
        # Extract project-specific rules from PDF
        if os.path.exists(spec_pdf_path):
            parser = SpecSectionParser(spec_pdf_path)
            sections = parser.extract_all_sections()
            
            session["progress"] = 50
            
            if sections:
                generator = ProjectRuleGenerator()
                project_rules = generator.generate_rules(sections)
                session["project_rules"] = project_rules
                
                logger.log(project_id, "RuleExtractor", "extracted_project_rules",
                           {"count": len(project_rules), "sections": list(sections.keys())}, LogLevel.INFO)
        
        session["progress"] = 70
        
        # Find conflicts using LLM-based intelligent detection
        detector = get_conflict_detector()
        conflict_result = detector.detect_conflicts(tdc_rules, session.get("project_rules", []))
        
        session["conflicts"] = conflict_result.get("conflicts", [])
        session["compatible_rules"] = conflict_result.get("compatible_rules", [])
        session["conflict_analysis"] = conflict_result.get("analysis_notes", "")
        
        logger.log(project_id, "ConflictDetector", "found_conflicts",
                   {"count": conflict_result.get("total_conflicts", 0), 
                    "analysis": conflict_result.get("analysis_notes", "")}, LogLevel.INFO)
        
        session["status"] = "awaiting_approval"
        session["progress"] = 100
        _persist_session(project_id)  # Save state
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        logger.log(project_id, "RuleExtractor", "extraction_failed",
                   {"error": str(e)}, LogLevel.ERROR)
        _persist_session(project_id)  # Save error state

@app.get("/api/projects/{project_id}/status")
async def get_status(project_id: str):
    """Get current validation status."""
    session = validation_sessions.get(project_id)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "status": session["status"],
        "progress": session["progress"],
        "message": f"Status: {session['status']}"
    }

@app.get("/api/projects/{project_id}/rules")
async def get_rules(project_id: str):
    """Get TDC rules, project rules, and conflicts."""
    session = validation_sessions.get(project_id)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "project_name": session["project_name"],
        "tdc_rules": session["tdc_rules"],
        "project_rules": session["project_rules"],
        "conflicts": session["conflicts"],
        "status": session["status"]
    }

@app.post("/api/projects/{project_id}/rules/approve")
async def approve_rules(project_id: str, request: RuleApprovalRequest, background_tasks: BackgroundTasks):
    """
    Submit rule preferences after human review.
    Then trigger validation with approved rules.
    """
    session = validation_sessions.get(project_id)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")
    
    session["approved_rules"] = request.approved_rules
    session["rule_preferences"] = request.rule_preferences
    session["status"] = "validating"
    session["progress"] = 10
    
    logger.log(project_id, "HumanInLoop", "rules_approved",
               {"preferences": request.rule_preferences}, LogLevel.INFO)
    
    # Run validation in background
    background_tasks.add_task(run_validation_task, project_id)
    
    return {"status": "validating", "message": "Rules approved, validation started"}

async def run_validation_task(project_id: str):
    """Background task to run validation."""
    try:
        session = validation_sessions.get(project_id)
        if not session:
            return
        
        door_schedule_path = session["door_schedule_path"]
        
        if not os.path.exists(door_schedule_path):
            session["status"] = "error"
            session["error"] = f"Door schedule not found: {door_schedule_path}"
            return
        
        session["progress"] = 30
        
        # Parse door schedule
        hw_sets = HardwareExportParser.parse_csv(door_schedule_path)
        
        session["progress"] = 50
        
        # Build final rules based on preferences
        final_project_rules = []
        preferences = session.get("rule_preferences", {})
        
        for pr in session.get("project_rules", []):
            # Check if this rule was overridden by TDC preference
            conflict_for_rule = next((c for c in session["conflicts"] 
                                       if c["project_rule"]["id"] == pr["id"]), None)
            if conflict_for_rule:
                pref = preferences.get(conflict_for_rule["id"], "project")
                if pref == "project":
                    final_project_rules.append(pr)
            else:
                final_project_rules.append(pr)
        
        session["progress"] = 60
        
        # Run AI validation
        evaluator = DynamicEvaluator()
        issues_map = evaluator.evaluate_batch(hw_sets, project_rules=final_project_rules)
        
        session["progress"] = 90
        
        # Format results for UI
        results = []
        for set_id, issues in issues_map.items():
            if issues:
                results.append({
                    "opening_id": set_id,
                    "issues": [
                        {
                            "level": i.level,
                            "category": i.category,
                            "message": i.message,
                            "fix_suggestion": i.fix_suggestion,
                            "source_line": i.source_line,
                            "highlight_color": "yellow" if i.level == "WARNING" else "red"
                        }
                        for i in issues
                    ]
                })
        
        session["validation_results"] = results
        session["status"] = "complete"
        session["progress"] = 100
        
        logger.log(project_id, "Validator", "validation_complete",
                   {"total_issues": sum(len(r["issues"]) for r in results),
                    "openings_with_issues": len(results)}, LogLevel.INFO)
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        logger.log(project_id, "Validator", "validation_failed",
                   {"error": str(e)}, LogLevel.ERROR)

@app.get("/api/projects/{project_id}/validation")
async def get_validation_results(project_id: str):
    """Get validation results with highlighted issues."""
    session = validation_sessions.get(project_id)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "status": session["status"],
        "results": session.get("validation_results", []),
        "summary": {
            "total_openings_checked": len(session.get("validation_results", [])),
            "total_issues": sum(len(r["issues"]) for r in session.get("validation_results", []))
        }
    }

@app.get("/api/projects/{project_id}/logs")
async def get_logs(project_id: str):
    """Get agent decision logs for this project."""
    logs = logger.get_logs(project_id)
    return {"logs": logs}

@app.get("/api/tdc-rules")
async def get_tdc_rules():
    """Get all TDC company-wide rules."""
    return {"rules": parse_tdc_rules_to_json()}

# ============================================================================
# Feedback & Learning Endpoints
# ============================================================================

@app.post("/api/projects/{project_id}/feedback")
async def submit_feedback(project_id: str, request: IssueFeedbackRequest):
    """
    Submit feedback on a validation issue.
    This feeds into the learning system to improve future validations.
    """
    try:
        feedback_type = FeedbackType(request.feedback_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feedback type: {request.feedback_type}")
    
    feedback_id = memory.record_feedback(
        project_id=project_id,
        feedback_type=feedback_type,
        opening_id=request.opening_id,
        original_issue_id=request.issue_id,
        estimator_comment=request.comment,
        original_ai_message=request.original_message,
        corrected_message=request.corrected_message,
        category=request.category
    )
    
    logger.log(project_id, "HumanFeedback", f"feedback_{feedback_type.value}",
               {"opening": request.opening_id, "comment": request.comment}, LogLevel.INFO)
    
    return {"feedback_id": feedback_id, "status": "recorded", "message": "Feedback recorded and learning updated"}

@app.post("/api/projects/{project_id}/issues/add")
async def add_manual_issue(project_id: str, request: AddIssueRequest):
    """
    Add a manual issue that the AI missed.
    This also creates a memory for future validations.
    """
    session = validation_sessions.get(project_id)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Add to validation results
    new_issue = {
        "level": request.level,
        "category": f"Manual: {request.category}",
        "message": request.message,
        "fix_suggestion": None,
        "source_line": None,
        "highlight_color": "yellow" if request.level == "WARNING" else "red",
        "added_by": "estimator"
    }
    
    # Find or create the opening in results
    results = session.get("validation_results", [])
    opening_found = False
    for result in results:
        if result["opening_id"] == request.opening_id:
            result["issues"].append(new_issue)
            opening_found = True
            break
    
    if not opening_found:
        results.append({
            "opening_id": request.opening_id,
            "issues": [new_issue]
        })
    
    session["validation_results"] = results
    
    # Record as feedback for learning
    memory.record_feedback(
        project_id=project_id,
        feedback_type=FeedbackType.ADD_ISSUE,
        opening_id=request.opening_id,
        estimator_comment=request.comment,
        corrected_message=request.message,
        category=request.category
    )
    
    logger.log(project_id, "HumanFeedback", "manual_issue_added",
               {"opening": request.opening_id, "category": request.category}, LogLevel.INFO)
    
    return {"status": "added", "message": "Issue added and recorded for learning"}

@app.delete("/api/projects/{project_id}/issues/{opening_id}/{issue_index}")
async def dismiss_issue(project_id: str, opening_id: str, issue_index: int, comment: str = ""):
    """
    Dismiss an issue as not applicable.
    Records feedback for learning.
    """
    session = validation_sessions.get(project_id)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")
    
    results = session.get("validation_results", [])
    for result in results:
        if result["opening_id"] == opening_id:
            if 0 <= issue_index < len(result["issues"]):
                dismissed_issue = result["issues"][issue_index]
                
                # Record feedback before removing
                memory.record_feedback(
                    project_id=project_id,
                    feedback_type=FeedbackType.DISMISS,
                    opening_id=opening_id,
                    estimator_comment=comment,
                    original_ai_message=dismissed_issue.get("message"),
                    category=dismissed_issue.get("category", "").replace("AI: ", "")
                )
                
                # Mark as dismissed (don't remove, just mark)
                result["issues"][issue_index]["dismissed"] = True
                result["issues"][issue_index]["dismiss_comment"] = comment
                
                logger.log(project_id, "HumanFeedback", "issue_dismissed",
                           {"opening": opening_id, "issue": dismissed_issue.get("message")[:50]}, LogLevel.INFO)
                
                return {"status": "dismissed", "message": "Issue dismissed and feedback recorded"}
    
    raise HTTPException(status_code=404, detail="Issue not found")

@app.get("/api/memories")
async def get_memories(active_only: bool = True):
    """Get all learned memories from estimator feedback."""
    memories = memory.get_all_memories(include_inactive=not active_only)
    return {"memories": memories, "count": len(memories)}

@app.get("/api/memories/prompt")
async def get_memories_prompt():
    """Get the memory prompt section that will be injected into AI."""
    prompt = memory.get_memories_for_prompt()
    return {"prompt_section": prompt}

@app.delete("/api/memories/{memory_id}")
async def deactivate_memory(memory_id: str):
    """Deactivate a memory (won't be used in future validations)."""
    memory.deactivate_memory(memory_id)
    return {"status": "deactivated"}

@app.get("/api/projects/{project_id}/feedback-history")
async def get_feedback_history(project_id: str):
    """Get feedback history for a project."""
    history = memory.get_feedback_history(project_id)
    return {"history": history}

# ============================================================================
# Export Functionality - CommSense Compatible
# ============================================================================

@app.get("/api/projects/{project_id}/export")
async def export_validation_results(project_id: str, format: str = "excel"):
    """
    Export validation results in a format compatible with CommSense workflow.
    
    Format options:
    - excel: Creates Excel file with yellow-highlighted cells (for CommSense agent)
    - csv: Creates CSV with validation notes column
    - json: Returns raw JSON data
    """
    session = validation_sessions.get(project_id)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")
    
    results = session.get("validation_results", [])
    
    if format == "json":
        return {"project_id": project_id, "results": results}
    
    if format == "csv":
        # Return CSV-formatted data
        csv_data = _build_csv_export(results, project_id)
        from fastapi.responses import Response
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={project_id}_validation_issues.csv"}
        )
    
    if format == "excel":
        # Return Excel with yellow-highlighted cells
        excel_bytes = _build_excel_export(results, project_id)
        from fastapi.responses import Response
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={project_id}_validation_issues.xlsx"}
        )
    
    raise HTTPException(status_code=400, detail=f"Unknown format: {format}")


def _build_csv_export(results: List[Dict], project_id: str) -> str:
    """Build CSV export with validation issues."""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        "Opening", "Category", "Level", "Issue Description", 
        "Fix Suggestion", "Rule Reference", "Status"
    ])
    
    # Data rows
    for result in results:
        opening_id = result.get("opening_id", "")
        for issue in result.get("issues", []):
            if issue.get("dismissed"):
                status = "Dismissed"
            else:
                status = "Active"
            
            writer.writerow([
                opening_id,
                issue.get("category", "").replace("AI: ", ""),
                issue.get("level", "WARNING"),
                issue.get("message", ""),
                issue.get("fix_suggestion", ""),
                "",  # Rule reference extracted from message if needed
                status
            ])
    
    return output.getvalue()


def _build_excel_export(results: List[Dict], project_id: str) -> bytes:
    """
    Build Excel export with yellow-highlighted cells.
    Format matches what CommSense agent expects to read.
    Extracts current values and recommended new values from issue messages.
    """
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    except ImportError:
        # Fallback to CSV if openpyxl not available
        csv_data = _build_csv_export(results, project_id)
        return csv_data.encode('utf-8')
    
    import io
    import re
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Validation Issues"
    
    # Define styles
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    red_font = Font(color="FF0000", bold=True)
    header_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Headers - now with clearer columns
    headers = ["Opening", "Field", "Current Issue", "New Value Required", "Category", "Level"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center')
    
    def extract_values_from_message(message: str, fix: str, category: str) -> tuple:
        """
        Parse AI message to extract current issue and recommended new value.
        Returns (current_issue, new_value)
        """
        message_lower = message.lower()
        
        # Extract current issue description (the problem)
        current_issue = message.split("|")[0].strip() if "|" in message else message
        # Remove rule reference prefix like [A2]
        current_issue = re.sub(r'^\[[A-Z0-9-]+\]\s*', '', current_issue)
        
        # Extract recommended new value from fix suggestion or message
        new_value = ""
        
        # Pattern matching for common fix suggestions
        if fix:
            # Direct specifications like "Specify 5" heavyweight hinges"
            spec_match = re.search(r'[Ss]pecify\s+(.+?)(?:\.|$)', fix)
            if spec_match:
                new_value = spec_match.group(1).strip()
            
            # "Change to X" or "Update to X"
            change_match = re.search(r'(?:[Cc]hange|[Uu]pdate|[Ss]et)\s+(?:to\s+)?(.+?)(?:\.|$)', fix)
            if change_match and not new_value:
                new_value = change_match.group(1).strip()
            
            # If no pattern matched, use the fix as-is
            if not new_value:
                new_value = fix
        
        # If still no new value, try to extract from message
        if not new_value:
            # Look for "requires X" or "should be X"
            req_match = re.search(r'(?:requires?|should be|must be|need)\s+(.+?)(?:\.|,|$)', message_lower)
            if req_match:
                new_value = req_match.group(1).strip()
        
        return current_issue, new_value
    
    # Data rows - format for CommSense to read
    row_num = 2
    for result in results:
        opening_id = result.get("opening_id", "")
        
        for issue in result.get("issues", []):
            if issue.get("dismissed"):
                continue  # Skip dismissed issues
            
            # Parse the message to extract field info
            message = issue.get("message", "")
            fix = issue.get("fix_suggestion", "")
            category = issue.get("category", "").replace("AI: ", "")
            level = issue.get("level", "WARNING")
            
            # Extract current issue and new value
            current_issue, new_value = extract_values_from_message(message, fix, category)
            
            # Opening column
            ws.cell(row=row_num, column=1, value=opening_id).border = thin_border
            
            # Field - extract from category
            field = category.split(":")[0] if ":" in category else category
            ws.cell(row=row_num, column=2, value=field).border = thin_border
            
            # Current Issue - what's wrong (yellow highlight)
            issue_cell = ws.cell(row=row_num, column=3, value=current_issue)
            issue_cell.fill = yellow_fill
            issue_cell.border = thin_border
            if level == "ERROR":
                issue_cell.font = red_font
            
            # New Value Required - what to change to (yellow highlight, red text for errors)
            new_value_cell = ws.cell(row=row_num, column=4, value=new_value or fix or "Review and update")
            new_value_cell.fill = yellow_fill
            new_value_cell.border = thin_border
            if level == "ERROR":
                new_value_cell.font = red_font
            
            # Category
            ws.cell(row=row_num, column=5, value=category).border = thin_border
            
            # Level
            level_cell = ws.cell(row=row_num, column=6, value=level)
            level_cell.border = thin_border
            if level == "ERROR":
                level_cell.font = red_font
            
            row_num += 1
    
    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 60)
        ws.column_dimensions[column].width = adjusted_width
    
    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()

# ============================================================================
# Static Files & Dashboard
# ============================================================================

# Mount static files for dashboard
dashboard_dir = Path(__file__).parent / "dashboard"
if dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

