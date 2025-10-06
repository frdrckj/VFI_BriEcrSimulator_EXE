#!/bin/bash

# Start BRI ECR Web Application
echo "Starting BRI ECR Web Application..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.11 or later."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Please install pip."
    exit 1
fi

# Install requirements if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing/updating requirements..."
pip install -r requirements.txt

echo "Starting Flask application..."
export PYTHONPATH=$(pwd)
cd src
python main.py