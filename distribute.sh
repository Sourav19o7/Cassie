#!/bin/bash

# Empathic Problem Solver CLI Distributor
# This script downloads and installs the prepackaged Empathic Problem Solver CLI

echo "Empathic Problem Solver CLI Installer"
echo "======================================"

# Configuration
DOWNLOAD_URL="https://your-private-server/empathic-solver"
VERSION="1.1.0"

# Create temporary directory
TMP_DIR=$(mktemp -d)
cd $TMP_DIR

echo "Downloading Empathic Problem Solver CLI v$VERSION (Claude Haiku Edition)..."
curl -L "$DOWNLOAD_URL" -o empathic-solver

if [ $? -ne 0 ]; then
    echo "Download failed. Please check your internet connection and try again."
    cd - > /dev/null
    rm -rf $TMP_DIR
    exit 1
fi

echo "Download complete. Installing..."

# Make executable
chmod +x empathic-solver

# Create destination directory if it doesn't exist
if [ ! -d "$HOME/.local/bin" ]; then
    mkdir -p "$HOME/.local/bin"
fi

# Move to bin directory
mv empathic-solver "$HOME/.local/bin/"

# Add to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    echo "Added $HOME/.local/bin to PATH"
    echo "You may need to restart your terminal or run 'source ~/.bash_profile' to use the command."
fi

# Install dependencies
echo "Installing required Python packages..."
pip3 install typer rich pandas numpy requests keyring --quiet

# Create global symlink (optional)
if [ "$1" == "--global" ]; then
    echo "Creating global symlink (requires sudo)..."
    sudo ln -sf "$HOME/.local/bin/empathic-solver" /usr/local/bin/empathic-solver
    
    if [ $? -ne 0 ]; then
        echo "Failed to create global symlink. You can still use the command from your user account."
    else
        echo "Global symlink created successfully."
    fi
fi

# Clean up
cd - > /dev/null
rm -rf $TMP_DIR

echo ""
echo "Installation completed successfully!"
echo "You can now use the Empathic Problem Solver CLI by running: empathic-solver"
echo ""
echo "First-time setup:"
echo "  empathic-solver configure   # Set up your Claude API key and preferences"
echo ""
echo "Try these commands:"
echo "  empathic-solver --help      # Show help"
echo "  empathic-solver new         # Create a new problem"
echo "  empathic-solver list        # List all problems"
echo "  empathic-solver analyze 1   # Get AI analysis of problem #1"
echo ""
echo "Enjoy using Empathic Problem Solver CLI powered by Claude Haiku!"