#!/usr/bin/env bash
# ==============================================================================
# Amity University Chhattisgarh - Automatic Attendance Planner Launcher (Mac/Linux)
# ==============================================================================

set -e

# Change to the directory of this script
cd "$(dirname "$0")"

echo "===================================================================="
echo "    AMITY AUTOMATIC ATTENDANCE CALCULATOR & STRATEGY PLANNER        "
echo "===================================================================="

# Check for python3
if ! command -v python3 &>/dev/null; then
    echo "[Error] python3 is not installed or not in PATH."
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

# Validate or create virtual environment
RECREATE_VENV=0
if [ ! -d "venv" ] || [ ! -f "venv/bin/python" ]; then
    RECREATE_VENV=1
elif ! ./venv/bin/python -c 'import sys' &>/dev/null; then
    echo "[Setup] Existing virtual environment is invalid or was moved. Recreating..."
    rm -rf venv
    RECREATE_VENV=1
fi

if [ "$RECREATE_VENV" -eq 1 ]; then
    echo "[Setup] Creating Python virtual environment in ./venv..."
    python3 -m venv venv
fi

# Install / update requirements
if [ -f "requirements.txt" ]; then
    echo "[Setup] Checking dependencies..."
    ./venv/bin/python -m pip install -q -r requirements.txt
fi

echo "[Launch] Starting attendance planner..."
echo ""
exec ./venv/bin/python attendance_planner.py "$@"
