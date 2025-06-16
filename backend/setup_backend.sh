#!/bin/bash
# Setup script for Velo Threat Hunter backend Python environment

set -e

echo "📦 Installing python3-venv (if not already)..."
sudo apt update
sudo apt install -y python3-venv

echo "🧪 Creating virtual environment..."
python3 -m venv venv

echo "✅ Activating virtual environment..."
source venv/bin/activate

echo "📄 Installing requirements..."
pip install -r requirements.txt

echo "🚀 Done! To activate later, run:"
echo "source venv/bin/activate"
