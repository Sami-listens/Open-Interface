"""
Schema definitions for Hardware Sets and Validation Reports
Mocking Comsense export structure
"""
from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass, field

@dataclass
class HardwareComponent:
    """A single component within a hardware set (e.g., Hinge, Lock, Closer)"""
    category: str
    description: str
    quantity: int
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    short_code: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Source tracking for traceability
    source_file: Optional[str] = None
    source_line: Optional[int] = None

@dataclass
class OpeningContext:
    """Context about the opening where this hardware set is applied"""
    width_inches: float
    height_inches: float
    is_pair: bool = False
    is_exterior: bool = False
    fire_rated: bool = False
    leaf_count: int = 1
    
@dataclass
class HardwareSet:
    """Represents a complete hardware set for an opening type"""
    set_id: str
    name: str
    opening_context: OpeningContext
    components: List[HardwareComponent]
    notes: Optional[str] = None
    
    def __post_init__(self):
        # Convert dicts to objects if necessary
        if isinstance(self.opening_context, dict):
            self.opening_context = OpeningContext(**self.opening_context)
        
        new_components = []
        for c in self.components:
            if isinstance(c, dict):
                new_components.append(HardwareComponent(**c))
            else:
                new_components.append(c)
        self.components = new_components

    def json(self):
        import json
        return json.dumps(self, default=lambda o: o.__dict__)

@dataclass
class ValidationIssue:
    """A single issue found during validation"""
    level: Literal["INFO", "WARNING", "ERROR"]
    category: str
    message: str
    component_index: Optional[int] = None
    fix_suggestion: Optional[str] = None
    
    # Derived context from the component
    source_line: Optional[int] = None
    
    def json(self):
        import json
        return json.dumps(self, default=lambda o: o.__dict__)

@dataclass
class ValidationReport:
    """Complete validation report for a hardware set"""
    set_id: str
    issues: List[ValidationIssue]
    score: int = 100
    
    def json(self):
        import json
        return json.dumps(self, default=lambda o: o.__dict__)
