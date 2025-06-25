import yaml
import re
from pathlib import Path
from gooddata_sdk import GoodDataSdk
from typing import Optional, Dict
from llm_client import LLMClient
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def extract_ids_from_maql(maql: str) -> list:
    pattern = r'\b(fact|attribute|metric|label|dataset)/([a-zA-Z0-9_]+)\b'
    matches = re.findall(pattern, maql)
    return [f"{type_}/{id_}" for type_, id_ in matches]


def extract_ids_from_visualization_object(content: dict) -> list:
    identifiers = []
    for bucket in content.get('buckets', []):
        for item in bucket.get('items', []):
            measure = item.get('measure', {})
            definition = measure.get('definition', {})
            if 'measureDefinition' in definition:
                identifiers.append(measure['definition']['measureDefinition']['item']['identifier']['id'])
            elif 'previousPeriodMeasure' in definition:
                for date_dataset in definition['previousPeriodMeasure']['dateDataSets']:
                    identifiers.append(date_dataset['dataSet']['identifier']['id'])
                identifiers.append(definition['previousPeriodMeasure']['measureIdentifier'])

    for filter_item in content.get('filters', []):
        if 'relativeDateFilter' in filter_item:
            identifiers.append(filter_item['relativeDateFilter']['dataSet']['identifier']['id'])

    return identifiers


def extract_ids_from_dashboard(layout: dict) -> list:
    identifiers = []
    for section in layout.get('sections', []):
        for item in section.get('items', []):
            widget = item.get('widget', {})
            insight = widget.get('insight', {})
            if 'identifier' in insight:
                identifiers.append(insight['identifier']['id'])

    return identifiers


class YAMLProcessor:
    def __init__(self, workspace_id: str, sdk: GoodDataSdk, llm_client: LLMClient, description_source: str,
                 root_path: Path):
        self.workspace_id = workspace_id
        self.sdk = sdk
        self.llm_client = llm_client
        self.description_source = description_source
        self.root_path = root_path
        self.descriptions_dict = self.load_descriptions()

    def generate_descriptions(self, layout_root_path: Optional[Path] = Path.cwd()) -> None:
        self.store_current_layout(layout_root_path)
        self.process_date_instance_files(layout_root_path)
        self.process_dataset_files(layout_root_path)
        self.process_non_metric_files(layout_root_path)
        self.process_metric_files(layout_root_path)
        self.process_visualization_object_files(layout_root_path)
        self.process_dashboard_files(layout_root_path)
        self.save_descriptions()

    def store_current_layout(self, layout_root_path: Path) -> None:
        try:
            self.sdk.catalog_workspace.store_declarative_workspace(self.workspace_id, layout_root_path)
            logger.info("Workspace layout stored successfully.")
        except Exception as e:
            logger.error(f"Failed to store workspace layout: {e}")
            sys.exit(1)

    def process_date_instance_files(self, layout_root_path: Path) -> None:
        logger.info("Processing date instance files...")
        for yaml_file in layout_root_path.glob('**/ldm/date_instances/*.yaml'):
            data = self.load_yaml_file(yaml_file)
            if not data:
                continue

            element_id = data.get('id')
            logger.debug(f"Processing date instance with ID: {element_id}")

            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                logger.info(f"Applied existing description for date instance ID {element_id}: {data['description']}")
            else:
                logger.info(f"Generating description for date instance ID {element_id}.")
                data = self.update_date_instance_description(data)

            self.save_yaml_file(yaml_file, data)

    def process_dataset_files(self, layout_root_path: Path) -> None:
        logger.info("Processing dataset files...")
        for yaml_file in layout_root_path.glob('**/ldm/datasets/*.yaml'):
            data = self.load_yaml_file(yaml_file)
            if not data:
                continue

            element_id = data.get('id')
            logger.debug(f"Processing dataset with ID: {element_id}")

            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                logger.info(f"Applied existing description for dataset ID {element_id}: {data['description']}")
            else:
                logger.info(f"Generating description for dataset ID {element_id}.")
                data = self.update_dataset_description(data)

            self.save_yaml_file(yaml_file, data)

    def process_non_metric_files(self, layout_root_path: Path) -> None:
        logger.info("Processing non-metric dependent metric files...")
        for yaml_file in layout_root_path.glob('**/analytics_model/metrics/*.yaml'):
            data = self.load_yaml_file(yaml_file)
            if not data:
                continue

            maql = data.get('content', {}).get('maql', '')
            element_id = data.get('id')
            logger.debug(f"Processing metric with ID: {element_id}")

            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                logger.info(f"Applied existing description for metric ID {element_id}: {data['description']}")
            else:
                if not self.has_metric_references(maql):
                    logger.info(f"Generating description for non-metric dependent metric ID {element_id}.")
                    self.update_metric_file(yaml_file, data)

            self.save_yaml_file(yaml_file, data)

    def process_metric_files(self, layout_root_path: Path) -> None:
        logger.info("Processing metric-dependent metric files...")
        for yaml_file in layout_root_path.glob('**/analytics_model/metrics/*.yaml'):
            data = self.load_yaml_file(yaml_file)
            if not data:
                continue

            maql = data.get('content', {}).get('maql', '')
            element_id = data.get('id')
            logger.debug(f"Processing metric with ID: {element_id}")

            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                logger.info(f"Applied existing description for metric ID {element_id}: {data['description']}")
            else:
                if self.has_metric_references(maql):
                    logger.info(f"Generating description for metric-dependent metric ID {element_id}.")
                    self.update_metric_file(yaml_file, data)

            self.save_yaml_file(yaml_file, data)

    def process_visualization_object_files(self, layout_root_path: Path) -> None:
        logger.info("Processing visualization object files...")
        for yaml_file in layout_root_path.glob('**/analytics_model/visualization_objects/*.yaml'):
            data = self.load_yaml_file(yaml_file)
            if not data:
                continue

            element_id = data.get('id')
            logger.debug(f"Processing visualization object with ID: {element_id}")

            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                logger.info(
                    f"Applied existing description for visualization object ID {element_id}: {data['description']}")
            else:
                logger.info(f"Generating description for visualization object ID {element_id}.")
                data = self.update_visualization_object_description(data)

            self.save_yaml_file(yaml_file, data)

    def process_dashboard_files(self, layout_root_path: Path) -> None:
        logger.info("Processing analytical dashboard files...")
        for yaml_file in layout_root_path.glob('**/analytics_model/analytical_dashboards/*.yaml'):
            data = self.load_yaml_file(yaml_file)
            if not data:
                continue

            element_id = data.get('id')
            logger.debug(f"Processing dashboard with ID: {element_id}")

            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                logger.info(f"Applied existing description for dashboard ID {element_id}: {data['description']}")
            else:
                logger.info(f"Generating description for dashboard ID {element_id}.")
                data = self.update_dashboard_description(data)

            self.save_yaml_file(yaml_file, data)

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

        prompt = self._generate_prompt(data, description_type)
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

    def _generate_prompt(self, data: dict, description_type: str) -> str:
        if description_type == "metric":
            maql = data.get('content', {}).get('maql', '')
            format_ = data.get('content', {}).get('format', '')
            return (
                f"Generate a descriptive text for a {description_type} with business meaning for ecommerce-solution "
                f"so I can find it with various similarity search algorithms. "
                f"Do not describe the fields themselves. "
                f"Without any single or double quotes in the beginning and at the end "
                f"The documentation must fit into 256 characters based on the following details:\n"
                f"Title: {data.get('title')}\n"
                f"ID: {data.get('id')}\n"
                f"MAQL: {maql}\n"
                f"Format: {format_}\n"
            )
        elif description_type == "visualization object":
            content = data.get('content', {})
            visualization_url = data.get('visualizationUrl', '')
            title = data.get('title', '')
            extracted_ids = extract_ids_from_visualization_object(content)
            context = "\n".join(
                [f"{id_}: {self.descriptions_dict.get(id_, 'No description available')}" for id_ in extracted_ids])

            return (
                f"Generate a descriptive text for a {description_type} with business meaning for ecommerce-solution "
                f"so I can find it with various similarity search algorithms. "
                f"Do not describe the fields themselves. "
                f"Without any single or double quotes in the beginning and at the end "
                f"The documentation must fit into 256 characters based on the following details:\n"
                f"Title: {title}\n"
                f"ID: {data.get('id')}\n"
                f"Visualization URL: {visualization_url}\n"
                f"Context:\n{context}\n"
            )
        elif description_type == "analytical dashboard":
            layout = data.get('layout', {})
            title = data.get('title', '')
            extracted_ids = extract_ids_from_dashboard(layout)
            context = "\n".join(
                [f"{id_}: {self.descriptions_dict.get(id_, 'No description available')}" for id_ in extracted_ids])

            return (
                f"Generate a descriptive text for an {description_type} with business meaning for ecommerce-solution "
                f"so I can find it with various similarity search algorithms. "
                f"Do not describe the fields themselves. "
                f"Without any single or double quotes in the beginning and at the end "
                f"The documentation must fit into 256 characters based on the following details:\n"
                f"Title: {title}\n"
                f"ID: {data.get('id')}\n"
                f"Context:\n{context}\n"
            )
        else:
            return (
                f"Generate a descriptive text with business meaning for a {description_type} in an ecommerce solution. "
                f"Do not describe the fields themselves. "
                f"Without any single or double quotes in the beginning and at the end "
                f"The documentation must fit into 256 characters based on the following details:\n"
                f"Title: {data.get('title')}\n"
                f"ID: {data.get('id')}\n"
            )

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


