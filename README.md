# GoodData - LLM powered metadata describer

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A tool for describing and managing metadata for GoodData LLM (Large Language Model) projects. It processes YAML configuration and description files to generate, manage, and utilize metadata for GoodData LLM-driven workflows.

---

## Features
- Reads and processes YAML metadata files
- Provides utilities for LLM-based description generation
- Configurable via `config.yaml`
- Modular Python codebase

## Project Structure
```
llm-metadata-describer/
├── config.yaml                # Main configuration file
├── descriptions.yaml          # Main metadata/description data
├── lmm_descriptor.py          # Core logic for LLM metadata description
├── llm_client.py              # LLM client utilities
├── main.py                    # Main entry point
├── prompt_utils.py            # Prompt and text utilities
├── sdk_initialization.py      # SDK setup
├── utils.py                   # General utilities
├── yaml_processor.py          # YAML file processing
├── workspace_layout_directory/ # (Optional) Workspace layouts (see below)
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Setup
1. Clone the repository:
   ```sh
   git clone <repo-url>
   cd llm-metadata-describer
   ```
2. Create and activate a virtual environment:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Copy the provided `.env` file and fill in your own secrets (do **not** commit this file to git):
   ```sh
   cp .env .env.local  # or edit .env directly if not versioned
   # Edit .env/.env.local and set your GOODDATA_API_TOKEN, LLM_API_TOKEN, etc.
   ```

## Usage
### Basic
To process and describe all entities, use the following command:
```sh
python main.py
```
This is the only supported entry point. All configured entities in your YAML/config will be processed and described automatically. No command-line arguments are required or supported.

Internally, `main.py` uses the `YAMLProcessor` class and supporting functions defined in `llm_descriptor.py` to perform the metadata description workflow. You should not run or modify `llm_descriptor.py` directly—use it only as a module.

## Configuration
- **`config.yaml`**: Main configuration file for API keys, model settings, workspace ID, and other options. You must edit this file to provide your GoodData instance hostname, API tokens, workspace ID, and other relevant settings before running the project. Example fields include:
  - `hostname`: GoodData Cloud instance URL
  - `api_token`: API token for GoodData SDK authentication
  - `llm_api_token`: Token for the LLM client
  - `workspace_id`: Target workspace identifier
  - `layout_root_directory`: Path to your workspace layout directory
  - `enable_load_workspace`: Set to `true` to enable workspace loading

- **`descriptions.yaml`**: Contains the metadata entities (datasets, metrics, dashboards, etc.) to be processed or described by the tool. Edit this file to add or update the entities for which you want to generate or improve descriptions. The tool will read and update this file as part of its workflow.

## Workspace Layout Directory
- The `workspace_layout_directory/` is **ignored by default** in git. If it contains essential, non-generated data, remove it from `.gitignore` and commit it.
- If it is generated or contains large data, keep it ignored to avoid bloating the repository.

---

## API/LLM Query Cost and Caching Behavior

### Query Estimation
- The tool will make **one LLM API call per entity** (domain: dataset, metric, dashboard, etc.) that does not already have a filled description in `descriptions.yaml`.
- For a typical workspace, this means:
  - **Datasets:** 10–100+ (one per dataset)
  - **Metrics:** 20–200+ (one per metric)
  - **Dashboards/Visualizations:** 5–50+ (one per dashboard or visualization object)
- The total number of API calls = sum of all entities missing descriptions. If all descriptions are already filled, **no LLM API calls will be made**.

### Cost Implications
- Each LLM API call may incur cost depending on your provider (e.g., OpenAI, Azure, etc.).
- For large workspaces, costs can add up if many entities lack descriptions. For small workspaces or incremental runs, costs are minimal.
- **Tip:** To minimize cost, run the tool once to fill all missing descriptions. On subsequent runs, only new or updated entities will trigger additional LLM API calls.

### Caching Behavior
- Once a description is generated and stored in `descriptions.yaml`, it is **not processed again** on future runs unless you clear or edit that description.
- This ensures efficient, cost-effective operation and avoids redundant LLM usage.

## Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.