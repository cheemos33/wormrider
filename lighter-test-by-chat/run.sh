#!/usr/bin/env zsh
# 🚀 Lighter Testnet - quick setup & run script (macOS)

# Stop if any command fails
set -e

echo "=== Setting up virtual environment ==="
python3 -m venv .venv

echo "=== Activating virtual environment ==="
source .venv/bin/activate

echo "=== Upgrading pip ==="
python -m pip install --upgrade pip

echo "=== Installing requirements ==="
pip install -r requirements.txt

echo "=== Running Lighter Testnet script ==="
python lighter_market_buy.py
