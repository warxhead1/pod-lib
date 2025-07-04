#!/usr/bin/env python3
"""
Test runner script for POD library
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"❌ {description} failed with exit code {result.returncode}")
        return False
    else:
        print(f"✅ {description} passed")
        return True


def main():
    parser = argparse.ArgumentParser(description="Run POD library tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage reporting")
    parser.add_argument("--lint", action="store_true", help="Run linting checks")
    parser.add_argument("--format", action="store_true", help="Format code with black and isort")
    parser.add_argument("--security", action="store_true", help="Run security checks")
    parser.add_argument("--all", action="store_true", help="Run all tests and checks")
    parser.add_argument("--parallel", "-j", type=int, help="Number of parallel workers for tests")
    
    args = parser.parse_args()
    
    # Change to project directory
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    success = True
    
    # Format code if requested
    if args.format:
        if not run_command(["black", "pod", "tests"], "Code formatting with black"):
            success = False
        if not run_command(["isort", "pod", "tests"], "Import sorting with isort"):
            success = False
    
    # Run linting if requested
    if args.lint:
        if not run_command(["flake8", "pod"], "Flake8 linting"):
            success = False
        if not run_command(["mypy", "pod"], "MyPy type checking"):
            success = False
    
    # Run security checks if requested
    if args.security:
        if not run_command(["bandit", "-r", "pod"], "Security check with bandit"):
            success = False
    
    # Build test command
    test_cmd = ["python", "-m", "pytest"]
    
    # Add parallel execution
    if args.parallel:
        test_cmd.extend(["-n", str(args.parallel)])
    
    # Add coverage if requested
    if args.coverage or args.all:
        test_cmd.extend([
            "--cov=pod",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    # Add specific test types
    if args.unit:
        test_cmd.extend(["-m", "unit", "tests/unit/"])
    elif args.integration:
        test_cmd.extend(["-m", "integration", "tests/integration/"])
    elif not args.all:
        # Default to unit tests if nothing specified
        test_cmd.append("tests/unit/")
    else:
        # Run all tests
        test_cmd.append("tests/")
    
    # Run tests
    if args.unit or args.integration or args.all or (not args.lint and not args.format and not args.security):
        if not run_command(test_cmd, "Running tests"):
            success = False
    
    # Final status
    print(f"\n{'='*60}")
    if success:
        print("🎉 All checks passed!")
        return 0
    else:
        print("❌ Some checks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())