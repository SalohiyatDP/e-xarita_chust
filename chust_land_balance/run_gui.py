# -*- coding: utf-8 -*-
"""
Launcher for the Chust District Electronic Land Balance desktop GUI.

Double-click this file (or run ``python run_gui.py``) inside the ArcGIS Desktop
10.8.2 Python 2.7 environment to open the application.
"""

from __future__ import unicode_literals

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from src.gui.app import main

if __name__ == "__main__":
    main()
