import logging
from pathlib import Path
from load_env import load_config
from sdk_initialization import initialize_sdk
from llm_client import LLMClient
from yaml_processor import YAMLProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


if __name__ == "__main__":
    main()
