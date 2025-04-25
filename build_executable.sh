#!/bin/bash

# Empathic Problem Solver CLI - Improved Build Script
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

# Check if all required dependencies are installed
echo "Checking required dependencies..."
pip3 install typer rich pandas numpy requests keyring schedule selenium webdriver-manager pillow

# Check for required files
if [ ! -f "empathic_solver.py" ]; then
    echo "Error: empathic_solver.py not found. Make sure you're in the correct directory."
    exit 1
fi

if [ ! -f "reminders.py" ]; then
    echo "Error: reminders.py not found. Make sure you're in the correct directory."
    exit 1
fi

# Create backup of original files
echo "Creating backups of original files..."
cp empathic_solver.py empathic_solver.py.bak
cp reminders.py reminders.py.bak
if [ -f "whatsapp_integration.py" ]; then
    cp whatsapp_integration.py whatsapp_integration.py.bak
fi

# Instead of trying to modify the file in pieces, let's create a new file with all our changes
echo "Creating modified empathic_solver.py..."

# Create a complete modified version from scratch
cat > empathic_solver.py << 'EOF'
#!/usr/bin/env python3

import os
import sys
import json
import sqlite3
import datetime
import typer
from typing import List, Dict, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
import pandas as pd
import numpy as np
from pathlib import Path
import requests
import textwrap
import getpass
import keyring
import time
import threading
import schedule

# Initialize Typer app and console first
app = typer.Typer(help="Empathic Problem Solver CLI")
console = Console()

# Create application data directory constants
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
CONFIG_PATH = APP_DIR / "config.json"

# Define flags for module availability
REMINDERS_AVAILABLE = False
WHATSAPP_AVAILABLE = False

# First try to import reminders module
try:
    # Add the current directory to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    import reminders
    REMINDERS_AVAILABLE = True
except ImportError:
    console.print("[yellow]Warning: reminders module could not be imported.[/yellow]")
    REMINDERS_AVAILABLE = False

# Then try to import WhatsApp integration
try:
    import whatsapp_integration
    WHATSAPP_AVAILABLE = True
except ImportError:
    console.print("[yellow]WhatsApp integration module not available.[/yellow]")
    WHATSAPP_AVAILABLE = False

def init_app():
    """Initialize application directories and database."""
    if not APP_DIR.exists():
        APP_DIR.mkdir(parents=True)
    
    # Initialize database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS problems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        created_date TEXT NOT NULL,
        status TEXT DEFAULT 'active'
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS kpis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        problem_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        target_value REAL,
        current_value REAL DEFAULT 0,
        FOREIGN KEY (problem_id) REFERENCES problems (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS action_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        problem_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (problem_id) REFERENCES problems (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS progress_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        problem_id INTEGER NOT NULL,
        kpi_id INTEGER NOT NULL,
        value REAL NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (problem_id) REFERENCES problems (id),
        FOREIGN KEY (kpi_id) REFERENCES kpis (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    # Create default config if it doesn't exist
    if not CONFIG_PATH.exists():
        config = {
            "model": DEFAULT_MODEL,
            "use_ai": True,
            "max_tokens": 500,
            "api_key_set": False,
            "reminders_enabled": True
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)

    # Initialize reminders only if available
    if REMINDERS_AVAILABLE:
        reminder_manager = reminders.init_reminders()
        # Check for any past-due reminders
        reminders.check_due_reminders()

def load_config():
    """Load the application configuration."""
    if not CONFIG_PATH.exists():
        init_app()
    
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(config):
    """Save the application configuration."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
EOF

# Now append the rest of the original file, starting after these functions
# Use grep to find the line number after the save_config function
LINE_NUM=$(grep -n "def get_api_key" empathic_solver.py.bak | cut -d: -f1)

# Append the rest of the file starting from that line
tail -n +$LINE_NUM empathic_solver.py.bak >> empathic_solver.py

# Add missing constants if needed
sed -i.tmp '1,50s/DEFAULT_MODEL = "claude-3-haiku-20240307"/DEFAULT_MODEL = "claude-3-haiku-20240307"/' empathic_solver.py

echo "Building standalone executable..."

# Create spec file
cat > empathic_solver.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Add the modules as data files
added_files = [
    ('reminders.py', '.'),
    ('whatsapp_integration.py', '.')
]

a = Analysis(
    ['empathic_solver.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'typer', 'rich.console', 'rich.table', 'rich.markdown', 'rich.panel', 
        'rich.progress', 'pandas', 'numpy', 'sqlite3', 'datetime', 'pathlib',
        'requests', 'keyring', 'getpass', 'json', 'textwrap', 'schedule',
        'threading', 'time', 'reminders', 'whatsapp_integration', 'PIL', 'PIL.Image'
    ],
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

# Build the executable
pyinstaller --clean empathic_solver.spec

if [ $? -ne 0 ]; then
    echo "Build failed. Check the errors above."
    # Restore original files
    mv empathic_solver.py.bak empathic_solver.py
    mv reminders.py.bak reminders.py
    if [ -f "whatsapp_integration.py.bak" ]; then
        mv whatsapp_integration.py.bak whatsapp_integration.py
    fi
    exit 1
fi

# Check if build was successful
if [ -f "dist/empathic-solver" ]; then
    echo "Build successful! Executable created at: dist/empathic-solver"
    
    # Create distribution directory
    mkdir -p distribute
    
    # Copy executable to distribute directory
    cp dist/empathic-solver distribute/
    
    # Test if the executable works - just version check for a more reliable test
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
    
    # Restore original files
    mv empathic_solver.py.bak empathic_solver.py
    mv reminders.py.bak reminders.py
    if [ -f "whatsapp_integration.py.bak" ]; then
        mv whatsapp_integration.py.bak whatsapp_integration.py
    fi
    
else
    echo "Build failed. No executable was produced."
    # Restore original files
    mv empathic_solver.py.bak empathic_solver.py
    mv reminders.py.bak reminders.py
    if [ -f "whatsapp_integration.py.bak" ]; then
        mv whatsapp_integration.py.bak whatsapp_integration.py
    fi
    exit 1
fi

echo "Build process complete!"