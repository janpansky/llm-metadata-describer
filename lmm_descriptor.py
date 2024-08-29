import os
import sys
import re
import requests
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from gooddata_sdk import GoodDataSdk


# Utility function to load environment variables
def load_env_variables() -> Dict[str, str]:
    env_vars = {
        "HOSTNAME": os.getenv('HOSTNAME'),
        "API_TOKEN": os.getenv('API_TOKEN'),
        "LLM_API_TOKEN": os.getenv('LLM_API_TOKEN')
    }

    missing_vars = [k for k, v in env_vars.items() if not v]
    if missing_vars:
        print(f"Error: Missing environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    return env_vars


# Initialize GoodData SDK
def initialize_sdk(hostname: str, api_token: str) -> GoodDataSdk:
    return GoodDataSdk.create(hostname, api_token)


# LLM API Client
class LLMClient:
    def __init__(self, api_token: str, model: str = "gpt-4o-mini"):
        self.api_token = api_token
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def call(self, prompt: str, max_tokens: int = 150) -> str:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        response = requests.post(self.api_url, headers=headers, json=data)

        if response.status_code != 200:
            print(f"Error: Received status code {response.status_code} from OpenAI API.")
            print(f"Response: {response.text}")
            sys.exit(1)

        response_data = response.json()
        return response_data['choices'][0]['message']['content'].strip()


class YAMLProcessor:
    def __init__(self, workspace_id: str, sdk: GoodDataSdk, llm_client: LLMClient, description_source: str,
                 root_path: Path):
        self.workspace_id = workspace_id
        self.sdk = sdk
        self.llm_client = llm_client
        self.description_source = description_source
        self.root_path = root_path
        self.descriptions_dict = self.load_descriptions()

    def generate_descriptions(self, layout_root_path: Optional[Path] = Path.cwd(), store_layouts: bool = False,
                              load_layouts: bool = False) -> None:
        if load_layouts:
            self.load_workspace(layout_root_path)
            print("Workspace loaded successfully. Skipping layout storage and description generation.")
            return

        if store_layouts:
            self.store_current_layout(layout_root_path)

        self.process_yaml_files(layout_root_path)
        self.save_descriptions()

    def store_current_layout(self, layout_root_path: Path) -> None:
        try:
            self.sdk.catalog_workspace.store_declarative_workspace(self.workspace_id, layout_root_path)
            print(f"Workspace layout stored successfully.")
        except Exception as e:
            print(f"Failed to store workspace layout: {e}")
            sys.exit(1)

    def load_workspace(self, layout_root_path: Path) -> None:
        if not layout_root_path.is_dir():
            print(f"Error: Path {layout_root_path} does not exist or is not a directory.")
            sys.exit(1)

        try:
            workspace_layout = self.sdk.catalog_workspace.load_declarative_workspace(self.workspace_id,
                                                                                     layout_root_path)
            self.sdk.catalog_workspace.put_declarative_workspace(
                workspace_id=self.workspace_id,
                workspace=workspace_layout
            )
            print(f"Workspace layout loaded and saved successfully.")
        except Exception as e:
            print(f"Failed to load workspace layout: {e}")
            sys.exit(1)

    def process_yaml_files(self, layout_root_path: Path) -> None:
        for yaml_file in layout_root_path.glob('**/ldm/datasets/*.yaml'):
            self.update_yaml_file(yaml_file)

        for yaml_file in layout_root_path.glob('**/ldm/date_instances/*.yaml'):
            self.update_date_instance_file(yaml_file)

        for yaml_file in layout_root_path.glob('**/analytics_model/metrics/*.yaml'):
            self.update_metric_file(yaml_file)

    def update_yaml_file(self, yaml_file: Path) -> None:
        print(f"Processing YAML file: {yaml_file}")

        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        data = self.update_labels(data)
        data = self.update_attributes(data)
        data = self.update_facts(data)
        data = self.update_global_description(data)

        if data != yaml.safe_load(yaml_file.read_text()):
            with open(yaml_file, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, default_flow_style=False)
            print(f"Updated file: {yaml_file.resolve()}")
        else:
            print(f"No changes detected in file: {yaml_file.resolve()}")

    def update_date_instance_file(self, yaml_file: Path) -> None:
        print(f"Processing date instance file: {yaml_file}")

        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        data = self.update_date_instance_description(data)

        if data != yaml.safe_load(yaml_file.read_text()):
            with open(yaml_file, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, default_flow_style=False)
            print(f"Updated file: {yaml_file.resolve()}")
        else:
            print(f"No changes detected in file: {yaml_file.resolve()}")

    def update_metric_file(self, yaml_file: Path) -> None:
        print(f"Processing metric file: {yaml_file}")

        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        data = self.update_metric_description(data)

        if data != yaml.safe_load(yaml_file.read_text()):
            with open(yaml_file, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, default_flow_style=False)
            print(f"Updated file: {yaml_file.resolve()}")
        else:
            print(f"No changes detected in file: {yaml_file.resolve()}")

    def update_labels(self, data: dict) -> dict:
        for attribute in data.get('attributes', []):
            if 'labels' in attribute:
                for label in attribute['labels']:
                    element_id = label.get('id')
                    if element_id in self.descriptions_dict:
                        label['description'] = self.descriptions_dict[element_id]
                        print(f"Skipped label description update for ID {element_id}, already present.")
                    else:
                        original_description = label.get('description')
                        new_description = self.generate_description(label)
                        if original_description != new_description:
                            label['description'] = new_description
                            print(f"Updated label description from '{original_description}' to '{new_description}'")
        return data

    def update_attributes(self, data: dict) -> dict:
        for attribute in data.get('attributes', []):
            element_id = attribute.get('id')
            if element_id in self.descriptions_dict:
                attribute['description'] = self.descriptions_dict[element_id]
                print(f"Skipped attribute description update for ID {element_id}, already present.")
            else:
                original_description = attribute.get('description')
                new_description = self.generate_description(attribute)
                if original_description != new_description:
                    attribute['description'] = new_description
                    print(f"Updated attribute description from '{original_description}' to '{new_description}'")
        return data

    def update_facts(self, data: dict) -> dict:
        for fact in data.get('facts', []):
            element_id = fact.get('id')
            if element_id in self.descriptions_dict:
                fact['description'] = self.descriptions_dict[element_id]
                print(f"Skipped fact description update for ID {element_id}, already present.")
            else:
                original_description = fact.get('description')
                new_description = self.generate_description(fact)
                if original_description != new_description:
                    fact['description'] = new_description
                    print(f"Updated fact description from '{original_description}' to '{new_description}'")
        return data

    def update_global_description(self, data: dict) -> dict:
        if 'description' in data:
            element_id = data.get('id')
            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                print(f"Skipped global description update for ID {element_id}, already present.")
            else:
                original_description = data.get('description')
                new_description = self.generate_global_description(data)
                if original_description != new_description:
                    data['description'] = new_description
                    print(f"Updated global description from '{original_description}' to '{new_description}'")
        return data

    def update_date_instance_description(self, data: dict) -> dict:
        if 'description' in data:
            element_id = data.get('id')
            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                print(f"Skipped date instance description update for ID {element_id}, already present.")
            else:
                original_description = data.get('description')
                new_description = self.generate_date_instance_description(data)
                if original_description != new_description:
                    data['description'] = new_description
                    print(f"Updated date instance description from '{original_description}' to '{new_description}'")
        return data

    def update_metric_description(self, data: dict) -> dict:
        if 'description' in data:
            element_id = data.get('id')
            if element_id in self.descriptions_dict:
                data['description'] = self.descriptions_dict[element_id]
                print(f"Skipped metric description update for ID {element_id}, already present.")
            else:
                original_description = data.get('description')
                new_description = self.generate_metric_description(data)
                if original_description != new_description:
                    data['description'] = new_description
                    print(f"Updated metric description from '{original_description}' to '{new_description}'")
        return data

    def generate_description(self, element: dict) -> str:
        element_id = element.get('id')
        if not element_id:
            raise ValueError("Element ID is missing")

        if element_id in self.descriptions_dict:
            return self.descriptions_dict[element_id]

        if self.description_source == 'api':
            prompt = (f"Generate a global descriptive text with business meaning for ecommerce-solution "
                      f"so I can find it with various similarity search algorithms "
                      f"do not describe the fields itself "
                      f"as a clean text, without any quotes in the beginning and end of the sentence "
                      f"The documentation must fit into 128 characters "
                      f"based on the following details:\n"
                      f"Title: {element.get('title')}\n"
                      f"Source Column: {element.get('sourceColumn')}\n"
                      f"Data Type: {element.get('sourceColumnDataType')}\n"
                      f"Tags: {', '.join(element.get('tags', []))}\n"
                      f"Value Type: {element.get('valueType', 'N/A')}\n")
            description = self.llm_client.call(prompt)
        else:
            description = "No description available"

        self.descriptions_dict[element_id] = description  # Store in global dictionary
        return description

    def generate_global_description(self, element: dict) -> str:
        element_id = element.get('id')
        if not element_id:
            raise ValueError("Element ID is missing")

        if element_id in self.descriptions_dict:
            return self.descriptions_dict[element_id]

        prompt = (f"Generate a global descriptive text with business meaning for ecommerce-solution "
                  f"so I can find it with various similarity search algorithms "
                  f"do not describe the fields itself "
                  f"as a clean text, without any quotes in the beginning and end of the sentence "
                  f"The documentation must fit into 256 characters "
                  f"based on the following details:\n"
                  f"Title: {element.get('title')}\n"
                  f"Existing Description: {element.get('description', '')}\n"
                  f"Details: {element}\n")
        description = self.llm_client.call(prompt)

        self.descriptions_dict[element_id] = description  # Store in global dictionary
        return description

    def generate_date_instance_description(self, data: dict) -> str:
        element_id = data.get('id')
        if not element_id:
            raise ValueError("Element ID is missing")

        if element_id in self.descriptions_dict:
            return self.descriptions_dict[element_id]

        prompt = (f"Generate a global descriptive text with business meaning for ecommerce-solution "
                  f"so I can find it with various similarity search algorithms "
                  f"do not describe the fields itself "
                  f"as a clean text, without any quotes in the beginning and end of the sentence "
                  f"The documentation must fit into 128 characters "
                  f"based on the following details:\n"
                  f"Title: {data.get('title')}\n"
                  f"ID: {element_id}\n"
                  f"Granularities: {', '.join(data.get('granularities', []))}\n"
                  f"Granularities Formatting: {data.get('granularitiesFormatting')}\n")
        description = self.llm_client.call(prompt)

        self.descriptions_dict[element_id] = description
        return description

    def generate_metric_description(self, data: dict) -> str:
        element_id = data.get('id')
        if not element_id:
            raise ValueError("Element ID is missing")

        if element_id in self.descriptions_dict:
            return self.descriptions_dict[element_id]

        maql = data.get('content', {}).get('maql', '')
        format_ = data.get('content', {}).get('format', '')

        referenced_ids = self.extract_ids_from_maql(maql)

        context = []
        for ref_id in referenced_ids:
            if ref_id.startswith('metric/'):
                if ref_id not in self.descriptions_dict:
                    referenced_metric_data = self.load_metric_data(ref_id)  # Load data for the referenced metric
                    self.generate_metric_description(referenced_metric_data)

                ref_description = self.descriptions_dict.get(ref_id, 'No description available')
            else:
                ref_description = self.descriptions_dict.get(ref_id, 'No description available')
            context.append(f"Reference ID {ref_id}: {ref_description}")

        context_str = "\n".join(context)

        prompt = (f"Generate a descriptive text for a metric with business meaning for ecommerce-solution "
                  f"so I can find it with various similarity search algorithms "
                  f"do not describe the fields itself "
                  f"as a clean text, without any quotes in the beginning and end of the sentence "
                  f"The documentation must fit into 256 characters "
                  f"based on the following details:\n"
                  f"Title: {data.get('title')}\n"
                  f"ID: {element_id}\n"
                  f"Description Context:\n{context_str}\n"
                  f"MAQL: {maql}\n"
                  f"Format: {format_}\n")
        description = self.llm_client.call(prompt)

        self.descriptions_dict[element_id] = description
        return description

    def extract_ids_from_maql(self, maql: str) -> list:
        pattern = r'\b(fact|attribute|metric|label|dataset)/([a-zA-Z0-9_]+)\b'
        matches = re.findall(pattern, maql)
        return [f"{type}/{id}" for type, id in matches]

    def load_metric_data(self, metric_id: str) -> dict:
        metric_file = self.find_metric_file_by_id(metric_id, self.root_path)
        with open(metric_file, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def find_metric_file_by_id(self, metric_id: str, root_path: Path) -> Path:
        metric_filename = f"{metric_id.split('/')[-1]}.yaml"

        for metric_file_path in root_path.rglob(f"analytics_model/metrics/{metric_filename}"):
            if metric_file_path.exists():
                return metric_file_path

        raise FileNotFoundError(f"Metric file for ID {metric_id} not found in {root_path}.")

    def save_descriptions(self) -> None:
        descriptions_file = self.root_path / "descriptions.yaml"
        with open(descriptions_file, 'w', encoding='utf-8') as file:
            yaml.safe_dump(self.descriptions_dict, file, default_flow_style=False)
        print(f"Descriptions saved to {descriptions_file}")

    def load_descriptions(self) -> dict:
        descriptions_file = self.root_path / "descriptions.yaml"
        if descriptions_file.exists():
            with open(descriptions_file, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        else:
            return {}


def main():
    env_vars = load_env_variables()

    sdk = initialize_sdk(env_vars['HOSTNAME'], env_vars['API_TOKEN'])
    llm_client = LLMClient(api_token=env_vars['LLM_API_TOKEN'])

    project_base_path = Path(__file__).parent
    layout_root_path = project_base_path / "workspace_layout_directory"

    processor = YAMLProcessor(
        workspace_id="prod",
        sdk=sdk,
        llm_client=llm_client,
        description_source='api',
        root_path=project_base_path
    )

    processor.generate_descriptions(
        layout_root_path=layout_root_path,
        store_layouts=False,
        load_layouts=False,
    )

    print("Descriptions Dictionary:")
    for element_id, description in processor.descriptions_dict.items():
        print(f"{element_id}: {description}")


if __name__ == "__main__":
    main()
