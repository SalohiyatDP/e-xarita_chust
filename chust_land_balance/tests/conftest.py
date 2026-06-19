# -*- coding: utf-8 -*-
import os
import sys

# Make the package root importable for the tests.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
