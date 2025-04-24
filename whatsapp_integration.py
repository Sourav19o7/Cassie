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
    SELENIUM_AVAILABLE = False

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

def get_whatsapp_driver(headless=None):
    """Initialize and return a WebDriver for WhatsApp Web."""
    config = load_whatsapp_config()
    
    if headless is None:
        headless = config.get("headless", False)
    
    browser_type = config.get("browser_type", "chrome").lower()
    
    if browser_type == "chrome":
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-dev-shm-usage")
        
        # Add user data directory to maintain session
        options.add_argument(f"--user-data-dir={WHATSAPP_SESSION_PATH}")
        
        # Install or update chromedriver
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            console.print(f"[red]Error initializing Chrome WebDriver: {e}[/red]")
            raise
            
    elif browser_type == "firefox":
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from webdriver_manager.firefox import GeckoDriverManager
        
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        
        # Add Firefox profile path
        profile_path = WHATSAPP_SESSION_PATH / "firefox_profile"
        if not profile_path.exists():
            profile_path.mkdir(parents=True)
        options.add_argument("-profile")
        options.add_argument(str(profile_path))
        
        try:
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)
        except Exception as e:
            console.print(f"[red]Error initializing Firefox WebDriver: {e}[/red]")
            raise
            
    elif browser_type == "edge":
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        options = EdgeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--window-size=1280,800")
        
        # Add user data directory for Edge
        edge_data_dir = WHATSAPP_SESSION_PATH / "edge_data"
        if not edge_data_dir.exists():
            edge_data_dir.mkdir(parents=True)
        options.add_argument(f"--user-data-dir={edge_data_dir}")
        
        try:
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=options)
        except Exception as e:
            console.print(f"[red]Error initializing Edge WebDriver: {e}[/red]")
            raise
    else:
        raise ValueError(f"Unsupported browser type: {browser_type}")
    
    # Navigate to WhatsApp Web
    driver.get("https://web.whatsapp.com/")
    
    return driver

def is_message_processed(message_id, group_name):
    """Check if a message has already been processed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT 1 FROM whatsapp_processed_messages WHERE message_id = ? AND group_name = ?",
        (message_id, group_name)
    )
    
    result = cursor.fetchone() is not None
    conn.close()
    
    return result

def mark_message_processed(message_id, group_name, sender):
    """Mark a message as processed in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR IGNORE INTO whatsapp_processed_messages (message_id, group_name, sender, processed_date) VALUES (?, ?, ?, ?)",
        (message_id, group_name, sender, datetime.datetime.now().isoformat())
    )
    
    conn.commit()
    conn.close()

def get_messages_from_group(driver, group_name, max_messages=50):
    """
    Get messages from a specific WhatsApp group.
    
    Args:
        driver: Selenium WebDriver instance
        group_name: Name of the group to get messages from
        max_messages: Maximum number of messages to get
        
    Returns:
        List of message dictionaries
    """
    wait = WebDriverWait(driver, 20)
    
    try:
        # Search for the group
        search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list-search"]')))
        search_input = search_box.find_element(By.TAG_NAME, 'input')
        search_input.clear()
        search_input.send_keys(group_name)
        
        time.sleep(2)  # Wait for search results
        
        # Find and click on the group chat
        group_found = False
        chats = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cell-frame-title"]')
        for chat in chats:
            if chat.text.strip() == group_name:
                chat.click()
                group_found = True
                break
        
        if not group_found:
            console.print(f"[yellow]Group '{group_name}' not found in chat list.[/yellow]")
            return []
        
        # Wait for chat to load
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="conversation-panel-messages"]')))
        time.sleep(2)  # Wait for messages to load
        
        # Scroll to load more messages if needed
        messages_container = driver.find_element(By.CSS_SELECTOR, 'div[data-testid="conversation-panel-messages"]')
        driver.execute_script("arguments[0].scrollTop = 0;", messages_container)  # Scroll to top to get newest messages
        
        # Get all message elements
        message_elements = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="msg-container"]')
        messages = []
        
        # Process the most recent messages (up to max_messages)
        for element in message_elements[-max_messages:] if len(message_elements) > max_messages else message_elements:
            try:
                # Check if it's a text message (skip media/docs/etc.)
                text_elements = element.find_elements(By.CSS_SELECTOR, 'div[data-testid="msg-text"]')
                if not text_elements:
                    continue
                
                # Get message text
                message_text = text_elements[0].text
                
                # Get sender (for group chats)
                try:
                    sender_element = element.find_element(By.CSS_SELECTOR, 'div[data-testid="msg-meta"] span')
                    sender = sender_element.text
                except NoSuchElementException:
                    # If sender not found, it might be your own message
                    sender = "You"
                
                # Get message ID (data-id attribute)
                message_id = element.get_attribute("data-id")
                
                # Get timestamp
                try:
                    time_element = element.find_element(By.CSS_SELECTOR, 'div[data-testid="msg-meta"] div[role="button"]')
                    timestamp = time_element.get_attribute("aria-label")
                    # Parse something like "12:34 PM" to a datetime
                    current_date = datetime.datetime.now().date()
                    time_str = timestamp.strip()
                    try:
                        # Try to parse time from the aria-label
                        if ":" in time_str:
                            # Extract just the time part
                            time_str = re.search(r'\d{1,2}:\d{2}(?:\s?[APap][Mm])?', time_str).group(0)
                            if "AM" in time_str or "PM" in time_str:
                                time_obj = datetime.datetime.strptime(time_str, "%I:%M %p").time()
                            else:
                                time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
                            timestamp = datetime.datetime.combine(current_date, time_obj).isoformat()
                        else:
                            timestamp = datetime.datetime.now().isoformat()
                    except (ValueError, AttributeError):
                        timestamp = datetime.datetime.now().isoformat()
                except NoSuchElementException:
                    timestamp = datetime.datetime.now().isoformat()
                
                # Check if already processed
                if is_message_processed(message_id, group_name):
                    continue
                
                # Add to messages list
                messages.append({
                    "group": group_name,
                    "sender": sender,
                    "message": message_text,
                    "timestamp": timestamp,
                    "message_id": message_id
                })
                
            except Exception as e:
                console.print(f"[yellow]Error processing message: {e}[/yellow]")
                continue
        
        return messages
        
    except Exception as e:
        console.print(f"[red]Error getting messages from group '{group_name}': {e}[/red]")
        return []

def get_whatsapp_messages_from_export(export_path=None):
    """
    Parse WhatsApp chat export files to extract messages.
    
    Args:
        export_path: Path to directory containing WhatsApp export files
        
    Returns:
        List of message dictionaries
    """
    config = load_whatsapp_config()
    
    if not export_path:
        export_path = config.get("export_path", str(Path.home() / "Downloads"))
    
    export_dir = Path(export_path)
    if not export_dir.exists():
        console.print(f"[red]Export directory not found: {export_path}[/red]")
        return []
    
    # Look for WhatsApp chat export files (typically named "WhatsApp Chat with Group Name.txt")
    export_files = list(export_dir.glob("WhatsApp Chat with *.txt"))
    
    if not export_files:
        console.print(f"[yellow]No WhatsApp chat export files found in {export_path}[/yellow]")
        return []
    
    console.print(f"[cyan]Found {len(export_files)} WhatsApp chat export files.[/cyan]")
    
    messages = []
    monitored_groups = config.get("monitored_groups", [])
    
    for file_path in export_files:
        try:
            # Extract group name from filename
            filename = file_path.name
            group_name = filename.replace("WhatsApp Chat with ", "").replace(".txt", "")
            
            # Check if this group is monitored (if groups are specified)
            if monitored_groups and group_name not in monitored_groups:
                continue
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                chat_text = f.read()
            
            # Parse messages
            # Pattern to match messages like: "[dd/mm/yy, HH:MM:SS] Sender Name: Message text"
            pattern = r'\[(\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}(?::\d{2})?\s?(?:[APap][Mm])?)\]\s([^:]+):\s(.+)'
            matches = re.findall(pattern, chat_text, re.MULTILINE)
            
            # Convert matches to message dictionaries
            max_messages = config.get("max_messages_per_chat", 50)
            
            for datetime_str, sender, message_text in matches[-max_messages:]:
                # Create a unique message ID
                message_id = f"{group_name}_{sender}_{datetime_str}_{hash(message_text)}"
                
                # Check if already processed
                if is_message_processed(message_id, group_name):
                    continue
                
                # Parse timestamp
                try:
                    # Try different date formats
                    if '/' in datetime_str:
                        # Try dd/mm/yy format first
                        try:
                            dt = datetime.datetime.strptime(datetime_str, "%d/%m/%y, %H:%M:%S")
                        except ValueError:
                            try:
                                dt = datetime.datetime.strptime(datetime_str, "%d/%m/%y, %H:%M")
                            except ValueError:
                                try:
                                    dt = datetime.datetime.strptime(datetime_str, "%d/%m/%Y, %H:%M:%S")
                                except ValueError:
                                    dt = datetime.datetime.strptime(datetime_str, "%d/%m/%Y, %H:%M")
                    else:
                        dt = datetime.datetime.now()
                    
                    timestamp = dt.isoformat()
                except ValueError:
                    timestamp = datetime.datetime.now().isoformat()
                
                # Add to messages list
                messages.append({
                    "group": group_name,
                    "sender": sender.strip(),
                    "message": message_text,
                    "timestamp": timestamp,
                    "message_id": message_id
                })
                
        except Exception as e:
            console.print(f"[yellow]Error processing export file {file_path}: {e}[/yellow]")
            continue
    
    return messages

def get_whatsapp_messages(use_export=False):
    """
    Get WhatsApp messages using either WebDriver or export files.
    
    Args:
        use_export: Whether to use export files instead of WebDriver
        
    Returns:
        List of message dictionaries
    """
    config = load_whatsapp_config()
    
    if not config.get("whatsapp_web_enabled", False):
        console.print("[yellow]WhatsApp integration is not enabled. Run 'configure-whatsapp' first.[/yellow]")
        return []
    
    # Use export-based approach if specified
    if use_export or config.get("use_export", False):
        return get_whatsapp_messages_from_export()
    
    # Otherwise use WebDriver
    if not SELENIUM_AVAILABLE:
        console.print("[red]Browser automation libraries not available. Cannot scan WhatsApp messages.[/red]")
        console.print("[yellow]You can install them with: pip install selenium webdriver-manager[/yellow]")
        console.print("[yellow]Alternatively, use 'configure-whatsapp' to set up export-based scanning.[/yellow]")
        return []
    
    monitored_groups = config.get("monitored_groups", [])
    if not monitored_groups:
        console.print("[yellow]No WhatsApp groups configured for monitoring.[/yellow]")
        return []
    
    console.print("[cyan]Scanning WhatsApp messages...[/cyan]")
    
    try:
        driver = get_whatsapp_driver()
        wait = WebDriverWait(driver, 30)
        
        # Wait for WhatsApp Web to load and check login status
        try:
            # Check for QR code (not logged in)
            qr_code = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="qrcode"]')))
            console.print("[yellow]Please scan the QR code with your phone to log in to WhatsApp Web.[/yellow]")
            
            # Wait for successful login
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list"]')))
                console.print("[green]Successfully logged in to WhatsApp Web![/green]")
            except TimeoutException:
                console.print("[red]Login timeout. Failed to scan WhatsApp messages.[/red]")
                driver.quit()
                return []
                
        except TimeoutException:
            # No QR code found, might be already logged in
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list"]')))
                console.print("[green]Already logged in to WhatsApp Web![/green]")
            except TimeoutException:
                console.print("[red]Failed to detect WhatsApp Web interface.[/red]")
                driver.quit()
                return []
        
        # Get messages from each monitored group
        max_messages = config.get("max_messages_per_chat", 50)
        all_messages = []
        
        for group_name in monitored_groups:
            console.print(f"[cyan]Scanning messages from '{group_name}'...[/cyan]")
            group_messages = get_messages_from_group(driver, group_name, max_messages)
            console.print(f"[green]Found {len(group_messages)} new messages from '{group_name}'.[/green]")
            all_messages.extend(group_messages)
        
        return all_messages
        
    except Exception as e:
        console.print(f"[red]Error scanning WhatsApp messages: {e}[/red]")
        return []
    finally:
        try:
            driver.quit()
        except:
            pass

def extract_tasks_from_messages(messages, problem_id=None):
    """
    Extract actionable tasks from WhatsApp messages using Claude.
    
    Args:
        messages: List of dicts with 'group', 'sender', 'message', 'timestamp'
        problem_id: Optional ID of problem to associate tasks with
    
    Returns:
        List of extracted tasks
    """
    if not messages:
        return []
    
    # Apply filters from config
    config = load_whatsapp_config()
    filters = config.get("filters", {})
    min_words = filters.get("min_words", 5)
    
    filtered_messages = []
    for msg in messages:
        # Skip very short messages
        word_count = len(msg["message"].split())
        if word_count < min_words:
            continue
        
        filtered_messages.append(msg)
    
    if not filtered_messages:
        return []
    
    # Format messages for Claude
    message_text = "\n\n".join([
        f"Group: {msg['group']}\nSender: {msg['sender']}\nTime: {msg['timestamp']}\nMessage: {msg['message']}"
        for msg in filtered_messages
    ])
    
    prompt = f"""
    Please analyze these WhatsApp messages and extract any actionable tasks or todo items.
    For each task you identify, please provide:
    1. A clear task description
    2. The priority level (high, medium, or low)
    3. The group and sender it came from
    
    Only extract tasks that represent actual action items, requests, assignments, or commitments - ignore general conversation.
    Look for language that indicates tasks like "can you", "please do", "we need to", "I'll handle", etc.
    
    Format your response as a JSON array of task objects, each with "task_description", "priority", "group", and "sender" fields.
    
    Messages to analyze:
    {message_text}
    
    Example output format:
    [
      {{
        "task_description": "Research pricing options for new software",
        "priority": "high",
        "group": "Project Team",
        "sender": "John Smith"
      }},
      {{
        "task_description": "Schedule meeting with client for Friday",
        "priority": "medium",
        "group": "Sales Team",
        "sender": "Jane Doe"
      }}
    ]
    
    If no actionable tasks are found, return an empty array: []
    """
    
    response = call_claude_api(prompt, max_tokens=1000)
    
    if not response:
        return []
    
    try:
        # Extract JSON from the response
        json_str = response.strip()
        # Find the first '[' and last ']' to extract just the JSON array
        start = json_str.find('[')
        end = json_str.rfind(']') + 1
        if start != -1 and end != 0:
            json_str = json_str[start:end]
            tasks = json.loads(json_str)
            
            # Associate with original message data
            for task in tasks:
                # Find the original message this task came from
                for msg in filtered_messages:
                    if msg['group'] == task['group'] and msg['sender'] == task['sender']:
                        task['message'] = msg['message']
                        task['timestamp'] = msg['timestamp']
                        task['message_id'] = msg.get('message_id', f"{msg['group']}_{msg['sender']}_{msg['timestamp']}")
                        
                        # Mark the message as processed
                        mark_message_processed(task['message_id'], task['group'], task['sender'])
                        break
                
                # Set problem_id if provided
                if problem_id:
                    task['problem_id'] = problem_id
            
            return tasks
        return []
    except Exception as e:
        console.print(f"[yellow]Error parsing Claude response: {e}[/yellow]")
        return []

def save_tasks_to_database(tasks):
    """Save extracted tasks to the database."""
    if not tasks:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tasks_added = 0
    
    for task in tasks:
        try:
            problem_id = task.get('problem_id')
            message_id = task.get('message_id', f"{task['group']}_{task['sender']}_{task.get('timestamp', datetime.datetime.now().isoformat())}")
            
            # Check if this message_id already exists in tasks
            cursor.execute(
                "SELECT 1 FROM whatsapp_tasks WHERE message_id = ?",
                (message_id,)
            )
            if cursor.fetchone():
                # Task already exists, skip
                continue
            
            cursor.execute(
                """
                INSERT INTO whatsapp_tasks 
                (problem_id, group_name, sender, message, task_description, timestamp, status, priority, message_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    problem_id,
                    task['group'],
                    task['sender'],
                    task.get('message', ''),
                    task['task_description'],
                    task.get('timestamp', datetime.datetime.now().isoformat()),
                    task['priority'],
                    message_id
                )
            )
            tasks_added += 1
        except Exception as e:
            console.print(f"[yellow]Error saving task: {e}[/yellow]")
    
    conn.commit()
    conn.close()
    
    return tasks_added

def scan_whatsapp_for_tasks(problem_id=None, use_export=False):
    """
    Scan WhatsApp messages and extract actionable tasks.
    
    Args:
        problem_id: Optional ID of problem to associate tasks with
        use_export: Whether to use chat export files instead of WebDriver
    
    Returns:
        Number of tasks extracted
    """
    # If problem_id is provided, check if it exists
    if problem_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM problems WHERE id = ?", (problem_id,))
        if not cursor.fetchone():
            console.print(f"[red]Problem with ID {problem_id} not found.[/red]")
            conn.close()
            return 0
        conn.close()
    
    messages = get_whatsapp_messages(use_export)
    if not messages:
        console.print("[yellow]No new messages found to analyze.[/yellow]")
        return 0
    
    console.print(f"[cyan]Analyzing {len(messages)} WhatsApp messages...[/cyan]")
    tasks = extract_tasks_from_messages(messages, problem_id)
    
    if not tasks:
        console.print("[yellow]No actionable tasks found in the messages.[/yellow]")
        return 0
    
    count = save_tasks_to_database(tasks)
    console.print(f"[green]Extracted and saved {count} new tasks from WhatsApp messages![/green]")
    
    return count

def run_background_scanner():
    """Run WhatsApp scanner in the background at regular intervals."""
    config = load_whatsapp_config()
    
    if not config.get("whatsapp_web_enabled", False) or not config.get("auto_scan", False):
        return
    
    scan_interval = config.get("scan_interval", 3600)  # Default to 1 hour
    
    def background_scan():
        while True:
            try:
                # Reload config in case it changed
                config = load_whatsapp_config()
                if not config.get("whatsapp_web_enabled", False) or not config.get("auto_scan", False):
                    break
                
                # Run the scan
                print(f"[Background] Running WhatsApp scan at {datetime.datetime.now().isoformat()}")
                count = scan_whatsapp_for_tasks(use_export=config.get("use_export", False))
                print(f"[Background] Found {count} new tasks.")
                
                # Sleep until next scan
                scan_interval = config.get("scan_interval", 3600)
                time.sleep(scan_interval)
                
            except Exception as e:
                print(f"[Background] Error in background scanner: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    # Start the background thread
    scanner_thread = threading.Thread(target=background_scan, daemon=True)
    scanner_thread.start()
    
    return scanner_thread

def list_whatsapp_tasks(problem_id=None, status=None, limit=20):
    """List extracted WhatsApp tasks."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT id, problem_id, group_name, sender, task_description, timestamp, status, priority FROM whatsapp_tasks"
    params = []
    where_conditions = []
    
    if problem_id:
        where_conditions.append("problem_id = ?")
        params.append(problem_id)
    
    if status:
        where_conditions.append("status = ?")
        params.append(status)
    
    if where_conditions:
        query += " WHERE " + " AND ".join(where_conditions)
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    tasks = cursor.fetchall()
    
    conn.close()
    
    if not tasks:
        console.print("No WhatsApp tasks found.")
        return
    
    table = Table(title="WhatsApp Tasks")
    table.add_column("ID", style="dim")
    table.add_column("Problem")
    table.add_column("Group")
    table.add_column("Sender")
    table.add_column("Task")
    table.add_column("Date")
    table.add_column("Priority")
    table.add_column("Status")
    
    for task_id, pid, group, sender, description, timestamp, status, priority in tasks:
        # Get problem title if available
        problem_title = "None"
        if pid:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM problems WHERE id = ?", (pid,))
            problem = cursor.fetchone()
            if problem:
                problem_title = f"{pid}: {problem[0]}"
            conn.close()
        
        # Format date
        try:
            date = datetime.datetime.fromisoformat(timestamp).strftime("%Y-%m-%d")
        except:
            date = timestamp
        
        # Set styles based on priority and status
        priority_style = "red" if priority == "high" else "yellow" if priority == "medium" else "blue"
        status_style = "green" if status == "completed" else "yellow"
        
        table.add_row(
            str(task_id), 
            problem_title,
            group, 
            sender, 
            description, 
            date,
            f"[{priority_style}]{priority}[/{priority_style}]",
            f"[{status_style}]{status}[/{status_style}]"
        )
    
    console.print(table)

def update_task_status(task_id, status):
    """Update the status of a WhatsApp task."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return False
    
    cursor.execute(
        "UPDATE whatsapp_tasks SET status = ? WHERE id = ?",
        (status, task_id)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} marked as {status}![/green]")
    return True

def assign_task_to_problem(task_id, problem_id):
    """Assign a WhatsApp task to a specific problem."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if task exists
    cursor.execute("SELECT id FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return False
    
    # Check if problem exists
    cursor.execute("SELECT id FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"[red]Problem with ID {problem_id} not found.[/red]")
        conn.close()
        return False
    
    # Assign task to problem
    cursor.execute(
        "UPDATE whatsapp_tasks SET problem_id = ? WHERE id = ?",
        (problem_id, task_id)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} assigned to problem {problem_id}![/green]")
    return True

def create_action_step_from_task(task_id):
    """Create an action step for a problem from a WhatsApp task."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get task details
    cursor.execute(
        "SELECT problem_id, task_description FROM whatsapp_tasks WHERE id = ?", 
        (task_id,)
    )
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return False
    
    problem_id, description = task
    
    if not problem_id:
        console.print("[yellow]Task is not assigned to any problem. Assign it first.[/yellow]")
        conn.close()
        return False
    
    # Add action step to the problem
    cursor.execute(
        "INSERT INTO action_steps (problem_id, description) VALUES (?, ?)",
        (problem_id, description)
    )
    
    # Mark the task as converted
    cursor.execute(
        "UPDATE whatsapp_tasks SET status = 'converted' WHERE id = ?",
        (task_id,)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} converted to action step for problem {problem_id}![/green]")
    return True

def view_task_details(task_id):
    """View detailed information about a WhatsApp task."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT id, problem_id, group_name, sender, message, task_description, 
               timestamp, status, priority, message_id
        FROM whatsapp_tasks 
        WHERE id = ?
        """, 
        (task_id,)
    )
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return
    
    task_id, problem_id, group, sender, message, description, timestamp, status, priority, message_id = task
    
    # Get problem title if available
    problem_title = "Not assigned"
    if problem_id:
        cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
        problem = cursor.fetchone()
        if problem:
            problem_title = problem[0]
    
    conn.close()
    
    # Format date
    try:
        date = datetime.datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
    except:
        date = timestamp
    
    # Set styles based on priority and status
    priority_style = "red" if priority == "high" else "yellow" if priority == "medium" else "blue"
    status_style = "green" if status == "completed" else "yellow" if status == "pending" else "cyan"
    
    # Display task details
    console.print(Panel(
        f"[bold]Task ID:[/bold] {task_id}\n\n"
        f"[bold]Source:[/bold] {group} (from {sender})\n"
        f"[bold]Date:[/bold] {date}\n"
        f"[bold]Problem:[/bold] {problem_title}\n"
        f"[bold]Priority:[/bold] [{priority_style}]{priority}[/{priority_style}]\n"
        f"[bold]Status:[/bold] [{status_style}]{status}[/{status_style}]\n\n"
        f"[bold]Task Description:[/bold]\n{description}\n\n"
        f"[bold]Original Message:[/bold]\n{message}",
        title="WhatsApp Task Details", 
        border_style="green"))
    
    # Show available actions
    console.print("\n[bold]Available Actions:[/bold]")
    console.print(f"1. Mark as completed: empathic-solver whatsapp-complete-task {task_id}")
    console.print(f"2. Assign to problem: empathic-solver whatsapp-assign-task {task_id} <problem_id>")
    console.print(f"3. Convert to action step: empathic-solver whatsapp-convert-task {task_id}")
    console.print(f"4. Update priority: empathic-solver whatsapp-priority {task_id} <high|medium|low>")
    
    return True

def delete_task(task_id):
    """Delete a WhatsApp task."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return False
    
    cursor.execute("DELETE FROM whatsapp_tasks WHERE id = ?", (task_id,))
    
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} deleted![/green]")
    return True

def update_task_priority(task_id, priority):
    """Update the priority of a WhatsApp task."""
    valid_priorities = ["high", "medium", "low"]
    if priority not in valid_priorities:
        console.print(f"[red]Invalid priority. Choose from: {', '.join(valid_priorities)}[/red]")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return False
    
    cursor.execute(
        "UPDATE whatsapp_tasks SET priority = ? WHERE id = ?",
        (priority, task_id)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} priority set to {priority}![/green]")
    return True

# Main functions to be called from CLI commands
def command_configure_whatsapp():
    """Command to configure WhatsApp integration."""
    init_whatsapp_integration()
    configure_whatsapp()

def command_scan_whatsapp(problem_id=None):
    """Command to scan WhatsApp messages for actionable tasks."""
    init_whatsapp_integration()
    config = load_whatsapp_config()
    
    # Check if we should use export files
    use_export = config.get("use_export", False)
    
    count = scan_whatsapp_for_tasks(problem_id, use_export)
    
    if count > 0:
        console.print(f"[green]Found {count} actionable tasks from WhatsApp messages![/green]")
        list_whatsapp_tasks(problem_id=problem_id, limit=count)
    else:
        console.print("[yellow]No actionable tasks found in WhatsApp messages.[/yellow]")

def command_list_whatsapp_tasks(problem_id=None, status=None, limit=20):
    """Command to list extracted WhatsApp tasks."""
    init_whatsapp_integration()
    list_whatsapp_tasks(problem_id, status, limit)

def command_complete_whatsapp_task(task_id):
    """Command to mark a WhatsApp task as completed."""
    init_whatsapp_integration()
    update_task_status(task_id, "completed")

def command_pending_whatsapp_task(task_id):
    """Command to mark a WhatsApp task as pending."""
    init_whatsapp_integration()
    update_task_status(task_id, "pending")

def command_assign_whatsapp_task(task_id, problem_id):
    """Command to assign a WhatsApp task to a problem."""
    init_whatsapp_integration()
    assign_task_to_problem(task_id, problem_id)

def command_convert_whatsapp_task(task_id):
    """Command to convert a WhatsApp task to an action step."""
    init_whatsapp_integration()
    create_action_step_from_task(task_id)

def command_view_whatsapp_task(task_id):
    """Command to view details of a WhatsApp task."""
    init_whatsapp_integration()
    view_task_details(task_id)

def command_delete_whatsapp_task(task_id):
    """Command to delete a WhatsApp task."""
    init_whatsapp_integration()
    delete_task(task_id)

def command_update_whatsapp_task_priority(task_id, priority):
    """Command to update the priority of a WhatsApp task."""
    init_whatsapp_integration()
    update_task_priority(task_id, priority)

# Start background scanner when module is imported
def start_background_scanner():
    config = load_whatsapp_config()
    if config.get("whatsapp_web_enabled", False) and config.get("auto_scan", False):
        console.print("[cyan]Starting WhatsApp background scanner...[/cyan]")
        run_background_scanner()

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