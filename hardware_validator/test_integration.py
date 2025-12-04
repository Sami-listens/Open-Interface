import sys
import os

# Add the project root to sys.path so we can import hardware_validator
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

import json
from hardware_validator.node import hardware_evaluator_node

def test_integration():
    # 1. Create state with no hardware sets -> triggers mock loading
    state = {"hardware_sets": []}
    
    print("Running Hardware Evaluator Node...")
    result = hardware_evaluator_node(state)
    
    print("\n--- Validation Summary ---")
    print(result["validation_summary"])
    
    # print("\n--- Report Data ---")
    # print(json.dumps(result["validation_reports"], indent=2))

if __name__ == "__main__":
    test_integration()
