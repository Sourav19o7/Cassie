#!/bin/bash

# Empathic Problem Solver CLI - Build Script
# This script builds a standalone executable for distribution

echo "Empathic Problem Solver CLI - Build Script"
echo "=========================================="

# Check if PyInstaller is installed
if ! pip3 show pyinstaller &> /dev/null; then
    echo "PyInstaller is not installed. Installing..."
    pip3 install pyinstaller
    
    if [ $? -ne 0 ]; then
        echo "Failed to install PyInstaller. Please install it manually with 'pip install pyinstaller'."
        exit 1
    fi
fi

# Check for required files
if [ ! -f "empathic_solver.py" ]; then
    echo "Error: empathic_solver.py not found. Make sure you're in the correct directory."
    exit 1
fi

echo "Building standalone executable..."

# Create spec file if it doesn't exist
if [ ! -f "empathic_solver.spec" ]; then
    cat > empathic_solver.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['empathic_solver.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['typer', 'rich.console', 'rich.table', 'rich.markdown', 'rich.panel', 'rich.progress',
                  'pandas', 'numpy', 'sqlite3', 'datetime', 'pathlib', 'requests', 'keyring', 'getpass'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='empathic-solver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOF
    echo "Created spec file."
fi

# Build the executable
pyinstaller --clean empathic_solver.spec

if [ $? -ne 0 ]; then
    echo "Build failed. Check the errors above."
    exit 1
fi

# Check if build was successful
if [ -f "dist/empathic-solver" ]; then
    echo "Build successful! Executable created at: dist/empathic-solver"
    
    # Create distribution directory
    mkdir -p distribute
    
    # Copy executable to distribute directory
    cp dist/empathic-solver distribute/
    
    # Test if the executable works
    echo "Testing executable..."
    ./dist/empathic-solver version
    
    if [ $? -ne 0 ]; then
        echo "Warning: Executable test failed. The build may have issues."
    else
        echo "Executable test passed!"
    fi
    
    echo ""
    echo "To distribute the executable:"
    echo "1. Upload the 'dist/empathic-solver' file to your hosting server"
    echo "2. Update the DOWNLOAD_URL in distribute.sh to point to your hosted file"
    echo "3. Share the distribute.sh script with your users"
    echo ""
    
    # Create a version with Claude Haiku branding
    echo "Adding Claude Haiku branding to distribute.sh..."
    cat distribute.sh | sed 's/VERSION="1.0.0"/VERSION="1.1.0"/g' | \
    sed 's/Empathic Problem Solver CLI/Empathic Problem Solver CLI (Claude Haiku Edition)/g' > \
    distribute/distribute.sh
    chmod +x distribute/distribute.sh
    
    echo "Distribution package ready in the 'distribute' directory."
    
else
    echo "Build failed. No executable was produced."
    exit 1
fi

echo "Build process complete!"