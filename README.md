# QC-Studio

QC-Studio is a web-based quality control (QC) application for neuroimaging data. It gives raters one place to look at raw BIDS data, processed pipeline derivatives, and image quality metrics (IQMs), assign a structured QC decision with optional notes, and export the result as a tab-separated table. See the [Overview](docs/source/overview/overview.md) for the design and vocabulary.

[See design overview →](docs/source/development/dev_plan.md)

## 🎯 Goals

- Create an interactive web app to visualize neuroimaging data - raw and processed!
- Support multiple image types: 3D MRI (NIfTI), 2D image montages, and IQM metrics
- Enable structured quality control ratings through a clean, intuitive interface

## 📚 Documentation

| Document | Purpose | Audience |
|----------|---------|----------|
| [architecture.md](docs/source/development/architecture.md) | Complete architecture overview | All |
| [dev_plan.md](docs/source/development/dev_plan.md) | Product scope and design overview | Contributors |
| [ui/tests/README.md](ui/tests/README.md) | Test suite usage and testing patterns | Developers |
| [SCanD QC guidelines](https://github.com/TIGRLab/SCanD_project/tree/Fir/docs) | Pipeline QC pass/fail criteria (fMRIPrep, FreeSurfer, QSIPrep, XCP-D, NODDIreg) | Raters / supervisors |

## 🚀 Quick Start

Requires **Python 3.10+** and **[uv](https://github.com/astral-sh/uv)** (recommended). The traditional pip/venv path is covered in the [Installation guide](docs/source/overview/installation.md).

```bash
# Clone the repository
git clone https://github.com/nipoppy/qc-studio.git
cd qc-studio

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt

# Install niivue-streamlit component
uv pip install --index-url https://test.pypi.org/simple/ --no-deps niivue-streamlit

# Run the app
streamlit run ui/main.py
```

To see QC-Studio end to end with a bundled demo (`./fmriprep_demo.sh`), follow the [Quickstart](docs/source/overview/quickstart.md). For full installation instructions, see [Installation](docs/source/overview/installation.md).

## 📄 License

See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please:

1. Read the [architecture.md](docs/source/development/architecture.md) for design patterns
2. Check [ui/tests/README.md](ui/tests/README.md) for testing practices
3. Follow the code organization described above
4. Set up the development tooling as described [here](docs/source/overview/installation.md#developer-setup)
5. Ensure all tests pass before submitting PR

Before pushing, run all pre-commit checks. This includes the same UI test command used in CI.

```bash
pre-commit run --all-files
```

## ❓ Support

For issues, questions, or suggestions open an issue on GitHub with detailed description
