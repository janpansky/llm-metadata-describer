import os
import sys
import yaml
import logging
from dotenv import load_dotenv
from typing import Dict

logger = logging.getLogger(__name__)


def load_config() -> Dict[str, str]:
    """
    Loads environment variables from .env and returns a config dictionary.
    Secrets and runtime config are now sourced from environment variables, not YAML.
    """
    load_dotenv()  # Loads from .env by default
    config = {
        'hostname': os.environ.get('GOODDATA_HOSTNAME'),
        'api_token': os.environ.get('GOODDATA_API_TOKEN'),
        'llm_api_token': os.environ.get('LLM_API_TOKEN'),
        'workspace_id': os.environ.get('WORKSPACE_ID'),
        'layout_root_directory': os.environ.get('LAYOUT_ROOT_DIRECTORY', 'workspace_layout_directory'),
        'enable_load_workspace': os.environ.get('ENABLE_LOAD_WORKSPACE', 'true').lower() in ('true', '1', 'yes')
    }

    required_keys = ["hostname", "api_token", "llm_api_token", "workspace_id", "layout_root_directory"]
    missing_keys = [key for key in required_keys if key not in config or config[key] is None]

    if missing_keys:
        logger.error(f"Missing configuration keys: {', '.join(missing_keys)}")
        sys.exit(1)

    return config
