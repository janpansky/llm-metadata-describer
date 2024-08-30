import os
import sys
import yaml
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def load_config(config_file: str = "config.yaml") -> Dict[str, str]:
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    required_keys = ["hostname", "api_token", "llm_api_token", "workspace_id", "layout_root_directory"]
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        logger.error(f"Missing configuration keys: {', '.join(missing_keys)}")
        sys.exit(1)

    return config
