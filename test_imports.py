#!/usr/bin/env python3

"""
Test script to verify all required modules can be imported correctly.
Run this before building to ensure all dependencies are available.
"""

import sys
import os

print("Testing imports for Empathic Problem Solver CLI...")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print("=" * 50)

# Test basic imports
modules_to_test = [
    "typer",
    "rich.console",
    "rich.table",
    "rich.markdown",
    "rich.panel",
    "rich.progress",
    "pandas",
    "numpy",
    "sqlite3",
    "datetime",
    "pathlib",
    "requests",
    "keyring",
    "getpass",
    "json",
    "textwrap",
    "schedule",
    "threading",
    "time"
]

print("Testing basic imports:")
for module in modules_to_test:
    try:
        __import__(module)
        print(f"✅ {module}")
    except ImportError as e:
        print(f"❌ {module}: {e}")

print("\nTesting local module imports:")

# Test if current directory is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    print(f"Added {current_dir} to sys.path")

# Test reminders module
try:
    import reminders
    print("✅ reminders")
except ImportError as e:
    print(f"❌ reminders: {e}")

# Test WhatsApp integration module
try:
    import whatsapp_integration
    print("✅ whatsapp_integration")
except ImportError as e:
    print(f"❌ whatsapp_integration: {e}")

# Test optional dependencies
print("\nTesting optional dependencies:")

try:
    from PIL import Image
    print("✅ PIL.Image")
except ImportError as e:
    print(f"❌ PIL.Image: {e}")

try:
    import selenium
    print("✅ selenium")
    
    from selenium import webdriver
    print("✅ selenium.webdriver")
    
    from selenium.webdriver.chrome.service import Service
    print("✅ selenium.webdriver.chrome.service")
    
    from selenium.webdriver.chrome.options import Options
    print("✅ selenium.webdriver.chrome.options")
    
    from selenium.webdriver.common.by import By
    print("✅ selenium.webdriver.common.by")
except ImportError as e:
    print(f"❌ selenium: {e}")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    print("✅ webdriver_manager.chrome")
except ImportError as e:
    print(f"❌ webdriver_manager.chrome: {e}")

print("\nImport test complete!")