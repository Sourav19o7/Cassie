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
pip install typer rich pandas numpy requests keyring

# Download the main Python script
echo "Downloading Cassie script..."
mkdir -p "$INSTALL_DIR/src"
curl -L "https://sourav19o7.github.io/Cassie/empathic_solver.py" -o "$INSTALL_DIR/src/empathic_solver.py"

if [ $? -ne 0 ]; then
    echo "Failed to download script. Please check your internet connection."
    exit 1
fi

# Create launcher script
echo "Creating launcher..."
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/cassie" << 'EOF'
#!/bin/bash
source "$HOME/.local/share/cassie/venv/bin/activate"
python "$HOME/.local/share/cassie/src/empathic_solver.py" "$@"
EOF

chmod +x "$HOME/.local/bin/cassie"

# Add to PATH if needed
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    echo "Added $HOME/.local/bin to PATH. You may need to restart your terminal or run 'source ~/.bash_profile'"
fi

echo ""
echo "Installation completed successfully!"
echo "You can now use Cassie by running: cassie"
echo ""
echo "First-time setup:"
echo "  cassie configure   # Set up your Claude API key and preferences"
echo ""
echo "Try these commands:"
echo "  cassie --help      # Show help"
echo "  cassie new         # Create a new problem"
echo "  cassie list        # List all problems"
echo ""
echo "Enjoy using Cassie!"