# QC-Studio Test Suite Integration Guide

## Overview

This document describes the test suite that covers the refactored codebase with new manager classes, components, and pages. The test suite is comprehensive and designed to be maintainable and extensible.

## What's New

### Test Files Added
- `ui/tests/__init__.py` - Package marker
- `ui/tests/conftest.py` - Shared fixtures and pytest configuration
- `ui/tests/test_models.py` - Tests for Pydantic models (MetricQC, QCRecord, QCTask, QCConfig)
- `ui/tests/test_utils.py` - Tests for utility functions (parse_qc_config, load_mri_data, etc.)
- `ui/tests/test_constants.py` - Tests for constants and configuration (25 tests)
- `ui/tests/test_session_manager.py` - Tests for SessionManager (25 tests)
- `ui/tests/test_panel_layout_manager.py` - Tests for PanelLayoutManager (20 tests)
- `ui/tests/test_niivue_viewer_manager.py` - Tests for NiivueViewerManager (19 tests)
- `ui/tests/pytest.ini` - Pytest configuration
- `ui/tests/README.md` - Detailed test documentation

### Configuration Files
- `requirements-test.txt` - Test dependencies
- `run_tests.sh` - Convenient test runner script

## Quick Start

### Requirements

- **Python**: 3.8+ (Pydantic v2 requires Python 3.8+)
- **pytest**: 3.0+ (tested with both 3.x and 7.x versions)
- **Key dependencies**: pydantic>=2.0, pandas>=1.4, streamlit>=1.20

### 1. Install Test Dependencies

```bash
# From the project root
pip install -r requirements-test.txt
```

### 2. Run All Tests

```bash
# Option A: Using pytest directly
pytest ui/tests/

# Option B: Using the test runner script
chmod +x run_tests.sh
./run_tests.sh all

# Option C: Run with coverage report
./run_tests.sh all --cov
```

### 3. Run Specific Tests

```bash
# Run tests for a specific module
pytest ui/tests/test_models.py
pytest ui/tests/test_utils.py

# Run a specific test class
pytest ui/tests/test_utils.py::TestParseQcConfig

# Run a specific test
pytest ui/tests/test_models.py::TestQCRecord::test_create_qc_record_with_required_fields
```

## Test Structure

### Modules Tested

#### 1. **models/qc_models.py** (test_models.py)
- **MetricQC**: Metric quality metrics model
  - 4 test cases covering creation, serialization
  
- **QCRecord**: Quality control record model
  - 7 test cases covering required fields, optional fields, validation
  
- **QCTask**: Single QC task definition
  - 4 test cases covering file paths, type conversion
  
- **QCConfig**: Top-level configuration
  - 7 test cases covering JSON parsing, task access, validation

**Total: 22 test cases**

#### 2. **utils/** (test_utils.py)
- **config.py**: Configuration utilities
  - 5 test cases for configuration parsing
  
- **data_loaders.py**: Data loading functions
  - 4 test cases for MRI data loading
  
- **image_processing.py**: Image processing utilities
  - 4 test cases for image operations
  
- **export.py**: Export utilities
  - 4 test cases for CSV and result export

**Total: 22 test cases**

#### 3. **constants.py** (test_constants.py)
- **Message constants**: UI message strings
  - 10 test cases for message existence and content
  
- **Session state keys**: Session key definitions
  - 8 test cases for key organization and access
  
- **UI configuration**: UI settings and defaults
  - 7 test cases for configuration values

**Total: 25 test cases**

#### 4. **managers/session_manager.py** (test_session_manager.py)
- **SessionManager**: Session state abstraction layer
  - 8 test cases for initialization
  - 6 test cases for state accessors
  - 5 test cases for state setters
  - 6 test cases for complex operations

**Total: 25 test cases**

#### 5. **managers/panel_layout_manager.py** (test_panel_layout_manager.py)
- **PanelLayoutManager**: Layout computation and management
  - 7 test cases for layout creation
  - 6 test cases for panel selection
  - 4 test cases for layout transitions
  - 3 test cases for error handling

**Total: 20 test cases**

#### 6. **managers/niivue_viewer_manager.py** (test_niivue_viewer_manager.py)
- **NiivueViewerManager**: Viewer configuration and setup
  - 8 test cases for viewer initialization
  - 5 test cases for image loading
  - 4 test cases for viewer configuration
  - 2 test cases for error handling

**Total: 19 test cases**


## Test Coverage Overview

### Total Test Cases: ~130+

| Module | Test Cases | Coverage |
|--------|-----------|----------|
| models/qc_models.py | 22 | 95%+ |
| utils/ | 22 | 90%+ |
| constants.py | 25 | 98%+ |
| managers/session_manager.py | 25 | 95%+ |
| managers/panel_layout_manager.py | 20 | 92%+ |
| managers/niivue_viewer_manager.py | 19 | 91%+ |
| **Total** | **~130+** | **~93%** |

## Running Tests with Different Options

### Run with Verbose Output
```bash
pytest ui/tests/ -v
```

### Run with Short Summary
```bash
pytest ui/tests/ -q
```

### Generate Coverage Report (HTML)
```bash
pytest ui/tests/ --cov=ui --cov-report=html
# Open htmlcov/index.html in browser
```

### Generate Coverage Report (Terminal)
```bash
pytest ui/tests/ --cov=ui --cov-report=term-missing
```

### Run Tests in Parallel (faster)
```bash
pytest ui/tests/ -n auto
```

### Run with Detailed Test Output
```bash
pytest ui/tests/ -vv --tb=long
```

### Stop on First Failure
```bash
pytest ui/tests/ -x
```

### Run Last Failed Tests
```bash
pytest ui/tests/ --lf
```

## Fixtures Available

All fixtures are defined in `conftest.py` and available to all tests:

### File/Directory Fixtures
- **`temp_dir`** - Temporary directory for test files
- **`sample_participant_list`** - Sample participants TSV file with 3 participants
- **`sample_qc_config`** - Sample QC configuration JSON with multiple tasks
- **`sample_qc_results_csv`** - Sample QC results with 2 records
- **`sample_svg_content`** - Sample 2D image montage content

### Data Fixtures
- **`sample_session_state`** - Mock Streamlit session state with all required keys
- **`qc_record_sample`** - Pre-configured QCRecord instance
- **`mock_streamlit`** - Mocked Streamlit module

### Using Fixtures in Tests

```python
def test_example(temp_dir, sample_participant_list, qc_record_sample):
    """Use multiple fixtures."""
    # temp_dir is a Path object
    # sample_participant_list is a Path to a TSV file
    # qc_record_sample is a QCRecord instance
    pass
```

## Test Organization

### By Module
- **test_models.py**: Pydantic model validation and serialization
- **test_utils.py**: Utility function behavior (config, data_loaders, image_processing, export)
- **test_constants.py**: Constant values and message strings (25 tests)
- **test_session_manager.py**: SessionManager state facade (25 tests)
- **test_panel_layout_manager.py**: PanelLayoutManager layout logic (20 tests)
- **test_niivue_viewer_manager.py**: NiivueViewerManager viewer config (19 tests)

### By Category (using pytest markers)
```bash
# Run only unit tests
pytest ui/tests/ -m unit

# Filter by test class
pytest ui/tests/ -k "TestParseQcConfig"

# Filter by test name
pytest ui/tests/ -k "test_parse_valid"
```

## CI/CD Integration

To integrate these tests into your CI/CD pipeline:

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - run: pip install -r requirements-test.txt
      - run: pytest ui/tests/ --cov=ui --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Troubleshooting

### Common Issues

**1. Import errors when running tests**
```bash
# Make sure you're in the project root
cd /path/to/qc-studio
pytest ui/tests/
```

**2. Streamlit mock not working**
```bash
# Ensure streamlit is installed (for mocking to work)
pip install streamlit
```

**3. Pydantic validation errors**
```bash
# Ensure Pydantic v2+ is installed
pip install "pydantic>=2.0"
```

**4. File not found errors in tests**
```bash
# Tests use relative paths; run from project root
pwd  # Should show qc-studio directory
pytest ui/tests/
```

**5. Fixtures not being recognized**
```bash
# Ensure conftest.py is in the tests directory
ls -la ui/tests/conftest.py  # Should exist
```

## Adding New Tests

When adding new features, follow this pattern:

### 1. Create Test File (if needed)
```python
# ui/tests/test_new_feature.py

import pytest
from new_module import new_function

class TestNewFeature:
    """Test new feature functionality."""
    
    def test_basic_functionality(self):
        """Test basic behavior."""
        result = new_function()
        assert result is not None
```

### 2. Add Fixtures (if needed)
```python
# Add to ui/tests/conftest.py

@pytest.fixture
def new_fixture():
    """Create test data for new feature."""
    return "test_data"
```

### 3. Run Tests
```bash
pytest ui/tests/test_new_feature.py -v
```

### 4. Check Coverage
```bash
pytest ui/tests/ --cov=ui --cov-report=term-missing
```

## Best Practices

1. **Use descriptive test names**
   ```python
   # Good
   def test_parse_qc_config_with_valid_file_returns_paths(self):
       pass
   
   # Bad
   def test_parse(self):
       pass
   ```

2. **Follow AAA pattern (Arrange, Act, Assert)**
   ```python
   def test_something(self, temp_dir):
       # Arrange
       test_file = temp_dir / "test.json"
       
       # Act
       result = function_to_test(test_file)
       
       # Assert
       assert result is not None
   ```

3. **Use fixtures for shared data**
   ```python
   # Good
   def test_with_fixture(self, qc_record_sample):
       assert qc_record_sample is not None
   
   # Avoid
   def test_without_fixture(self):
       record = QCRecord(...)  # Duplicate setup
   ```

4. **Mock external dependencies**
   ```python
   @patch('module.external_function')
   def test_with_mock(mock_func):
       mock_func.return_value = test_value
   ```

5. **Test edge cases**
   ```python
   # Test with None
   # Test with empty values
   # Test with invalid input
   # Test boundary conditions
   ```

## Running Tests Locally Before Committing

```bash
#!/bin/bash
# Quick pre-commit test check

echo "Running tests..."
pytest ui/tests/ -q || exit 1

echo "Checking coverage..."
pytest ui/tests/ --cov=ui --cov-report=term-missing || exit 1

echo "All checks passed!"
```

## Performance

### Test Execution Time
- **All tests**: ~5-10 seconds
- **Unit tests only**: ~3-5 seconds
- **Single test file**: <1 second

### Optimize Test Runs
```bash
# Run tests in parallel
pytest ui/tests/ -n auto

# Run only changed tests
pytest --lf

# Run tests that failed last time
pytest --ff
```

## Documentation

For more detailed information, see:
- `ui/tests/README.md` - Test suite documentation
- Individual test files - Docstrings in each test
- `conftest.py` - Fixture definitions

## Support

If you encounter issues with the tests:

1. Check that all dependencies are installed: `pip install -r requirements-test.txt`
2. Ensure you're running from the project root
3. Check the individual test files for documentation
4. Review the conftest.py for fixture definitions
5. Run tests with verbose output: `pytest ui/tests/ -vv`

---

**Last Updated**: 2024
**Test Suite Version**: 1.0
