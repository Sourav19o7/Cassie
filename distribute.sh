#!/bin/bash

# Cassie CLI Installer
echo "Cassie CLI Installer"
echo "===================="

# Create a Python virtual environment
INSTALL_DIR="$HOME/.local/share/cassie"
mkdir -p "$INSTALL_DIR"

echo "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

echo "Installing Cassie and dependencies..."
pip install typer rich pandas numpy requests keyring

# Download the main script
echo "Downloading Cassie script..."
mkdir -p "$INSTALL_DIR/src"
curl -L "https://sourav19o7.github.io/Cassie/empathic_solver.py" -o "$INSTALL_DIR/src/empathic_solver.py"

# Create a launcher script
echo "Creating launcher..."
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/cassie" << EOF
#!/bin/bash
source "$INSTALL_DIR/venv/bin/activate"
python "$INSTALL_DIR/src/empathic_solver.py" "\$@"
EOF

chmod +x "$HOME/.local/bin/cassie"

# Add to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bash_profile"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    echo "Added $HOME/.local/bin to PATH"
    echo "You may need to restart your terminal or run 'source ~/.bash_profile' to use the command."
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