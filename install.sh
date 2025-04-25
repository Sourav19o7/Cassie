#!/bin/bash

# Empathic Problem Solver CLI Installer
# This script installs the Empathic Problem Solver CLI on macOS or Linux

echo "Empathic Problem Solver CLI Installer"
echo "======================================"

# Ensure app directory exists
APP_DIR="$HOME/.empathic_solver"
mkdir -p "$APP_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.8 or later."
    exit 1
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

# Install required packages
echo "Installing required packages..."
pip3 install --upgrade pip
pip3 install typer>=0.9.0 rich>=13.4.2 pandas>=2.0.3 numpy>=1.24.3 requests>=2.28.0 keyring>=23.0.0 schedule>=1.2.0

# Ask about WhatsApp integration
if [ "$1" != "--no-prompt" ]; then
    read -p "Install WhatsApp integration dependencies? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing WhatsApp integration dependencies..."
        pip3 install selenium webdriver-manager pillow
    fi
fi

# Copy files to the app directory
echo "Copying files to $APP_DIR..."
cp empathic_solver.py "$APP_DIR/"
cp reminders.py "$APP_DIR/"
if [ -f "whatsapp_integration.py" ]; then
    cp whatsapp_integration.py "$APP_DIR/"
fi

# Make the main script executable
chmod +x "$APP_DIR/empathic_solver.py"

# Create WhatsApp session directories
mkdir -p "$APP_DIR/whatsapp_session/chrome"
mkdir -p "$APP_DIR/whatsapp_session/firefox"
mkdir -p "$APP_DIR/whatsapp_session/edge"

# Create launcher scripts
echo "Creating launcher scripts..."
mkdir -p "$HOME/.local/bin"

# Create the main launcher script
cat > "$HOME/.local/bin/cassie" << 'EOF'
#!/bin/bash
APP_DIR="$HOME/.empathic_solver"
cd "$APP_DIR"
python3 "$APP_DIR/empathic_solver.py" "$@"
EOF

chmod +x "$HOME/.local/bin/cassie"

# Create symlink for empathic-solver command
ln -sf "$HOME/.local/bin/cassie" "$HOME/.local/bin/empathic-solver"
chmod +x "$HOME/.local/bin/empathic-solver"

# Add to PATH if needed
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    echo "Added $HOME/.local/bin to PATH. You may need to restart your terminal or run 'source ~/.bash_profile' or 'source ~/.zshrc'"
fi

# Test the installation
echo "Testing installation..."
"$HOME/.local/bin/cassie" version 2>/dev/null

if [ $? -ne 0 ]; then
    echo "[WARNING] Installation test failed. Trying direct execution..."
    cd "$APP_DIR" && python3 empathic_solver.py version
    
    if [ $? -ne 0 ]; then
        echo "[ERROR] Installation failed. Please check the error messages above."
    else
        echo "[WARNING] Script works when executed directly, but launcher script failed."
        echo "You can run the application with: cd $APP_DIR && python3 empathic_solver.py"
    fi
else
    echo "[SUCCESS] Installation test passed!"
fi

echo ""
echo "Installation completed!"
echo "You can now use the CLI by running: cassie or empathic-solver"
echo ""
echo "First-time setup:"
echo "  cassie configure   # Set up your Claude API key and preferences"
echo "  cassie configure-whatsapp  # Set up WhatsApp integration (if installed)"
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