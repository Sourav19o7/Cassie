#!/bin/bash

# Cassie CLI Installer
VERSION="1.1.0"
DOWNLOAD_URL="https://sourav19o7.github.io/Cassie"

echo "Cassie CLI (Claude Haiku Edition) Installer v$VERSION"
echo "==================================================="

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

# Function to download a file with retry
download_with_retry() {
    local url="$1"
    local output="$2"
    local max_retries=3
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        echo "Downloading $url to $output (attempt $(($retry + 1))/$max_retries)..."
        curl -L "$url" -o "$output" && return 0
        
        retry=$(($retry + 1))
        echo "Download failed, retrying in 2 seconds..."
        sleep 2
    done
    
    echo "Failed to download $url after $max_retries attempts."
    return 1
}

# Download the main script files
download_with_retry "$DOWNLOAD_URL/empathic_solver.py" "$INSTALL_DIR/src/empathic_solver.py" || exit 1
download_with_retry "$DOWNLOAD_URL/reminders.py" "$INSTALL_DIR/src/reminders.py" || exit 1
download_with_retry "$DOWNLOAD_URL/whatsapp_integration.py" "$INSTALL_DIR/src/whatsapp_integration.py" || exit 1

# Ensure imports work correctly by modifying files if needed
echo "Ensuring correct imports..."

# Fix import issues in empathic_solver.py if necessary
sed -i.bak 's/from \. import reminders/import reminders/g' "$INSTALL_DIR/src/empathic_solver.py"
sed -i.bak 's/from \. import whatsapp_integration/import whatsapp_integration/g' "$INSTALL_DIR/src/empathic_solver.py"

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

# Create symlink for empathic-solver command
ln -sf "$HOME/.local/bin/cassie" "$HOME/.local/bin/empathic-solver"
chmod +x "$HOME/.local/bin/empathic-solver"

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

# Test the installation
echo "Testing installation..."
"$HOME/.local/bin/cassie" version 2>/dev/null

if [ $? -ne 0 ]; then
    echo "[WARNING] Installation test failed. Please check the installation manually."
else
    echo "[SUCCESS] Installation test passed!"
fi

echo ""
echo "Installation completed successfully!"
echo "You can now use Cassie by running: cassie"
echo ""
echo "First-time setup:"
echo "  cassie configure   # Set up your Claude API key and preferences"
echo "  cassie configure-whatsapp  # Set up WhatsApp integration (optional)"
echo ""
echo "Try these commands:"
echo "  cassie --help      # Show help"
echo "  cassie new         # Create a new problem"
echo "  cassie list        # List all problems"
echo "  cassie scan-whatsapp  # Scan WhatsApp for tasks (if configured)"
echo ""
echo "Reminder commands:"
echo "  cassie reminder-set 1      # Set a reminder for problem #1"
echo "  cassie reminders-list      # List all active reminders"
echo "  cassie reminder-test 1     # Test notification for problem #1"
echo ""
echo "Enjoy using Cassie CLI powered by Claude Haiku!"