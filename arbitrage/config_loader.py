#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Config loader helper"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(config_name: str = "config/base.yml") -> dict[str, Any]:
    """Load YAML config relative to the project root."""

    config_path = PROJECT_ROOT / config_name
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_secrets(secrets_name: str = "config/secrets.yml") -> dict[str, Any]:
    """Load secrets YAML. Return empty dict if file missing."""

    secrets_path = PROJECT_ROOT / secrets_name
    if not secrets_path.exists():
        return {}

    with secrets_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
