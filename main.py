import logging
from pathlib import Path
from load_env import load_config
from sdk_initialization import initialize_sdk
from llm_client import LLMClient
from yaml_processor import YAMLProcessor
from gooddata_sdk import GoodDataSdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_workspace(layout_root_path: Path, workspace_id: str, sdk: GoodDataSdk, enable_load: bool = True) -> None:
    if not enable_load:
        logger.info("Loading workspace is disabled by configuration.")
        return

    logger.info(f"Attempting to load workspace layout from: {layout_root_path}")

    try:
        if not layout_root_path.is_dir():
            raise FileNotFoundError(f"Path {layout_root_path} does not exist or is not a directory.")

        workspace_layout = sdk.catalog_workspace.load_declarative_workspace(workspace_id, layout_root_path)
        logger.info("Workspace layout loaded successfully.")

        sdk.catalog_workspace.put_declarative_workspace(workspace_id=workspace_id, workspace=workspace_layout)
        logger.info("Workspace layout saved successfully.")

    except FileNotFoundError as fnf_error:
        logger.error(f"File not found error: {fnf_error}")
        return  # Continue with the next steps without exiting

    except Exception as e:
        logger.error(f"Failed to load workspace layout: {e}")
        return  # Continue with the next steps without exiting


def main():
    config = load_config()

    sdk = initialize_sdk(config['hostname'], config['api_token'])
    llm_client = LLMClient(api_token=config['llm_api_token'])

    project_base_path = Path(__file__).parent
    layout_root_directory = config.get('layout_root_directory', 'workspace_layout_directory')  # Use default value
    layout_root_path = project_base_path / layout_root_directory

    processor = YAMLProcessor(
        workspace_id=config['workspace_id'],
        sdk=sdk,
        llm_client=llm_client,
        description_source='api',
        root_path=project_base_path,
        batch_size=50  # Adjust the batch size as needed
    )

    processor.generate_descriptions(layout_root_path=layout_root_path)

    logger.info("Descriptions Dictionary:")
    for element_id, description in processor.descriptions_dict.items():
        logger.info(f"{element_id}: {description}")

    # Check if loading the workspace should be enabled
    enable_load = config.get('enable_load_workspace', True)

    # Load the workspace if enabled
    load_workspace(layout_root_path, config['workspace_id'], sdk, enable_load=enable_load)


if __name__ == "__main__":
    main()
