"""
Main Engine for Hardware Validation
Orchestrates Rule-Based and AI-Based Checks in an optimized manner.
"""
import sys
import os

# Add project root to sys.path BEFORE local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from typing import List, Dict, Any
from .schema import HardwareSet, ValidationReport, ValidationIssue
from .rules import HardwareRules
from .ai_evaluator import DynamicEvaluator


class HardwareValidationEngine:
    """
    Orchestrates the validation process.
    Uses a single AI call for all sets to minimize API usage.
    """
    
    def __init__(self):
        self.rules = HardwareRules()
        self.ai_evaluator = DynamicEvaluator()

    def validate_batch(self, hw_sets_data: List[Any]) -> List[ValidationReport]:
        """
        Validates a batch of hardware sets efficiently.
        - Single AI call for all sets
        - Local rule checks run in parallel
        """
        # 1. Convert all to HardwareSet objects
        hw_sets = []
        for d in hw_sets_data:
            if isinstance(d, HardwareSet):
                hw_sets.append(d)
            elif isinstance(d, dict):
                try:
                    hw_sets.append(HardwareSet(**d))
                except:
                    pass
        
        if not hw_sets:
            return []

        # 2. Single AI Evaluation call for ALL sets
        try:
            ai_issues_map = self.ai_evaluator.evaluate_batch(hw_sets)
        except Exception as e:
            print(f"  ⚠ AI evaluation failed: {e}")
            ai_issues_map = {s.set_id: [] for s in hw_sets}

        # 3. Run local rules and merge with AI results
        reports = []
        for hw_set in hw_sets:
            issues = []
            
            # Rule-Based checks (fast, local)
            rule_issues = self.rules.run_all(hw_set)
            for i in rule_issues:
                if not i.category.startswith("Rule:"):
                    i.category = f"Rule: {i.category}"
            issues.extend(rule_issues)
            
            # AI-Based issues (from single batch call)
            if hw_set.set_id in ai_issues_map:
                issues.extend(ai_issues_map[hw_set.set_id])
            
            # Calculate Score
            score = 100
            for issue in issues:
                if issue.level == "ERROR":
                    score -= 20
                elif issue.level == "WARNING":
                    score -= 10
                elif issue.level == "INFO":
                    score -= 2
            score = max(0, score)
            
            reports.append(ValidationReport(
                set_id=hw_set.set_id,
                issues=issues,
                score=score
            ))
            
        return reports

    def validate_set(self, hw_set_data: Dict[str, Any]) -> ValidationReport:
        """
        Validates a single hardware set (wraps batch for consistency).
        """
        reports = self.validate_batch([hw_set_data])
        if reports:
            return reports[0]
        return ValidationReport(
            set_id=hw_set_data.get("set_id", "UNKNOWN"),
            issues=[ValidationIssue(level="ERROR", category="System", message="Validation failed")],
            score=0
        )
