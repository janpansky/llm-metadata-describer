import yaml
import re
import sys
from pathlib import Path
from gooddata_sdk import GoodDataSdk
from typing import Optional, Dict, List
from llm_client import LLMClient
from prompt_utils import generate_prompt, extract_ids_from_visualization_object, extract_ids_from_dashboard
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def extract_ids_from_maql(maql: str) -> list:
    pattern = r'\b(fact|attribute|metric|label|dataset)/([a-zA-Z0-9_]+)\b'
    matches = re.findall(pattern, maql)
    return [f"{type_}/{id_}" for type_, id_ in matches]


class YAMLProcessor:
    def __init__(self, workspace_id: str, sdk: GoodDataSdk, llm_client: LLMClient, description_source: str,
                 root_path: Path, batch_size: int = 50):
        self.workspace_id = workspace_id
        self.sdk = sdk
        self.llm_client = llm_client
        self.description_source = description_source
        self.root_path = root_path
        self.batch_size = batch_size
        self.descriptions_dict = self.load_descriptions()

    def generate_descriptions(self, layout_root_path: Optional[Path] = Path.cwd()) -> None:
        self.store_current_layout(layout_root_path)
        self.process_files_in_batches(layout_root_path, 'date instance')
        self.process_files_in_batches(layout_root_path, 'dataset')
        self.process_files_in_batches(layout_root_path, 'non-metric')
        self.process_files_in_batches(layout_root_path, 'metric')
        self.process_files_in_batches(layout_root_path, 'visualization object')
        self.process_files_in_batches(layout_root_path, 'dashboard')
        self.save_descriptions()

    def process_files_in_batches(self, layout_root_path: Path, file_type: str) -> None:
        logger.info(f"Processing {file_type} files in batches...")
        file_paths = self.get_file_paths(layout_root_path, file_type)

        for i in range(0, len(file_paths), self.batch_size):
            batch = file_paths[i:i + self.batch_size]
            logger.info(f"Processing batch {i // self.batch_size + 1}: {len(batch)} files")
            for yaml_file in batch:
                self.process_file(yaml_file, file_type)

    def process_file(self, yaml_file: Path, file_type: str) -> None:
        data = self.load_yaml_file(yaml_file)
        if not data:
            return

        # Process dataset-level description
        self._update_element_description(data, 'dataset')

        # Process attributes, labels, and facts within the dataset
        if 'attributes' in data:
            for attribute in data['attributes']:
                self._update_element_description(attribute, 'attribute')

                # Process labels within attributes
                if 'labels' in attribute:
                    for label in attribute['labels']:
                        self._update_element_description(label, 'label')

        if 'facts' in data:
            for fact in data['facts']:
                self._update_element_description(fact, 'fact')

        self.save_yaml_file(yaml_file, data)

    def _update_element_description(self, element: dict, element_type: str) -> None:
        element_id = element.get('id')
        if element_id in self.descriptions_dict:
            element['description'] = self.descriptions_dict[element_id]
            logger.info(f"Applied existing description for {element_type} ID {element_id}: {element['description']}")
        else:
            prompt = generate_prompt(element, element_type, self.descriptions_dict)
            description = self.llm_client.call(prompt)
            if description and (element_type != "metric" or validate_metric_description(description)):
                element['description'] = description
                self.descriptions_dict[element_id] = description
                logger.info(f"Generated description for {element_type} ID {element_id}: {description}")
            else:
                logger.error(f"Invalid description generated for {element_type} ID {element_id}")

    def validate_metric_description(description: str) -> bool:
        return "dataset" not in description.lower()

    def get_file_paths(self, layout_root_path: Path, file_type: str) -> List[Path]:
        if file_type == 'date instance':
            return list(layout_root_path.glob('**/ldm/date_instances/*.yaml'))
        elif file_type == 'dataset':
            return list(layout_root_path.glob('**/ldm/datasets/*.yaml'))
        elif file_type == 'non-metric':
            return list(layout_root_path.glob('**/analytics_model/metrics/*.yaml'))
        elif file_type == 'metric':
            return list(layout_root_path.glob('**/analytics_model/metrics/*.yaml'))
        elif file_type == 'visualization object':
            return list(layout_root_path.glob('**/analytics_model/visualization_objects/*.yaml'))
        elif file_type == 'dashboard':
            return list(layout_root_path.glob('**/analytics_model/analytical_dashboards/*.yaml'))
        else:
            return []

    def store_current_layout(self, layout_root_path: Path) -> None:
        try:
            self.sdk.catalog_workspace.store_declarative_workspace(self.workspace_id, layout_root_path)
            logger.info("Workspace layout stored successfully.")
        except Exception as e:
            logger.error(f"Failed to store workspace layout: {e}")
            sys.exit(1)

    def load_yaml_file(self, yaml_file: Path) -> Optional[dict]:
        try:
            with open(yaml_file, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
            logger.debug(f"Loaded data from {yaml_file}: {data}")
            return data
        except Exception as e:
            logger.error(f"Failed to load YAML file {yaml_file}: {e}")
            return None

    def save_yaml_file(self, yaml_file: Path, data: dict) -> None:
        try:
            logger.debug(f"Data to be saved for {yaml_file}: {data}")
            with open(yaml_file, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, default_flow_style=False)
            logger.info(f"Successfully saved updated file: {yaml_file.resolve()}")
        except Exception as e:
            logger.error(f"Failed to save YAML file {yaml_file}: {e}")
            sys.exit(1)

    def update_metric_file(self, yaml_file: Path, data: dict) -> None:
        logger.info(f"Updating metric file: {yaml_file}")
        data = self.update_metric_description(data)
        self.save_yaml_file(yaml_file, data)

    def update_dataset_description(self, data: dict) -> dict:
        return self._update_description(data, description_type="dataset")

    def update_metric_description(self, data: dict) -> dict:
        return self._update_description(data, description_type="metric")

    def update_date_instance_description(self, data: dict) -> dict:
        return self._update_description(data, description_type="date instance")

    def update_visualization_object_description(self, data: dict) -> dict:
        return self._update_description(data, description_type="visualization object")

    def update_dashboard_description(self, data: dict) -> dict:
        return self._update_description(data, description_type="analytical dashboard")

    def _update_description(self, data: dict, description_type: str) -> dict:
        element_id = data.get('id')
        if not element_id:
            raise ValueError(f"Element ID is missing for {description_type}")

        if element_id in self.descriptions_dict:
            data['description'] = self.descriptions_dict[element_id]
            logger.debug(f"Skipped {description_type} description update for ID {element_id}, already present.")
            return data

        prompt = generate_prompt(data, description_type, self.descriptions_dict)
        logger.debug(f"Prompt for LLM: {prompt}")
        description = self.llm_client.call(prompt)
        logger.debug(f"Generated description: {description}")

        if not description:
            logger.error(f"Failed to generate a description for {description_type} ID {element_id}")
        else:
            data['description'] = description
            self.descriptions_dict[element_id] = description
            logger.info(f"Updated description for {description_type} ID {element_id}: {description}")

        return data

    def has_metric_references(self, maql: str) -> bool:
        referenced_ids = extract_ids_from_maql(maql)
        has_references = any(ref_id.startswith('metric/') for ref_id in referenced_ids)
        logger.debug(f"MAQL: {maql}, has metric references: {has_references}")
        return has_references

    def save_descriptions(self) -> None:
        descriptions_file = self.root_path / "descriptions.yaml"
        try:
            with open(descriptions_file, 'w', encoding='utf-8') as file:
                yaml.safe_dump(self.descriptions_dict, file, default_flow_style=False)
            logger.info(f"Descriptions saved to {descriptions_file}")
        except Exception as e:
            logger.error(f"Failed to save descriptions.yaml: {e}")
            sys.exit(1)

    def load_descriptions(self) -> dict:
        descriptions_file = self.root_path / "descriptions.yaml"
        if descriptions_file.exists():
            try:
                with open(descriptions_file, 'r', encoding='utf-8') as file:
                    descriptions = yaml.safe_load(file) or {}
                    logger.debug(f"Loaded descriptions: {descriptions}")
                    return descriptions
            except Exception as e:
                logger.error(f"Failed to load descriptions.yaml: {e}")
                return {}
        else:
            return {}


# Main execution script
if __name__ == "__main__":
    import logging
    from pathlib import Path
    from load_env import load_config
    from sdk_initialization import initialize_sdk
    from llm_client import LLMClient

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
            root_path=project_base_path
        )

        processor.generate_descriptions(layout_root_path=layout_root_path)

        logger.info("Descriptions Dictionary:")
        for element_id, description in processor.descriptions_dict.items():
            logger.info(f"{element_id}: {description}")


    main()
