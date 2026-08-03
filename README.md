# QC-Studio

A web-based quality control (QC) application for neuroimaging data. QC-Studio allows raters to visualize and assess MRI data, SVG montages, and IQM metrics in an interactive Streamlit interface.

[See design overview →](docs/DEV_PLAN.md)

## 🎯 Goals

- Create an interactive web app to visualize neuroimaging data - raw and processed! 
- Support multiple image types: 3D MRI (NIfTI), SVG montages, and IQM metrics
- Enable structured quality control ratings through a clean, intuitive interface

## 📚 Documentation

| Document | Purpose | Audience |
|----------|---------|----------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Complete architecture overview | All |
| [DEV_PLAN.md](docs/DEV_PLAN.md) | Product scope and design overview | Contributors |
| [ui/tests/README.md](ui/tests/README.md) | Test suite usage and testing patterns | Developers |
| [SCanD QC guidelines](https://github.com/TIGRLab/SCanD_project/tree/Fir/docs) | Pipeline QC pass/fail criteria (fMRIPrep, FreeSurfer, QSIPrep, XCP-D, NODDIreg) | Raters / supervisors |

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.10+ (3.12 tested in CI/DEV environment)
- **pip/venv** OR **[uv](https://github.com/astral-sh/uv)** (recommended for faster installs)

### Option A: Using uv (Recommended - Fastest)

```bash
# Clone the repository
git clone https://github.com/nipoppy/qc-studio.git
cd qc-studio

# Create and activate virtual environment with uv
uv venv

# Activate the environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies with uv
uv pip install -r requirements.txt

# Install niivue-streamlit component
uv pip install --index-url https://test.pypi.org/simple/ --no-deps niivue-streamlit
```

### Option B: Using pip & venv (Traditional)

```bash
# Clone the repository
git clone https://github.com/nipoppy/qc-studio.git
cd qc-studio

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip setuptools wheel

# Install runtime dependencies
pip install -r requirements.txt

# Install niivue-streamlit component
pip install --index-url https://test.pypi.org/simple/ --no-deps niivue-streamlit
```

### Run the Application

```bash
# Run the web app
streamlit run ui/app.py

# Or use the CLI entry point
python ui/main.py --help
```

### Try the Demo (Optional)

```bash
# Test with sample fMRIPrep data
cd ui
./fmriprep_test.sh
```

## 🔗 Related Projects

- [Nipoppy](https://github.com/nipoppy/nipoppy) - Lightweight framework for standardized organization and processing of neuroimaging-clinical datasets.
- [NiiVue](https://github.com/niivue/niivue) - 3D medical image viewer
- [Streamlit](https://streamlit.io/) - Python web app framework

## 📄 License

See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please:

1. Read the [ARCHITECTURE.md](docs/ARCHITECTURE.md) for design patterns
2. Check [ui/tests/README.md](ui/tests/README.md) for testing practices
3. Follow the code organization described above
4. Ensure all tests pass before submitting PR

Install the development checks once per clone:

```bash
python -m pip install -r requirements-test.txt
pre-commit install
```

Run every pre-commit check manually:

```bash
pre-commit run --all-files
```

## ❓ Support

For issues, questions, or suggestions open an issue on GitHub with detailed description
