"""
Token Manager for Anycubic Cloud.
Handles token retrieval from config, environment, or user input.
"""

import os
import json
import logging

logger = logging.getLogger("anycubic_cloud.token_manager")

CONFIG_PATH = os.path.expandvars(r"%APPDATA%\OrcaSlicer\orca_plugins\anycubic_cloud\config.json")
SLICER_NEXT_CONF = os.path.expandvars(r"%APPDATA%\AnycubicSlicerNext\AnycubicSlicerNext.conf")


def get_token():
    """Retrieve Anycubic Cloud access token from config, env, or Slicer Next."""
    # 1. Environment variable
    env_token = os.environ.get("ANYCUBIC_TOKEN")
    if env_token:
        logger.info("Using token from ANYCUBIC_TOKEN environment variable")
        return env_token.strip()

    # 2. Plugin config file
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                tok = cfg.get("token") or cfg.get("access_token")
                if tok and isinstance(tok, str):
                    logger.info("Using token from plugin config.json")
                    return tok.strip()
        except Exception as e:
            logger.warning(f"Error reading {CONFIG_PATH}: {e}")

    # 3. Check AnycubicSlicerNext.conf for plaintext token
    if os.path.exists(SLICER_NEXT_CONF):
        try:
            with open(SLICER_NEXT_CONF, "r", encoding="utf-8") as f:
                data = json.load(f)
                cloud = data.get("anycubic_cloud", {})
                if isinstance(cloud, dict):
                    tok = cloud.get("access_token")
                    if tok and isinstance(tok, str) and not tok.endswith("=="):
                        logger.info("Found plaintext token in AnycubicSlicerNext.conf")
                        return tok.strip()
        except Exception as e:
            logger.debug(f"Error reading AnycubicSlicerNext.conf: {e}")

    return None


def save_token(token, user_id=None, device_id=None):
    """Save token and optional identifiers to plugin config.json."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    cfg["token"] = token.strip()
    if user_id:
        cfg["user_id"] = user_id
    if device_id:
        cfg["device_id"] = device_id

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    logger.info(f"Token saved successfully to {CONFIG_PATH}")
