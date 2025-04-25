#!/bin/bash

# Empathic Problem Solver CLI Installer
# This script installs the Empathic Problem Solver CLI on macOS

echo "Empathic Problem Solver CLI Installer"
echo "======================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Installing Python..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Homebrew is not installed. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install Python with Homebrew
    brew install python
    
    if [ $? -ne 0 ]; then
        echo "Failed to install Python. Please install Python 3.8 or later manually."
        exit 1
    fi
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "Python 3.8 or later is required. You have Python $PYTHON_VERSION."
    echo "Please update your Python installation."
    exit 1
fi

echo "Python $PYTHON_VERSION detected."

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Installing pip..."
    python3 -m ensurepip --upgrade
    
    if [ $? -ne 0 ]; then
        echo "Failed to install pip. Please install pip manually."
        exit 1
    fi
fi

# Create a virtual environment (optional)
if [ "$1" == "--venv" ]; then
    echo "Creating a virtual environment..."
    python3 -m venv empathic-solver-env
    
    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment. Proceeding with system-wide installation."
    else
        echo "Activating virtual environment..."
        source empathic-solver-env/bin/activate
    fi
fi

# Install required packages
echo "Installing required packages..."
pip3 install typer>=0.9.0 rich>=13.4.2 pandas>=2.0.3 numpy>=1.24.3 requests>=2.28.0 keyring>=23.0.0 schedule>=1.2.0 selenium webdriver-manager pillow

# Check if we are in the source directory
if [ -f "empathic_solver.py" ] && [ -f "setup.py" ]; then
    echo "Installing from source..."
    pip3 install -e .
    
    if [ $? -ne 0 ]; then
        echo "Installation from source failed. Installing from individual files..."
        # Check if destination directory exists
        if [ ! -d "$HOME/.local/bin" ]; then
            mkdir -p "$HOME/.local/bin"
        fi
        
        # Copy the main script and modules
        cp empathic_solver.py "$HOME/.local/bin/empathic-solver"
        cp reminders.py "$HOME/.local/bin/"
        cp whatsapp_integration.py "$HOME/.local/bin/"
        chmod +x "$HOME/.local/bin/empathic-solver"
        
        # Add to PATH if not already there
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
            echo "Added $HOME/.local/bin to PATH"
        fi
        
        # Create WhatsApp session directories
        mkdir -p "$HOME/.empathic_solver/whatsapp_session/chrome"
        mkdir -p "$HOME/.empathic_solver/whatsapp_session/firefox"
        mkdir -p "$HOME/.empathic_solver/whatsapp_session/edge"
    fi
else
    echo "Source files not found. Please make sure you're running this script from the correct directory."
    exit 1
fi

# Create symlink in /usr/local/bin for easier access (optional)
if [ "$1" == "--symlink" ] || [ "$2" == "--symlink" ]; then
    echo "Creating symlink in /usr/local/bin..."
    
    # Get the path to the installed script
    SCRIPT_PATH=$(which empathic-solver 2>/dev/null)
    
    if [ -n "$SCRIPT_PATH" ]; then
        sudo ln -sf "$SCRIPT_PATH" /usr/local/bin/empathic-solver
        
        if [ $? -ne 0 ]; then
            echo "Failed to create symlink. You may need to run this script with sudo."
        else
            echo "Symlink created successfully."
        fi
    else
        echo "Could not find the installed script. Skipping symlink creation."
    fi
fi

# Check if we need to set up notification permissions on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Setting up notification permissions for macOS..."
    echo "Note: You may need to manually grant notification permissions in System Preferences > Notifications"
    
    # Create a simple AppleScript to request notification permissions
    osascript -e 'display notification "Empathic Problem Solver installed successfully!" with title "Empathic Problem Solver"'
fi

echo ""
echo "Installation completed successfully!"
echo "You can now use the Empathic Problem Solver CLI by running: empathic-solver"
echo ""
echo "First-time setup:"
echo "  empathic-solver configure   # Set up your Claude API key and preferences"
echo "  empathic-solver configure-whatsapp  # Set up WhatsApp integration"
echo ""
echo "Try these commands:"
echo "  empathic-solver --help      # Show help"
echo "  empathic-solver new         # Create a new problem"
echo "  empathic-solver list        # List all problems"
echo "  empathic-solver scan-whatsapp  # Scan WhatsApp for tasks"
echo ""
echo "New reminder commands:"
echo "  empathic-solver reminder-set 1      # Set a reminder for problem #1"
echo "  empathic-solver reminders-list      # List all active reminders"
echo "  empathic-solver reminder-disable 1  # Disable a reminder"
echo "  empathic-solver reminder-enable 1   # Enable a reminder"
echo "  empathic-solver reminder-delete 1   # Delete a reminder"
echo "  empathic-solver reminder-test 1     # Test notification for problem #1"
echo ""
echo "Enjoy using Empathic Problem Solver CLI powered by Claude Haiku!"