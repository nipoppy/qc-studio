# QC-Studio Developer Quick Reference

Quick lookup for common development tasks, commands, and troubleshooting.

## Table of Contents
- [Running Tests](#running-tests)
- [Development Workflow](#development-workflow)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)
- [Code Organization](#code-organization)
- [Key Files & Locations](#key-files--locations)

---

## Running Tests

### Quick Test Commands

```bash
# All tests
bash run_tests.sh all

# Only new manager tests
pytest ui/tests/test_session_manager.py \
        ui/tests/test_panel_layout_manager.py \
        ui/tests/test_niivue_viewer_manager.py \
        ui/tests/test_constants.py -v

# Only model and utility tests
pytest ui/tests/test_models.py \
       ui/tests/test_utils.py -v

# With coverage report
pytest ui/tests/ --cov=ui --cov-report=html && open htmlcov/index.html

# Single test file
pytest ui/tests/test_session_manager.py -v

# Single test
pytest ui/tests/test_session_manager.py::TestSessionManagerInit::test_init_session_state_creates_defaults -v

# Stop on first failure
pytest ui/tests/ -x

# Show print statements
pytest ui/tests/ -v -s
```

### CI Test Script
```bash
#!/bin/bash
# run_tests.sh

case "$1" in
  all)
    pytest ui/tests/ -v
    ;;
  quick)
    pytest ui/tests/test_session_manager.py -v
    ;;
  coverage)
    pytest ui/tests/ --cov=ui --cov-report=html
    echo "Open htmlcov/index.html"
    ;;
esac
```

---

## Development Workflow

### Setting Up Environment

```bash
# Activate nipoppy_qc environment
conda activate nipoppy_qc

# Install test dependencies
pip install -r requirements-test.txt

# Verify environment
python -c "import pytest; print(pytest.__version__)"
```

### Making Code Changes

```bash
# 1. Make code changes
# 2. Run related tests
pytest ui/tests/test_<module>.py -v

# 3. Check coverage
pytest ui/tests/ --cov=ui --cov-report=term-missing

# 4. Run all tests before commit
bash run_tests.sh all

# 5. Commit with message
git commit -m "feat: description of change"
```

### Adding New Features

**Checklist**:
```
1. [ ] Implement feature
2. [ ] Write unit tests (test_<module>.py)
3. [ ] Write integration tests (test_<module>.py)
4. [ ] Run: pytest ui/tests/ -v
5. [ ] Check: pytest --cov=ui --cov-report=term-missing
6. [ ] Update: ARCHITECTURE.md if design changes
7. [ ] Run: bash run_tests.sh all (verify no regressions)
8. [ ] Commit
```

---

## Common Tasks

### Task: Add Constants

**File**: [constants.py](ui/constants.py)

```python
# 1. Add to appropriate section
MY_NEW_CONSTANT = "value"

# 2. Add test in test_constants.py
def test_my_new_constant(self):
    assert MY_NEW_CONSTANT == "value"

# 3. Run tests
pytest ui/tests/test_constants.py::TestNewConstant -v
```

### Task: Modify SessionManager

**File**: [ui/managers/session_manager.py](ui/managers/session_manager.py)

```python
# 1. Add new method
@staticmethod
def get_my_state():
    return st.session_state.get(SESSION_KEYS['my_key'], default_value)

# 2. Add initialization in init_session_state()
if SESSION_KEYS['my_key'] not in st.session_state:
    st.session_state[SESSION_KEYS['my_key']] = default_value

# 3. Add tests in test_session_manager.py
class TestMyNewMethods:
    def test_get_my_state_default(self, mock_session_state):
        # test code
    def test_set_and_get_my_state(self, mock_session_state):
        # test code

# 4. Run tests
pytest ui/tests/test_session_manager.py::TestMyNewMethods -v
```

### Task: Update UI Component

**File**: [ui/views/landing_page.py](ui/views/landing_page.py), [ui/components/qc_viewer.py](ui/components/qc_viewer.py), etc.

```python
# 1. Make changes
# 2. Run component tests
pytest ui/tests/ -v -s

# 3. Run full test suite
bash run_tests.sh all

# 4. Manually verify in Streamlit
streamlit run ui/app.py
```

### Task: Fix Failing Test

```bash
# 1. Run test with verbose output
pytest ui/tests/test_<module>.py::TestClass::test_method -v -s

# 2. Add debug output
print(f"Value: {value}")

# 3. Run again with -s flag to see print output
pytest ui/tests/test_<module>.py::TestClass::test_method -v -s

# 4. Or use debugger
# Add: import pdb; pdb.set_trace()
# Run: pytest ui/tests/test_<module>.py::TestClass::test_method -s
```

### Task: Check Code Quality

```bash
# Check for unused imports
pylint ui/*.py --disable=all --enable=W0611

# Or just run tests (they catch most issues)
pytest ui/tests/ -v

# Check type hints (if installed)
mypy ui/
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'ui.x'"

**Issue**: Import paths incorrect in tests

**Solution**: Use relative imports
```python
# ❌ Wrong
from ui.session_manager import SessionManager

# ✅ Correct (from tests directory context)
from session_manager import SessionManager
```

### "AssertionError: Expected 'title' to have been called"

**Issue**: Streamlit mock test failure

**Status**: Expected - pre-existing failures not from refactoring

**Note**: Not regressions - these are component-level UI tests with incomplete mocking

### "AttributeError: Mock object has no attribute 'x'"

**Issue**: Mock object incomplete

**Solution**: Check mock setup in conftest.py fixtures

```python
# Add to mock if needed
mock_session_state.get = MagicMock(return_value=default_value)
```

### "Test passes locally but fails in CI"

**Cause**: Environment differences

**Solution**:
1. Check Python version: `python --version` (should be 3.12+)
2. Check dependencies: `pip list` vs `requirements-test.txt`
3. Check paths: Use relative paths, not absolute

### "pytest: command not found"

**Issue**: Test dependencies not installed

**Solution**:
```bash
pip install -r requirements-test.txt
# or
pip install pytest pytest-cov
```

### "Too many open files" error

**Issue**: Test creates many fixtures without cleanup

**Solution**: Ensure test uses proper cleanup
```python
@pytest.fixture
def resource():
    r = create_resource()
    yield r
    r.close()  # Cleanup happens after test
```

---

## Code Organization

### Module Overview

```
ui/
├── app.py
├── main.py
├── constants.py
├── pages/
│   ├── 1_Landing_Page.py          # Sidebar → landing (calls views/)
│   └── 2_Congratulations_Page.py  # Sidebar → congratulations (calls views/)
├── views/
│   ├── landing_page.py             # Onboarding page (194 lines)
│   └── congratulations_page.py     # Results page (72 lines)
├── components/
│   ├── qc_viewer.py                # QC viewer orchestration (79 lines)
│   └── pagination.py               # Pagination controls (140 lines)
├── managers/
│   ├── session_manager.py          # Session state facade (155 lines)
│   ├── niivue_viewer_manager.py    # Viewer configuration (172 lines)
│   └── panel_layout_manager.py     # Layout management (139 lines)
├── models/
│   ├── __init__.py                 # Package exports
│   └── qc_models.py                # Pydantic models
├── utils/
│   ├── __init__.py                 # Package exports
│   ├── config.py                   # Configuration parsing
│   ├── data_loaders.py             # File I/O and loading
│   ├── image_processing.py         # Image utilities
│   └── export.py                   # Export utilities
└── tests/
    ├── conftest.py                 # Test fixtures
    ├── test_constants.py           # Constants tests (25 tests)
    ├── test_session_manager.py     # SessionManager tests (25 tests)
    ├── test_panel_layout_manager.py # PanelLayoutManager tests (20 tests)
    ├── test_niivue_viewer_manager.py # ViewerManager tests (19 tests)
    ├── test_models.py              # Model tests
    └── test_utils.py               # Utility tests
```

### Layer Architecture

```
┌─────────────────────────────────────┐
│     Entry Point Layer               │
│  app.py / main.py                   │  <-- Streamlit & CLI entry
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│     Page Layer (views/)             │
│  landing_page.py                    │  <-- Full-page views
│  congratulations_page.py            │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│     Component Layer (components/)   │
│  qc_viewer.py                       │  <-- Reusable components
│  pagination.py                      │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│     Manager Layer (managers/)       │
│  session_manager.py                 │  <-- Business logic
│  niivue_viewer_manager.py           │
│  panel_layout_manager.py            │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│     Utility & Model Layer           │
│  models/ (qc_models.py)             │  <-- Data models
│  utils/ (config, data_loaders, etc.)│  <-- Utilities
│  constants.py                       │  <-- Configuration
└─────────────────────────────────────┘
```

### Dependency Flow

```
app.py (entry)
  ├─→ views/
  │    ├─→ landing_page.py
  │    └─→ congratulations_page.py
  │
  ├─→ components/
  │    ├─→ qc_viewer.py
  │    └─→ pagination.py
  │
  ├─→ managers/
  │    ├─→ session_manager.py (state)
  │    ├─→ niivue_viewer_manager.py (config)
  │    └─→ panel_layout_manager.py (layout)
  │
  ├─→ models/qc_models.py (data)
  │
  └─→ utils/ (config, data_loaders, etc.)

NO CIRCULAR DEPENDENCIES ✓
```

---

## Key Files & Locations

### Entry Points
- [ui/app.py](ui/app.py) - Main Streamlit application
- [ui/main.py](ui/main.py) - CLI entry point
- [run_tests.sh](run_tests.sh) - Test runner script

### Pages (Full-Page Views)
- [ui/views/landing_page.py](ui/views/landing_page.py) - Onboarding and configuration
- [ui/views/congratulations_page.py](ui/views/congratulations_page.py) - Results display

### Components (Reusable UI)
- [ui/components/qc_viewer.py](ui/components/qc_viewer.py) - QC viewer orchestration
- [ui/components/pagination.py](ui/components/pagination.py) - Rating and pagination controls

### Managers (Business Logic)
- [ui/managers/session_manager.py](ui/managers/session_manager.py) - Session state management
- [ui/managers/niivue_viewer_manager.py](ui/managers/niivue_viewer_manager.py) - Viewer configuration
- [ui/managers/panel_layout_manager.py](ui/managers/panel_layout_manager.py) - Layout management

### Models & Utilities
- [ui/models/qc_models.py](ui/models/qc_models.py) - Pydantic data models
- [ui/utils/config.py](ui/utils/config.py) - Configuration parsing
- [ui/utils/data_loaders.py](ui/utils/data_loaders.py) - File I/O and data loading
- [ui/utils/image_processing.py](ui/utils/image_processing.py) - Image utilities
- [ui/utils/export.py](ui/utils/export.py) - Export utilities

### Configuration
- [ui/constants.py](ui/constants.py) - Global constants and messages
- [requirements.txt](requirements.txt) - Runtime dependencies
- [requirements-test.txt](requirements-test.txt) - Test dependencies

### Tests
- [ui/tests/conftest.py](ui/tests/conftest.py) - Test fixtures
- [ui/tests/test_session_manager.py](ui/tests/test_session_manager.py) - SessionManager tests (25 tests)
- [ui/tests/test_panel_layout_manager.py](ui/tests/test_panel_layout_manager.py) - Layout tests (20 tests)
- [ui/tests/test_niivue_viewer_manager.py](ui/tests/test_niivue_viewer_manager.py) - Viewer tests (19 tests)
- [ui/tests/test_constants.py](ui/tests/test_constants.py) - Constants tests (25 tests)
- [ui/tests/test_models.py](ui/tests/test_models.py) - Model tests
- [ui/tests/test_utils.py](ui/tests/test_utils.py) - Utility tests

### Documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - Complete architecture guide
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing practices and patterns
- [DEVELOPER_QUICKREF.md](DEVELOPER_QUICKREF.md) - This file!

---

## Git Workflow

### Branch Setup
```bash
# Clone and get on right branch
git clone <repo>
cd qc-studio
git checkout pagination  # or your branch

# Set up environment
conda activate nipoppy_qc
pip install -r requirements-test.txt
```

### Making Changes
```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
# ... edit files ...

# Test
bash run_tests.sh all

# Commit
git add .
git commit -m "feat: clear description of change"

# Push
git push origin feature/my-feature

# Create PR on GitHub
```

### Testing Before Commit
```bash
# Always run this before committing
bash run_tests.sh all

# Or individually:
pytest ui/tests/test_session_manager.py -v
pytest ui/tests/test_panel_layout_manager.py -v
pytest ui/tests/test_niivue_viewer_manager.py -v
pytest ui/tests/test_constants.py -v
pytest ui/tests/ -v
```

---

## Performance Tips

### Slow Tests?
```bash
# See which tests are slowest
pytest ui/tests/ --durations=10

# Parallelization (if installed)
pip install pytest-xdist
pytest ui/tests/ -n auto  # Uses all CPUs
```

### Slow Streamlit App?
```bash
# Profile the app
streamlit run ui/app.py --logger.level=debug

# Check component rendering time
# Look at SessionManager method times
# Check NiivueViewerManager overlay building
```

---

## Success Checklist

Before marking work as complete:

- [ ] Code compiles without errors
- [ ] All new code has comments
- [ ] Unit tests pass locally
- [ ] Full test suite passes: `bash run_tests.sh all`
- [ ] No regressions (67 original tests still pass)
- [ ] Coverage report looks good: `pytest --cov=ui`
- [ ] Code follows project patterns
- [ ] Related documentation updated
- [ ] PR description is clear
- [ ] No console errors when running Streamlit app

---

## Getting Help

**Quick Questions**: Check this file first!

**Code Questions**: 
- See [ARCHITECTURE.md](ARCHITECTURE.md) for design overview
- See [TESTING_GUIDE.md](TESTING_GUIDE.md) for testing patterns
- Check similar code in existing modules

**Test Failures**:
```bash
pytest <test_file> -v -s  # See full output
pytest <test_file> -v --tb=long  # Detailed traceback
```

**Module Documentation**:
```python
from session_manager import SessionManager
help(SessionManager.set_rater_id)  # View docstring
```

---

## Summary

**Key Commands**:
- `bash run_tests.sh all` - Run all tests
- `pytest ui/tests/test_<module>.py -v` - Run specific test file
- `pytest --cov=ui --cov-report=html` - Generate coverage report
- `streamlit run ui/app.py` - Run app locally

**Key Files**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - Understand the system
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Learn testing patterns
- [constants.py](ui/constants.py) - Find configuration
- [session_manager.py](ui/session_manager.py) - Use session state

**Remember**:
1. Always run tests before committing
2. No circular dependencies
3. 156+ tests passing = reliable code
4. ARCHITECTURE.md is your friend
5. One thing per test = clear failures
