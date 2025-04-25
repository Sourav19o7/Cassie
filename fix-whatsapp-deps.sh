#!/bin/bash

# Fix for WhatsApp Integration Dependencies
# This script installs the required dependencies for WhatsApp integration

echo "Installing WhatsApp Integration Dependencies"
echo "==========================================="

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Installing pip..."
    python3 -m ensurepip --upgrade
    
    if [ $? -ne 0 ]; then
        echo "Failed to install pip. Please install pip manually."
        exit 1
    fi
fi

# Install required packages
echo "Installing required packages..."
pip3 install --upgrade pip
pip3 install selenium webdriver-manager pillow

# Check if the installation was successful
if [ $? -ne 0 ]; then
    echo "Failed to install required packages. Please check the errors above."
    exit 1
fi

# Path to the WhatsApp integration module
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
WHATSAPP_PATH="${SCRIPT_DIR}/whatsapp_integration.py"

# Check if the file exists
if [ ! -f "$WHATSAPP_PATH" ]; then
    echo "WhatsApp integration module not found at: $WHATSAPP_PATH"
    exit 1
fi

# Check if rich.console is imported at the top
if ! grep -q "from rich.console import Console" "$WHATSAPP_PATH"; then
    # Add the import at the top
    echo "Fixing missing console import in WhatsApp integration module..."
    sed -i.bak '1s/^/from rich.console import Console\n/' "$WHATSAPP_PATH"
    echo "Fixed missing console import in WhatsApp integration module."
fi

# Create WhatsApp session directories
echo "Creating WhatsApp session directories..."
mkdir -p "$HOME/.empathic_solver/whatsapp_session/chrome"
mkdir -p "$HOME/.empathic_solver/whatsapp_session/firefox"
mkdir -p "$HOME/.empathic_solver/whatsapp_session/edge"

echo "Installation completed successfully!"
echo "Try running 'empathic-solver configure-whatsapp' to set up WhatsApp integration."