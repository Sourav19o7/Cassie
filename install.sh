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
pip3 install --upgrade pip
pip3 install typer>=0.9.0 rich>=13.4.2 pandas>=2.0.3 numpy>=1.24.3 requests>=2.28.0 keyring>=23.0.0 schedule>=1.2.0 selenium webdriver-manager pillow

# Check if we are in the source directory
if [ -f "empathic_solver.py" ] && [ -f "setup.py" ]; then
    echo "Installing from source..."
    
    # Fix potential console import issue in WhatsApp integration
    echo "Checking and fixing module dependencies..."
    if [ -f "whatsapp_integration.py" ]; then
        grep -q "from rich.console import Console" "whatsapp_integration.py"
        if [ $? -ne 0 ]; then
            # Add the missing import at the beginning of the file
            sed -i.bak '1s/^/from rich.console import Console\n/' "whatsapp_integration.py"
            echo "Fixed missing console import in WhatsApp integration."
        fi
    fi
    
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
        if [ -f "whatsapp_integration.py" ]; then
            cp whatsapp_integration.py "$HOME/.local/bin/"
        fi
        chmod +x "$HOME/.local/bin/empathic-solver"
        
        # Create a symlink for the cassie command
        ln -sf "$HOME/.local/bin/empathic-solver" "$HOME/.local/bin/cassie"
        chmod +x "$HOME/.local/bin/cassie"
        
        # Add to PATH if not already there
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
            echo "Added $HOME/.local/bin to PATH"
        fi
        
        # Create application directories
        mkdir -p "$HOME/.empathic_solver"
        
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
        sudo ln -sf "$SCRIPT_PATH" /usr/local/bin/cassie
        
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
    osascript -e 'display notification "Empathic Problem Solver installed successfully!" with title "Cassie CLI"'
fi

echo ""
echo "Installation completed successfully!"
echo "You can now use the CLI by running: cassie or empathic-solver"
echo ""
echo "First-time setup:"
echo "  cassie configure   # Set up your Claude API key and preferences"
echo "  cassie configure-whatsapp  # Set up WhatsApp integration"
echo ""
echo "Try these commands:"
echo "  cassie --help      # Show help"
echo "  cassie new         # Create a new problem"
echo "  cassie list        # List all problems"
echo "  cassie scan-whatsapp  # Scan WhatsApp for tasks"
echo ""
echo "New reminder commands:"
echo "  cassie reminder-set 1      # Set a reminder for problem #1"
echo "  cassie reminders-list      # List all active reminders"
echo "  cassie reminder-disable 1  # Disable a reminder"
echo "  cassie reminder-enable 1   # Enable a reminder"
echo "  cassie reminder-delete 1   # Delete a reminder"
echo "  cassie reminder-test 1     # Test notification for problem #1"
echo ""
echo "Enjoy using Cassie CLI powered by Claude Haiku!"