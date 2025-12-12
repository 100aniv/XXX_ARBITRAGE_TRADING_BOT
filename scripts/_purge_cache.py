#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D92-5: Python cache purge utility"""

import logging
import shutil
import importlib
from pathlib import Path

logger = logging.getLogger(__name__)


def purge_pycache() -> None:
    """Python 캐시 제거 (D92-5)"""
    repo_root = Path(__file__).parent.parent
    for d in [repo_root / "scripts", repo_root / "arbitrage"]:
        if d.exists():
            for p in d.rglob("__pycache__"):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
    importlib.invalidate_caches()
    logger.info("[PYCACHE_PURGE] Done")
