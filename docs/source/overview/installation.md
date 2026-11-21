# Installation

## Requirements

| | |
|---|---|
| **Python** | 3.10 or newer |
| **Git** | any recent version |
| **Browser** | required to interact with the app once it is running |
| **OS** | macOS or Linux |

## Get the code

```bash
git clone https://github.com/nipoppy/qc-studio.git
cd qc-studio
```

## Create an environment

### Option A — `uv` (recommended)

```bash
uv venv
source .venv/bin/activate
uv pip install ".[niivue]"
```

### Option B — `pip` and `venv`

```bash
python3 -m venv .venv
source .venv/bin/activate
# pip 25.1+ is required for `pip install --group` (see Developer setup)
python -m pip install --upgrade pip
pip install .
pip install --index-url https://test.pypi.org/simple/ --no-deps niivue-streamlit
```

## Verify the installation

```bash
python ui/main.py --help
```

## Upgrading

```bash
git pull

# uv
uv pip install ".[niivue]"

# pip
pip install .
pip install --index-url https://test.pypi.org/simple/ --no-deps niivue-streamlit
```

## Developer setup

```bash
# uv
uv pip install ".[niivue]" --group dev

# pip
pip install --group dev

pre-commit install
```

### Building the documentation locally

```bash
make -C docs html
```

The built site is written to `docs/_build/html`. To view it, open `docs/_build/html/index.html`
in a web browser, or serve it locally and browse to `http://localhost:8000`:

```bash
python -m http.server 8000 --directory docs/_build/html
```

Re-run `make -C docs html` and refresh the page after editing the docs.

## Next steps

Proceed to the [Quickstart](quickstart.md) to run a demo, or read [Configuration](../guides/configuration.md) first if you want to understand the flags.
