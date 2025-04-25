#!/bin/bash

# Cassie CLI Installer
echo "Cassie CLI Installer"
echo "===================="

# Set up installation directory
INSTALL_DIR="$HOME/.local/share/cassie"
mkdir -p "$INSTALL_DIR"

echo "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

echo "Installing required dependencies..."
pip install --upgrade pip
pip install typer rich pandas numpy requests keyring schedule selenium webdriver-manager pillow

# Download the main Python scripts
echo "Downloading Cassie scripts..."
mkdir -p "$INSTALL_DIR/src"
curl -L "https://sourav19o7.github.io/Cassie/empathic_solver.py" -o "$INSTALL_DIR/src/empathic_solver.py"
curl -L "https://sourav19o7.github.io/Cassie/reminders.py" -o "$INSTALL_DIR/src/reminders.py"
curl -L "https://sourav19o7.github.io/Cassie/whatsapp_integration.py" -o "$INSTALL_DIR/src/whatsapp_integration.py"

if [ $? -ne 0 ]; then
    echo "Failed to download scripts. Please check your internet connection."
    exit 1
fi

# Fix potential console import issue in WhatsApp integration
echo "Checking and fixing module dependencies..."
grep -q "from rich.console import Console" "$INSTALL_DIR/src/whatsapp_integration.py"
if [ $? -ne 0 ]; then
    # Add the missing import at the beginning of the file
    sed -i.bak '1s/^/from rich.console import Console\n/' "$INSTALL_DIR/src/whatsapp_integration.py"
    echo "Fixed missing console import in WhatsApp integration."
fi

# Create application data directory
mkdir -p "$HOME/.empathic_solver"

# Create launcher script
echo "Creating launcher..."
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/cassie" << 'EOF'
#!/bin/bash
cd "$HOME/.local/share/cassie/src"  # Change to the directory containing the scripts
source "$HOME/.local/share/cassie/venv/bin/activate"
python "$HOME/.local/share/cassie/src/empathic_solver.py" "$@"
EOF

chmod +x "$HOME/.local/bin/cassie"

# Add to PATH if needed
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    echo "Added $HOME/.local/bin to PATH. You may need to restart your terminal or run 'source ~/.bash_profile' or 'source ~/.zshrc'"
fi

# Create WhatsApp session directories
mkdir -p "$HOME/.empathic_solver/whatsapp_session/chrome"
mkdir -p "$HOME/.empathic_solver/whatsapp_session/firefox"
mkdir -p "$HOME/.empathic_solver/whatsapp_session/edge"

echo ""
echo "Installation completed successfully!"
echo "You can now use Cassie by running: cassie"
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
echo "Enjoy using Cassie!"