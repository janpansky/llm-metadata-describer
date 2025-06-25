# LLM Metadata Describer

A tool for describing and managing metadata for LLM (Large Language Model) projects. It processes YAML configuration and description files to generate, manage, and utilize metadata for LLM-driven workflows.

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
├── workspace_layout_directory/ # (Optional) Workspace layouts
├── .gitignore                 # Git ignore rules
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
   *(Add a `requirements.txt` if not present)*

## Usage
Run the main script:
```sh
python main.py
```

## Configuration
- Edit `config.yaml` for project-specific settings.
- Edit `descriptions.yaml` to add or modify metadata entries.

## Notes
- The `workspace_layout_directory/` is ignored by default; include it in git only if it contains essential, non-generated data.
- Ensure your API keys or secrets are not committed to git.

## License
Specify your license here.