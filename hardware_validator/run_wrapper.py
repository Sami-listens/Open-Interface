"""
Run script wrapper to handle path issues
"""
import sys
import os

# Add project root
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root) # Insert at 0 to prioritize

from hardware_validator.run_csv_test import test_csv_workflow

if __name__ == "__main__":
    test_csv_workflow()

