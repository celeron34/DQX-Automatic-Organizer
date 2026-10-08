"""Resolve per-process Discord tokens while keeping old formation installs working."""

from __future__ import annotations

import json
import os
from pathlib import Path


def get_token(service: str) -> str:
    env_name = f"{service.upper()}_BOT_TOKEN"
    token = os.environ.get(env_name)
    if token:
        return token

    # The existing formation process used token.json. Keep that migration path
    # for it only; new independent services always use their own environment key.
    if service == "formation":
        config_path = Path(os.environ.get("TOKEN_CONFIG_PATH", "token.json"))
        if config_path.is_file():
            with config_path.open(encoding="utf-8") as token_file:
                token = json.load(token_file).get("token")
            if token:
                return token

    raise RuntimeError(f"Set {env_name} before starting the {service} bot")
