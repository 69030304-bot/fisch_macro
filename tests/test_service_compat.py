"""
tests/test_service_compat.py - Pytest wrapper for test_service.py.
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import test_service


def test_service_all():
    """Runs all 10 baseline service and database test cases."""
    test_service.run_tests()
