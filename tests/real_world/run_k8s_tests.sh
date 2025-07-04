#!/bin/bash

# POD Library - Kubernetes Integration Test Runner
# This script runs real-world tests against a Kubernetes cluster

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "POD Library - Kubernetes Integration Tests"
echo "=========================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Test directory: $SCRIPT_DIR"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    
    case $status in
        "success")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "error")
            echo -e "${RED}✗${NC} $message"
            ;;
        "warning")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        *)
            echo "$message"
            ;;
    esac
}

# Check if we're in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    print_status "warning" "Not running in a virtual environment"
    echo "Consider activating your virtual environment first:"
    echo "  source venv/bin/activate"
    echo ""
fi

# Step 1: Validate environment
echo "1. Validating Kubernetes environment..."
echo "--------------------------------------"
if python "$SCRIPT_DIR/validate_environment.py"; then
    print_status "success" "Environment validation passed"
else
    print_status "error" "Environment validation failed"
    exit 1
fi

echo ""

# Step 2: Install test dependencies if needed
echo "2. Checking test dependencies..."
echo "-------------------------------"
if ! python -c "import pytest" 2>/dev/null; then
    print_status "warning" "pytest not installed. Installing..."
    pip install pytest pytest-html pytest-cov
fi
print_status "success" "Test dependencies ready"

echo ""

# Step 3: Run basic connectivity tests
echo "3. Running basic connectivity tests..."
echo "------------------------------------"
if pytest "$SCRIPT_DIR/test_basic_k8s.py" -v -s; then
    print_status "success" "Basic connectivity tests passed"
else
    print_status "error" "Basic connectivity tests failed"
    echo "Fix basic connectivity before running advanced tests"
    exit 1
fi

echo ""

# Step 4: Run VLAN isolation tests (if supported)
echo "4. Running VLAN isolation tests..."
echo "---------------------------------"
pytest "$SCRIPT_DIR/test_vlan_isolation.py" -v -s || print_status "warning" "Some VLAN tests were skipped or failed"

echo ""

# Step 5: Run all tests with coverage report
echo "5. Running all tests with coverage..."
echo "-----------------------------------"
pytest "$SCRIPT_DIR" \
    --cov=pod.connections.kubernetes \
    --cov=pod.os_abstraction.kubernetes \
    --cov=pod.infrastructure.kubernetes \
    --cov=pod.network.cni \
    --cov-report=term-missing \
    --cov-report=html:coverage_report \
    --html=test_report.html \
    --self-contained-html \
    -v

echo ""

# Step 6: Generate summary
echo "6. Test Summary"
echo "---------------"

# Count test results
TOTAL_TESTS=$(grep -c "test_" "$SCRIPT_DIR"/test_*.py || echo "0")
REPORT_FILE="test_report.html"

if [[ -f "$REPORT_FILE" ]]; then
    print_status "success" "Test report generated: $REPORT_FILE"
    
    # Try to extract summary from pytest output
    if command -v grep &> /dev/null; then
        # This is a simple extraction, actual implementation may vary
        echo ""
        echo "Test Results:"
        grep -E "passed|failed|skipped" test_report.html | head -5 || true
    fi
else
    print_status "warning" "Test report not found"
fi

if [[ -d "coverage_report" ]]; then
    print_status "success" "Coverage report generated: coverage_report/index.html"
fi

echo ""
echo "========================================"
print_status "success" "Test execution completed!"
echo ""
echo "Next steps:"
echo "  - View test report: open $REPORT_FILE"
echo "  - View coverage: open coverage_report/index.html"
echo "  - Run specific test: pytest $SCRIPT_DIR/test_basic_k8s.py::TestBasicKubernetes::test_cluster_connection -v"
echo ""

# Optional: Open reports in browser
read -p "Open test report in browser? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open "$REPORT_FILE"
    elif command -v open &> /dev/null; then
        open "$REPORT_FILE"
    else
        print_status "warning" "Cannot auto-open browser. Please open $REPORT_FILE manually."
    fi
fi