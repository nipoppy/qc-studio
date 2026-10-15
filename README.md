# QC-Studio

QC-Studio is a web-based quality control (QC) application for neuroimaging data. It gives raters a unified, portable interface (i.e. a web browser) to review raw imaging data, processed pipeline derivatives, and image quality metrics (IQMs), and export ratings as a tab-separated table. See [Why QC-Studio](docs/source/overview/why_qc-studio.md) for the motivation and vocabulary.

[See design overview →](docs/source/development/design_reqs.md)

## 🎯 Goals

- Create an interactive web app to visualize neuroimaging data - raw and processed!
- Support multiple image types: 3D MRI (NIfTI), 2D image montages, and IQM metrics
- Enable structured quality control ratings through a clean, intuitive interface

## 📚 Documentation

| Document | Purpose | Audience |
|----------|---------|----------|
| [architecture.md](docs/source/development/architecture.md) | Software architecture: code modules and data flow | All |
| [design_reqs.md](docs/source/development/design_reqs.md) | Design requirements | Contributors |
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

# Run the bundled fMRIPrep demo, then open http://localhost:8501
./fmriprep_demo.sh
```

See the [Quickstart](docs/source/overview/quickstart.md) for a walkthrough of the demo, and [Configuration](docs/source/guides/configuration.md) to run QC-Studio on your own data. For full installation instructions, see [Installation](docs/source/overview/installation.md).

## 📄 License

See the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please:

1. Read the [architecture.md](docs/source/development/architecture.md) for design patterns
2. Check [ui/tests/README.md](ui/tests/README.md) for testing practices
3. Set up the development tooling as described [here](docs/source/overview/installation.md#developer-setup)
4. Ensure all tests pass before submitting PR

Before pushing, run all pre-commit checks. This includes the same UI test command used in CI.

```bash
pre-commit run --all-files
```

## ❓ Support

For issues, questions, or suggestions open an issue on GitHub with detailed description
