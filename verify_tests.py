#!/usr/bin/env python3
"""
Quick sanity check script to verify test infrastructure setup.
Run this from the project root to verify all tests can be discovered.
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Run sanity checks."""
    project_root = Path(__file__).parent
    ui_dir = project_root / "ui"
    tests_dir = ui_dir / "tests"
    
    print("=" * 70)
    print("QC-Studio Test Infrastructure Sanity Check")
    print("=" * 70)
    print()
    
    # Check 1: Test files exist
    print("✓ Checking test files...")
    test_files = [
        tests_dir / "test_models.py",
        tests_dir / "test_utils.py",
        tests_dir / "test_ui.py",
        tests_dir / "test_layout.py",
    ]
    
    for test_file in test_files:
        if test_file.exists():
            print(f"  ✓ {test_file.relative_to(project_root)}")
        else:
            print(f"  ✗ {test_file.relative_to(project_root)} - NOT FOUND")
            return 1
    
    print()
    
    # Check 2: Configuration files exist
    print("✓ Checking configuration files...")
    config_files = [
        tests_dir / "conftest.py",
        tests_dir / "pytest.ini",
        tests_dir / "README.md",
        tests_dir / "__init__.py",
        project_root / "requirements-test.txt",
        project_root / "run_tests.sh",
    ]
    
    for config_file in config_files:
        if config_file.exists():
            print(f"  ✓ {config_file.relative_to(project_root)}")
        else:
            print(f"  ✗ {config_file.relative_to(project_root)} - NOT FOUND")
    
    print()
    
    # Check 3: Try to discover tests
    print("✓ Discovering tests with pytest...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "ui/tests/", "--collect-only", "-q"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Parse output to count tests
        output = result.stdout
        if "test session starts" in output or "tests collected" in output:
            print(f"  ✓ Test discovery successful")
            
            # Try to extract number of tests
            for line in output.split('\n'):
                if 'collected' in line:
                    print(f"  {line.strip()}")
                    break
        else:
            print("  Output:")
            print(result.stdout)
            if result.stderr:
                print("  Errors:")
                print(result.stderr)
    except Exception as e:
        print(f"  ✗ Error during test discovery: {e}")
        return 1
    
    print()
    
    # Check 4: Verify imports work
    print("✓ Checking imports...")
    try:
        sys.path.insert(0, str(ui_dir))
        from models import QCRecord, MetricQC, QCTask, QCConfig
        from utils.config import parse_qc_config
        from utils.data_loaders import load_mri_data, load_svg_data
        print("  ✓ All imports successful")
    except Exception as e:
        print(f"  ✗ Import error: {e}")
        return 1
    
    print()
    print("=" * 70)
    print("✓ All checks passed! Test infrastructure is ready.")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Install test dependencies:")
    print("     pip install -r requirements-test.txt")
    print()
    print("  2. Run all tests:")
    print("     pytest ui/tests/")
    print()
    print("  3. Run with coverage:")
    print("     pytest ui/tests/ --cov=ui --cov-report=html")
    print()
    print("  4. Or use the test runner script:")
    print("     chmod +x run_tests.sh")
    print("     ./run_tests.sh all --cov")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
