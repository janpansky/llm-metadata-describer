import os
import sys
import requests
import yaml
from pathlib import Path
from typing import Optional

from gooddata_sdk import GoodDataSdk
from gooddata_sdk.catalog.workspace.declarative_model.workspace.workspace import CatalogDeclarativeWorkspaceModel


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


class YAMLProcessor:
    def __init__(self, workspace_id: str, sdk: GoodDataSdk, llm_client: LLMClient, description_source: str):
        self.workspace_id = workspace_id
        self.sdk = sdk
        self.llm_client = llm_client
        self.description_source = description_source
        self.descriptions_dict = {}

    def generate_descriptions(self, layout_root_path: Optional[Path] = Path.cwd(), store_layouts: bool = False,
                              load_layouts: bool = False) -> None:
        if load_layouts:
            # Load the workspace layout from disk and skip storing layouts and description generation
            print(f"Loading workspace from path: {layout_root_path}")
            self.load_workspace(layout_root_path)
            print("Workspace loaded successfully. Skipping layout storage and description generation.")
            return  # Skip further processing

        if store_layouts:
            # Store the current workspace layout
            self.store_current_layout(layout_root_path)

        # Process YAML files and generate descriptions if not loading layouts
        self.process_yaml_files(layout_root_path)

    def store_current_layout(self, layout_root_path: Path) -> None:
        # Store the current workspace layout to disk
        self.sdk.catalog_workspace.store_declarative_workspace(self.workspace_id, layout_root_path)

    def load_workspace(self, layout_root_path: Path) -> None:
        print(f"Attempting to load workspace layout from: {layout_root_path}")

        try:
            if not layout_root_path.is_dir():
                raise FileNotFoundError(f"Path {layout_root_path} does not exist or is not a directory.")

            workspace_layout = self.sdk.catalog_workspace.load_declarative_workspace(self.workspace_id,
                                                                                     layout_root_path)
            print(f"Workspace layout loaded successfully: {workspace_layout}")

            self.sdk.catalog_workspace.put_declarative_workspace(
                workspace_id=self.workspace_id,
                workspace=workspace_layout
            )
            print("Workspace layout saved successfully.")

        except Exception as e:
            print(f"Failed to load workspace layout: {e}")
            sys.exit()

    def process_yaml_files(self, layout_root_path: Path) -> None:
        for yaml_file in layout_root_path.glob('**/ldm/datasets/*.yaml'):
            self.update_yaml_file(yaml_file)

    def update_yaml_file(self, yaml_file: Path) -> None:
        print(f"Processing YAML file: {yaml_file}")

        # Load existing data
        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        print("Original data:", data)  # Debug print

        # Update data
        data = self.update_labels(data)
        data = self.update_attributes(data)
        data = self.update_facts(data)
        data = self.update_global_description(data)

        print("Data to be written:", data)  # Debug print

        print(f"Writing to: {yaml_file.resolve()}")
        print(f"File exists: {os.path.exists(yaml_file)}")
        print(f"File writable: {os.access(yaml_file, os.W_OK)}")
        print(f"File permissions: {oct(os.stat(yaml_file).st_mode)}")
        directory = yaml_file.parent
        print(f"Directory writable: {os.access(directory, os.W_OK)}")

        # Check if data actually changed
        if data != yaml.safe_load(yaml_file.read_text()):
            print("Data has changed, writing to file...")

            with open(yaml_file, 'w', encoding='utf-8') as file:
                yaml.safe_dump(data, file, default_flow_style=False)

            # Verify that the file was written correctly
            written_data = yaml.safe_load(yaml_file.read_text())
            print("Data actually written to file:", written_data)
        else:
            print("Data has not changed, skipping file write.")

    def update_labels(self, data: dict) -> dict:
        for attribute in data.get('attributes', []):
            if 'labels' in attribute:
                for label in attribute['labels']:
                    original_description = label.get('description')
                    new_description = self.generate_description(label)
                    if original_description != new_description:
                        label['description'] = new_description
                        print(f"Updated label description from '{original_description}' to '{new_description}'")
        return data

    def update_attributes(self, data: dict) -> dict:
        for attribute in data.get('attributes', []):
            original_description = attribute.get('description')
            new_description = self.generate_description(attribute)
            if original_description != new_description:
                attribute['description'] = new_description
                print(f"Updated attribute description from '{original_description}' to '{new_description}'")
        return data

    def update_facts(self, data: dict) -> dict:
        for fact in data.get('facts', []):
            original_description = fact.get('description')
            new_description = self.generate_description(fact)
            if original_description != new_description:
                fact['description'] = new_description
                print(f"Updated fact description from '{original_description}' to '{new_description}'")
        return data

    def update_global_description(self, data: dict) -> dict:
        if 'description' in data:
            original_description = data.get('description')
            new_description = self.generate_global_description(data)
            if original_description != new_description:
                data['description'] = new_description
                print(f"Updated global description from '{original_description}' to '{new_description}'")
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


def main():
    env_vars = load_env_variables()

    sdk = initialize_sdk(env_vars['HOSTNAME'], env_vars['API_TOKEN'])
    llm_client = LLMClient(api_token=env_vars['LLM_API_TOKEN'])

    # Define the project base path
    project_base_path = Path(__file__).parent
    layout_root_path = project_base_path / "workspace_layout_directory"

    processor = YAMLProcessor(
        workspace_id="prod",
        sdk=sdk,
        llm_client=llm_client,
        description_source='api'
    )

    processor.generate_descriptions(
        layout_root_path=layout_root_path,
        store_layouts=False,
        load_layouts=True,
    )

    print("Descriptions Dictionary:")
    for element_id, description in processor.descriptions_dict.items():
        print(f"{element_id}: {description}")


if __name__ == "__main__":
    main()
