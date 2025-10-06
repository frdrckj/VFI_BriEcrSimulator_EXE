#!/bin/bash

echo "Building BRI ECR executable..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install build requirements
echo "Installing build requirements..."
pip install -r build_requirements.txt

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/

# Build the executable
echo "Building executable with PyInstaller..."
pyinstaller bri_ecr.spec

# Check if build was successful
if [ -f "dist/bri-ecr-simulator.exe" ]; then
    echo "Build successful! Executable created at: dist/bri-ecr-simulator.exe"
    echo "You can now distribute the 'dist/bri-ecr-simulator.exe' file to your clients."
    echo "Virtual environment deactivated."
else
    echo "Build failed. Check the output above for errors."
    exit 1
fi