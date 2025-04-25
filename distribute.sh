#!/bin/bash

# Cassie CLI Installer
VERSION="1.2.0"
DOWNLOAD_URL="https://sourav19o7.github.io/Cassie"

echo "Cassie CLI (Claude Haiku Edition) Installer v$VERSION"
echo "==================================================="

# Set up installation directory
INSTALL_DIR="$HOME/.local/share/cassie"
mkdir -p "$INSTALL_DIR"

# Ensure .empathic_solver directory exists
APP_DIR="$HOME/.empathic_solver"
mkdir -p "$APP_DIR"

# Create Python virtual environment
echo "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv" || {
    echo "Failed to create virtual environment. Trying with system Python..."
    mkdir -p "$INSTALL_DIR/src"
}

# Check if venv creation was successful
if [ -d "$INSTALL_DIR/venv" ]; then
    source "$INSTALL_DIR/venv/bin/activate"
    echo "Installing required dependencies in virtual environment..."
    pip install --upgrade pip
    pip install typer rich pandas numpy requests keyring schedule selenium webdriver-manager pillow
else
    echo "Installing required dependencies system-wide..."
    pip3 install --user typer rich pandas numpy requests keyring schedule selenium webdriver-manager pillow
fi

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
        if command -v curl &> /dev/null; then
            curl -L "$url" -o "$output" && return 0
        elif command -v wget &> /dev/null; then
            wget "$url" -O "$output" && return 0
        else
            echo "Neither curl nor wget is available. Please install one of them and try again."
            return 1
        fi
        
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

# Copy scripts to app directory for easier imports
cp "$INSTALL_DIR/src/empathic_solver.py" "$APP_DIR/empathic_solver.py"
cp "$INSTALL_DIR/src/reminders.py" "$APP_DIR/reminders.py"
cp "$INSTALL_DIR/src/whatsapp_integration.py" "$APP_DIR/whatsapp_integration.py"

# Fix import issues in empathic_solver.py if necessary
echo "Ensuring correct imports..."
sed -i.bak 's/from \. import reminders/import reminders/g' "$INSTALL_DIR/src/empathic_solver.py"
sed -i.bak 's/from \. import whatsapp_integration/import whatsapp_integration/g' "$INSTALL_DIR/src/empathic_solver.py"

# Make scripts executable
chmod +x "$INSTALL_DIR/src/empathic_solver.py"
chmod +x "$APP_DIR/empathic_solver.py"

# Create WhatsApp session directories
echo "Creating WhatsApp session directories..."
mkdir -p "$APP_DIR/whatsapp_session/chrome"
mkdir -p "$APP_DIR/whatsapp_session/firefox"
mkdir -p "$APP_DIR/whatsapp_session/edge"

# Create launcher script
echo "Creating launcher scripts..."
mkdir -p "$HOME/.local/bin"

# Create launcher that tries both approaches (venv and app_dir)
cat > "$HOME/.local/bin/cassie" << 'EOF'
#!/bin/bash

# Define paths
INSTALL_DIR="$HOME/.local/share/cassie"
APP_DIR="$HOME/.empathic_solver"
VENV_PYTHON="$INSTALL_DIR/venv/bin/python"
SCRIPT_PATH="$INSTALL_DIR/src/empathic_solver.py"
APP_SCRIPT_PATH="$APP_DIR/empathic_solver.py"

# Check if virtual environment exists and use it
if [ -f "$VENV_PYTHON" ]; then
    cd "$INSTALL_DIR/src"  # Change to the directory containing the scripts
    source "$INSTALL_DIR/venv/bin/activate"
    "$VENV_PYTHON" "$SCRIPT_PATH" "$@"
elif [ -f "$APP_SCRIPT_PATH" ]; then
    # Fallback to app directory if venv doesn't exist
    cd "$APP_DIR"
    python3 "$APP_SCRIPT_PATH" "$@"
else
    # Final fallback
    cd "$INSTALL_DIR/src"
    python3 "$SCRIPT_PATH" "$@"
fi
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
    echo "[WARNING] Installation test failed. Trying to fix common issues..."
    
    # Try to fix any permission issues
    chmod +x "$INSTALL_DIR/src/empathic_solver.py"
    chmod +x "$HOME/.local/bin/cassie"
    chmod +x "$HOME/.local/bin/empathic-solver"
    
    # Try again
    "$HOME/.local/bin/cassie" version 2>/dev/null
    
    if [ $? -ne 0 ]; then
        echo "[WARNING] Installation still failing. Please try running these commands manually:"
        echo "  cd $APP_DIR && python3 empathic_solver.py version"
    else
        echo "[SUCCESS] Fixed installation issues!"
    fi
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