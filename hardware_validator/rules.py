"""
Deterministic Rules for Hardware Validation based on Estimator Logic.
These rules run locally and catch obvious issues that don't need AI.
The AI evaluator handles the nuanced checks.
"""
from typing import List
from .schema import HardwareSet, ValidationIssue


class HardwareRules:
    """
    Implements specific validation logic derived from estimator expertise.
    Only flags actual issues (ERROR/WARNING), not informational notes.
    """

    @staticmethod
    def validate_geometry(hw_set: HardwareSet) -> List[ValidationIssue]:
        """Check geometry-related issues like hinge sizing."""
        issues = []
        ctx = hw_set.opening_context
        
        # Skip if this is just a door schedule row (no hardware components)
        is_door_schedule_row = any(c.category == "Door" for c in hw_set.components)
        if is_door_schedule_row:
            # Door schedule rows are validated by AI with full context
            return []
        
        # Check: 5" Hinges required for doors > 36" wide
        has_hinges = any("hinge" in c.category.lower() for c in hw_set.components)
        
        if has_hinges and ctx.width_inches > 36:
            has_valid_hinge = False
            hinge_size_found = None
            hinge_component = None
            
            for comp in hw_set.components:
                if "hinge" in comp.category.lower() or "hinge" in comp.description.lower():
                    hinge_component = comp
                    desc = comp.description.lower()
                    # Check for 5" hinge indicators
                    if "5" in desc and ("x5" in desc or "5inch" in desc or "5\"" in desc or "5x5" in desc):
                        has_valid_hinge = True
                    elif "4" in desc:
                        hinge_size_found = "4.5\"/4\""
            
            if not has_valid_hinge and hinge_component:
                issues.append(ValidationIssue(
                    level="ERROR",
                    category="Geometry",
                    message=f"Door width {ctx.width_inches}\" (>36\") requires 5\" hinges. Found {hinge_size_found or 'undersized'}.",
                    fix_suggestion="Upgrade to 5\" heavyweight hinges.",
                    source_line=hinge_component.source_line
                ))

        return issues

    @staticmethod
    def validate_dependencies(hw_set: HardwareSet) -> List[ValidationIssue]:
        """Check for missing dependent hardware (e.g., wire harness for electrified hardware)."""
        # Skip door schedule rows
        if any(c.category == "Door" for c in hw_set.components):
            return []
        
        issues = []
        has_electrified_hardware = False
        has_wire_harness = False
        electrified_component = None
        
        electrified_keywords = ["electrified", "electric", "motor", " el ", " eu ", " rx ", "lx ", "qel"]
        harness_keywords = ["harness", "con-", "con "]
        
        for comp in hw_set.components:
            desc = comp.description.lower()
            if any(k in desc for k in electrified_keywords):
                has_electrified_hardware = True
                electrified_component = comp
            if any(k in desc for k in harness_keywords):
                has_wire_harness = True
        
        if has_electrified_hardware and not has_wire_harness:
            issues.append(ValidationIssue(
                level="ERROR",
                category="Dependency",
                message="Electrified hardware specified but no wire harness (CON-*) found.",
                fix_suggestion="Add wire harness (e.g., CON-6W for hinge-to-lock, CON-38 for frame).",
                source_line=electrified_component.source_line if electrified_component else None
            ))

        return issues

    @staticmethod
    def validate_environmental(hw_set: HardwareSet) -> List[ValidationIssue]:
        """Check for missing environmental hardware (exterior/fire-rated requirements)."""
        # Skip door schedule rows
        if any(c.category == "Door" for c in hw_set.components):
            return []
        
        issues = []
        ctx = hw_set.opening_context
        base_line = hw_set.components[0].source_line if hw_set.components else None

        # Exterior opening checks
        if ctx.is_exterior:
            has_threshold = any("threshold" in c.description.lower() for c in hw_set.components)
            has_sweep = any(k in c.description.lower() for c in hw_set.components 
                          for k in ["sweep", "bottom seal", "door bottom"])
            
            if not has_threshold:
                issues.append(ValidationIssue(
                    level="WARNING",
                    category="Environmental",
                    message="Exterior opening missing threshold.",
                    fix_suggestion="Add appropriate threshold for weather protection.",
                    source_line=base_line
                ))
            if not has_sweep:
                issues.append(ValidationIssue(
                    level="WARNING",
                    category="Environmental",
                    message="Exterior opening missing door sweep/bottom seal.",
                    fix_suggestion="Add door sweep or automatic door bottom.",
                    source_line=base_line
                ))

        # Fire-rated opening checks
        if ctx.fire_rated:
            has_closer = any("closer" in c.description.lower() or "closer" in c.category.lower() 
                           for c in hw_set.components)
            
            if not has_closer:
                issues.append(ValidationIssue(
                    level="ERROR",
                    category="Code Compliance",
                    message="Fire-rated opening requires self-closing device (closer).",
                    fix_suggestion="Add door closer with fire rating.",
                    source_line=base_line
                ))

        return issues

    @classmethod
    def run_all(cls, hw_set: HardwareSet) -> List[ValidationIssue]:
        """Run all validation rules and return combined issues."""
        issues = []
        issues.extend(cls.validate_geometry(hw_set))
        issues.extend(cls.validate_dependencies(hw_set))
        issues.extend(cls.validate_environmental(hw_set))
        return issues
