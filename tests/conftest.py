#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest configuration and fixtures

Path bootstrap: ensures imports work from any CWD
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
