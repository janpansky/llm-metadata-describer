import os
import sys
import requests
import yaml
from pathlib import Path
from typing import Optional, Callable

from gooddata_sdk import GoodDataSdk


# Utility function to load environment variables
def load_env_variables() -> dict:
    env_vars = {
        "HOSTNAME": os.getenv('HOSTNAME'),
        "API_TOKEN": os.getenv('API_TOKEN'),
        "LLM_API_TOKEN": os.getenv('LLM_API_TOKEN')
    }

    missing_vars = [k for k, v in env_vars.items() if not v]
    if missing_vars:
        print(f"Error: Missing environment variables: {', '.join(missing_vars)}")
        sys.exit()

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
            sys.exit()

        response_data = response.json()
        return response_data['choices'][0]['message']['content'].strip()


# YAML Processor
class YAMLProcessor:
    def __init__(self, workspace_id: str, sdk: GoodDataSdk, llm_client: LLMClient, description_source: str):
        self.workspace_id = workspace_id
        self.sdk = sdk
        self.llm_client = llm_client
        self.description_source = description_source
        self.descriptions_dict = {}

    def generate_descriptions(self, layout_root_path: Optional[Path] = None, store_layouts: bool = False,
                              load_layouts: bool = False) -> None:
        workspace_folder = self.create_workspace_folder(layout_root_path)

        if store_layouts:
            self.store_current_layout(workspace_folder)

        self.process_yaml_files(workspace_folder)

        if load_layouts:
            self.load_workspace_from_disk(workspace_folder)

    def create_workspace_folder(self, layout_root_path: Optional[Path]) -> Path:
        if layout_root_path:
            workspace_folder = layout_root_path
        else:
            workspace_folder = Path.cwd() / "workspaces" / self.workspace_id
        workspace_folder.mkdir(parents=True, exist_ok=True)
        return workspace_folder

    def store_current_layout(self, workspace_folder: Path) -> None:
        workspace_content = self.sdk.catalog_workspace.get_declarative_workspace(self.workspace_id)
        workspace_content.store_to_disk(workspace_folder)

    def process_yaml_files(self, workspace_folder: Path) -> None:
        for yaml_file in workspace_folder.glob('ldm/datasets/*.yaml'):
            self.update_yaml_file(yaml_file)
            # if yaml_file.name == "customer.yaml":  # Process only the customer.yaml file
            #     print(f"Processing {yaml_file}")
            #     self.update_yaml_file(yaml_file)
            #     break

    def update_yaml_file(self, yaml_file: Path) -> None:
        with open(yaml_file, 'r') as file:
            data = yaml.safe_load(file)

        data = self.update_labels(data)
        data = self.update_attributes(data)
        data = self.update_facts(data)
        data = self.update_global_description(data)

        with open(yaml_file, 'w') as file:
            yaml.safe_dump(data, file, default_flow_style=False)

    def update_labels(self, data: dict) -> dict:
        for item in data.get('attributes', []):
            if 'labels' in item:
                for label in item['labels']:
                    label['description'] = self.generate_description(label)
        for item in data.get('facts', []):
            if 'labels' in item:
                for label in item['labels']:
                    label['description'] = self.generate_description(label)
        return data

    def update_attributes(self, data: dict) -> dict:
        for attribute in data.get('attributes', []):
            attribute['description'] = self.generate_description(attribute)
        return data

    def update_facts(self, data: dict) -> dict:
        for fact in data.get('facts', []):
            fact['description'] = self.generate_description(fact)
        return data

    def update_global_description(self, data: dict) -> dict:
        if 'description' in data:
            data['description'] = self.generate_global_description(data)
        return data

    def generate_description(self, element: dict) -> str:
        element_id = element.get('id')
        if not element_id:
            raise ValueError("Element ID is missing")

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
        elif self.description_source == 'disk':
            description = self.load_description_from_disk(element)
        else:
            description = "No description available"

        self.descriptions_dict[element_id] = description  # Store in global dictionary
        return description

    def generate_global_description(self, element: dict) -> str:
        element_id = element.get('id')
        if not element_id:
            raise ValueError("Element ID is missing")

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

    @staticmethod
    def load_description_from_disk(element: dict) -> str:
        description_file = Path('descriptions') / f"{element.get('title')}.txt"
        if description_file.exists():
            with open(description_file, 'r') as file:
                return file.read().strip()
        return "Description not found"

    def load_workspace_from_disk(self, workspace_folder: Path) -> None:
        # Assuming CatalogDeclarativeWorkspaceModel is properly defined elsewhere
        CatalogDeclarativeWorkspaceModel.load_from_disk(workspace_folder)


# Main function to orchestrate the workflow
def main():
    env_vars = load_env_variables()

    sdk = initialize_sdk(env_vars['HOSTNAME'], env_vars['API_TOKEN'])
    llm_client = LLMClient(api_token=env_vars['LLM_API_TOKEN'])

    processor = YAMLProcessor(
        workspace_id="dev",
        sdk=sdk,
        llm_client=llm_client,
        description_source='api'  # Change to 'disk' to use descriptions from disk
    )

    processor.generate_descriptions(
        store_layouts=True,
        load_layouts=False,
    )
    # Output the global dictionary containing all descriptions
    print("Descriptions Dictionary:")
    for element_id, description in processor.descriptions_dict.items():
        print(f"{element_id}: {description}")

    print(processor.descriptions_dict)


if __name__ == "__main__":
    main()
