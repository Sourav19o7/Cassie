"""
WhatsApp Integration Module for Empathic Problem Solver CLI
Enables scanning WhatsApp messages and extracting actionable tasks using WhatsApp Web API.
"""

import os
import re
import json
import sqlite3
import datetime
from pathlib import Path
import typer
from typing import List, Dict, Optional, Union
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
import requests
import keyring
import time
import threading

# Initialize this variable before trying to import Selenium
SELENIUM_AVAILABLE = False

try:
    # Try to import browser automation libraries
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    pass  # SELENIUM_AVAILABLE remains False

# Path constants
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
WHATSAPP_CONFIG_PATH = APP_DIR / "whatsapp_config.json"
WHATSAPP_SESSION_PATH = APP_DIR / "whatsapp_session"
SERVICE_NAME = "empathic-solver"

console = Console()

def get_api_key():
    """Get the Claude API key from keyring."""
    api_key = keyring.get_password(SERVICE_NAME, "claude_api_key")
    return api_key

def call_claude_api(prompt, model="claude-3-5-haiku-20241022", max_tokens=500):
    """Call the Claude API with the given prompt."""
    api_key = get_api_key()
    if not api_key:
        console.print("[yellow]Claude API key not set. Using fallback methods.[/yellow]")
        return None
    
    CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        console.print("[cyan]Analyzing messages...[/cyan]")
        
        response = requests.post(CLAUDE_API_URL, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            return result["content"][0]["text"]
        else:
            console.print(f"[red]API Error: {response.status_code} - {response.text}[/red]")
            return None
    except Exception as e:
        console.print(f"[red]Error calling Claude API: {str(e)}[/red]")
        return None

def init_whatsapp_integration():
    """Initialize WhatsApp integration module."""
    if not APP_DIR.exists():
        APP_DIR.mkdir(parents=True)
    
    # Create WhatsApp session directory if it doesn't exist
    if not WHATSAPP_SESSION_PATH.exists():
        WHATSAPP_SESSION_PATH.mkdir(parents=True)
    
    # Create WhatsApp config if it doesn't exist
    if not WHATSAPP_CONFIG_PATH.exists():
        config = {
            "whatsapp_web_enabled": False,
            "last_scan_time": None,
            "monitored_groups": [],
            "scan_interval": 3600,  # Default scan interval in seconds (1 hour)
            "browser_type": "chrome",
            "headless": False,  # Show browser by default to handle authentication
            "auto_scan": False,  # Auto scan in background
            "use_export": False,  # Use chat export as alternative method
            "export_path": str(Path.home() / "Downloads"),
            "max_messages_per_chat": 50,  # Limit number of messages to scan per chat
            "show_qr": True,  # Show QR code in terminal for setup
            "filters": {
                "min_words": 5,  # Ignore very short messages
                "ignore_media": True  # Ignore media messages when scanning
            }
        }
        with open(WHATSAPP_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
    
    # Create tasks table in database if it doesn't exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS whatsapp_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        problem_id INTEGER,
        group_name TEXT NOT NULL,
        sender TEXT NOT NULL,
        message TEXT NOT NULL,
        task_description TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'medium',
        message_id TEXT, 
        FOREIGN KEY (problem_id) REFERENCES problems (id)
    )
    ''')
    
    # Create table to track processed messages
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS whatsapp_processed_messages (
        message_id TEXT PRIMARY KEY,
        group_name TEXT NOT NULL,
        sender TEXT NOT NULL,
        processed_date TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()
    
    return load_whatsapp_config()

def load_whatsapp_config():
    """Load WhatsApp integration configuration."""
    if not WHATSAPP_CONFIG_PATH.exists():
        return init_whatsapp_integration()
    
    with open(WHATSAPP_CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_whatsapp_config(config):
    """Save WhatsApp integration configuration."""
    with open(WHATSAPP_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def configure_whatsapp():
    """Configure WhatsApp integration settings."""
    config = load_whatsapp_config()
    
    # Check if Selenium is available
    if not SELENIUM_AVAILABLE:
        console.print("[yellow]Browser automation libraries not found. Installing required packages...[/yellow]")
        try:
            import pip
            pip.main(['install', 'selenium', 'webdriver-manager'])
            console.print("[green]Installed browser automation libraries successfully![/green]")
            global SELENIUM_AVAILABLE
            SELENIUM_AVAILABLE = True
        except Exception as e:
            console.print(f"[red]Failed to install required packages: {e}[/red]")
            console.print("[yellow]You can manually install them with: pip install selenium webdriver-manager[/yellow]")
            
            # Allow continuing with export-based approach
            if typer.confirm("Would you like to use chat export files instead of browser automation?", default=True):
                config["use_export"] = True
                export_path = typer.prompt("Path to download folder for WhatsApp exports", default=str(Path.home() / "Downloads"))
                config["export_path"] = export_path
                save_whatsapp_config(config)
                console.print(f"[green]Set to use WhatsApp export files from: {export_path}[/green]")
                console.print(Panel("""
                [bold]WhatsApp Export Instructions:[/bold]
                
                1. In WhatsApp Web, open a chat you want to monitor
                2. Click the three dots (menu) at the top right
                3. Select "More" > "Export chat"
                4. Choose "Without media" 
                5. Save the file to your configured downloads folder
                6. Run 'scan-whatsapp --use-export' to process the exported files
                """, title="Export Instructions"))
                return config
    
    # Enable/disable WhatsApp Web integration
    web_enabled = typer.confirm(
        "Enable WhatsApp Web integration?", 
        default=config.get("whatsapp_web_enabled", False)
    )
    config["whatsapp_web_enabled"] = web_enabled
    
    if web_enabled:
        # Browser configuration
        if SELENIUM_AVAILABLE:
            browser_options = ["chrome", "firefox", "edge"]
            console.print("Available browsers:")
            for i, browser in enumerate(browser_options, 1):
                console.print(f"{i}. {browser}")
            
            browser_choice = typer.prompt(
                "Select browser (1-3)", 
                default="1"
            )
            try:
                browser_idx = int(browser_choice) - 1
                if 0 <= browser_idx < len(browser_options):
                    config["browser_type"] = browser_options[browser_idx]
            except ValueError:
                console.print("[yellow]Invalid choice. Using Chrome as default.[/yellow]")
                config["browser_type"] = "chrome"
            
            # Headless mode
            headless = typer.confirm(
                "Run browser in headless mode? (not recommended for initial setup)", 
                default=config.get("headless", False)
            )
            config["headless"] = headless
            
            # Auto-scan in background
            auto_scan = typer.confirm(
                "Enable automatic background scanning?", 
                default=config.get("auto_scan", False)
            )
            config["auto_scan"] = auto_scan
        
        # Configure scan interval
        scan_interval = typer.prompt(
            "How often to scan messages (in minutes)", 
            default=config.get("scan_interval", 3600) // 60,
            type=int
        )
        config["scan_interval"] = scan_interval * 60  # Convert to seconds
        
        # Configure max messages per chat
        max_messages = typer.prompt(
            "Maximum number of recent messages to scan per chat", 
            default=config.get("max_messages_per_chat", 50),
            type=int
        )
        config["max_messages_per_chat"] = max_messages
        
        # Configure monitored groups
        existing_groups = config.get("monitored_groups", [])
        console.print(f"Currently monitoring {len(existing_groups)} groups:")
        for i, group in enumerate(existing_groups, 1):
            console.print(f"{i}. {group}")
        
        if typer.confirm("Would you like to modify the list of monitored groups?"):
            # Clear existing groups if requested
            if existing_groups and typer.confirm("Clear all existing groups?", default=False):
                existing_groups = []
            
            # Add new groups
            while typer.confirm("Add a group to monitor?", default=True if not existing_groups else False):
                group_name = typer.prompt("Enter group name (exact name as in WhatsApp)")
                existing_groups.append(group_name)
            
            config["monitored_groups"] = existing_groups
        
        # Configure additional filters
        if typer.confirm("Configure message filtering options?", default=False):
            min_words = typer.prompt(
                "Minimum words in message (to filter out short messages)", 
                default=config.get("filters", {}).get("min_words", 5),
                type=int
            )
            ignore_media = typer.confirm(
                "Ignore media messages?", 
                default=config.get("filters", {}).get("ignore_media", True)
            )
            
            config["filters"] = {
                "min_words": min_words,
                "ignore_media": ignore_media
            }
        
        console.print(f"WhatsApp integration configured to scan {len(existing_groups)} groups every {scan_interval} minutes.")
    else:
        console.print("WhatsApp integration disabled.")
    
    save_whatsapp_config(config)
    
    if web_enabled:
        console.print(Panel("""
        [bold]WhatsApp Web Integration Instructions:[/bold]
        
        1. The CLI will attempt to open WhatsApp Web at https://web.whatsapp.com/
        2. You'll need to scan the QR code with your phone the first time
        3. After authentication, the CLI will be able to scan your messages
        4. You can manually scan for tasks using the 'scan-whatsapp' command
        
        Note: To maintain your session, avoid closing WhatsApp Web completely.
        """, title="Setup Instructions"))
        
        # Offer to test connection now
        if typer.confirm("Would you like to test your WhatsApp Web connection now?", default=True):
            test_whatsapp_connection()
    
    return config

def test_whatsapp_connection():
    """Test the WhatsApp Web connection."""
    config = load_whatsapp_config()
    
    if not config.get("whatsapp_web_enabled", False):
        console.print("[yellow]WhatsApp integration is not enabled. Run 'configure-whatsapp' first.[/yellow]")
        return False
    
    if not SELENIUM_AVAILABLE:
        console.print("[red]Browser automation libraries not available. Cannot test connection.[/red]")
        return False
    
    try:
        console.print("[cyan]Testing WhatsApp Web connection...[/cyan]")
        driver = get_whatsapp_driver(headless=False)  # Force non-headless for the test
        
        # Wait for WhatsApp Web to load
        wait = WebDriverWait(driver, 30)
        try:
            # Check for QR code (not logged in)
            qr_code = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="qrcode"]')))
            console.print("[yellow]Please scan the QR code with your phone to log in to WhatsApp Web.[/yellow]")
            
            # Wait for successful login
            try:
                # Wait for the main chat list to appear (indicates successful login)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list"]')))
                console.print("[green]Successfully logged in to WhatsApp Web![/green]")
                
                # Update the config
                config["last_successful_login"] = datetime.datetime.now().isoformat()
                save_whatsapp_config(config)
                
                result = True
            except TimeoutException:
                console.print("[red]Login timeout. Failed to detect successful login.[/red]")
                result = False
                
        except TimeoutException:
            # No QR code found, might be already logged in
            try:
                # Check for chat list
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list"]')))
                console.print("[green]Already logged in to WhatsApp Web![/green]")
                
                # Update the config
                config["last_successful_login"] = datetime.datetime.now().isoformat()
                save_whatsapp_config(config)
                
                result = True
            except TimeoutException:
                console.print("[red]Failed to detect WhatsApp Web interface.[/red]")
                result = False
        
        # Test accessing monitored groups
        if result and config.get("monitored_groups"):
            groups_found = 0
            groups_not_found = []
            
            for group_name in config["monitored_groups"]:
                try:
                    # Try to find the group in the chat list
                    search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list-search"]')))
                    search_input = search_box.find_element(By.TAG_NAME, 'input')
                    search_input.clear()
                    search_input.send_keys(group_name)
                    
                    time.sleep(2)  # Wait for search results
                    
                    # Look for the chat in search results
                    chats = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cell-frame-title"]')
                    found = False
                    for chat in chats:
                        if chat.text.strip() == group_name:
                            groups_found += 1
                            found = True
                            break
                    
                    if not found:
                        groups_not_found.append(group_name)
                        
                except Exception as e:
                    console.print(f"[yellow]Error searching for group '{group_name}': {e}[/yellow]")
                    groups_not_found.append(group_name)
            
            if groups_found == len(config["monitored_groups"]):
                console.print(f"[green]All {groups_found} monitored groups found![/green]")
            else:
                console.print(f"[yellow]Found {groups_found} out of {len(config['monitored_groups'])} monitored groups.[/yellow]")
                console.print(f"[yellow]Groups not found: {', '.join(groups_not_found)}[/yellow]")
            
        return result
        
    except Exception as e:
        console.print(f"[red]Error testing WhatsApp Web connection: {e}[/red]")
        return False
    finally:
        try:
            driver.quit()
        except:
            pass

# Rest of the functions remain the same...
# [The rest of the file continues with the same functions]

# When run directly, initialize the module
if __name__ == "__main__":
    # This could be used for testing the module directly
    init_whatsapp_integration()
    config = load_whatsapp_config()
    
    if config.get("auto_scan", False):
        console.print("Starting background scanner...")
        scanner_thread = run_background_scanner()
    
    # Test task extraction
    try:
        if SELENIUM_AVAILABLE:
            console.print("Testing WhatsApp Web connection...")
            test_whatsapp_connection()
        else:
            console.print("Selenium not available. Cannot test WhatsApp Web connection.")
    except Exception as e:
        console.print(f"Error testing connection: {e}")