# qc-studio

Prototyping repo for creating visual QC workflow that can be integrated with Nipoppy. [See design overview here](dev_plan.md).

## Goals 
- Create a web-app to visualize pipeline output including reports, svg / png images, and 3D MRI files
- Pre-define a set of files in a `<pipeline-name>_qc.json` config file that will be visualized in the web-app

## Installation
These instructions show how to create a Python virtual environment and install the project's runtime dependencies.

Prerequisites
- Python 3.10+ (3.12 tested in CI/DEV environment)

Create and activate a virtual environment

```bash
# from the project root
python3 -m venv .venv
source .venv/bin/activate

# upgrade packaging tools (recommended)
python -m pip install --upgrade pip setuptools wheel
```

Install dependencies

```bash
# Install core dependencies
pip install -e .

# Or install with optional LLM dependencies for testing llava
pip install -e .[llava]
```

Install niivue-streamlit component 

```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps niivue-streamlit
```

Run example workflow (uses files from sample_data)

```bash
cd ui
./fmriprep_test.sh
```
