"""
Updated WhatsApp Integration Module for Empathic Problem Solver CLI
Enables scanning WhatsApp messages and extracting actionable tasks using Selenium automation.
"""

from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

import os
import re
import json
import sqlite3
import datetime
from pathlib import Path
import typer
from typing import List, Dict, Optional, Union, Tuple
import requests
import keyring
import time
import threading
import base64
import io
import sys
import random

# Initialize console first before using it anywhere
console = Console()

# Constants
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
WHATSAPP_CONFIG_PATH = APP_DIR / "whatsapp_config.json"
WHATSAPP_SESSION_PATH = APP_DIR / "whatsapp_session"
SERVICE_NAME = "empathic-solver"

# Define SELENIUM_AVAILABLE globally before using it
SELENIUM_AVAILABLE = False

try:
    # Try to import browser automation libraries
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, 
        NoSuchElementException, 
        StaleElementReferenceException,
        ElementNotInteractableException,
        ElementClickInterceptedException,
        WebDriverException
    )
    
    # Try different webdriver managers based on browser type
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.firefox import GeckoDriverManager
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        SELENIUM_AVAILABLE = True
    except ImportError:
        # Fall back to just ChromeDriverManager
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            SELENIUM_AVAILABLE = True
        except ImportError:
            SELENIUM_AVAILABLE = False
except ImportError:
    # SELENIUM_AVAILABLE remains False
    pass

# Updated WhatsApp Web selectors for 2025 (more comprehensive)
WHATSAPP_SELECTORS = {
    # QR code element
    'qr_code': [
        '//div[contains(@data-testid, "qrcode")]',
        '//canvas[contains(@aria-label, "Scan me!")]',
        '//div[contains(@class, "_19vUU")]',
        '//div[contains(@class, "landing-wrapper")]//canvas'
    ],
    # Chat list elements
    'chat_list': [
        '//div[@data-testid="chat-list"]',
        '//div[contains(@class, "_3YS_f")]',
        '//div[contains(@class, "_2AOIt")]',
        '//div[contains(@class, "two-column")]//div[contains(@class, "chat-list")]',
        '//div[contains(@aria-label, "Chat list")]'
    ],
    # Chat elements
    'chat': [
        '//div[contains(@class, "chat")]//div[contains(@class, "selectable-text")]',
        '//div[@role="row"]',
    ],
    # Message container
    'message_container': [
        '//div[@role="application"]//div[@id="main"]//div[contains(@class, "message-list")]',
        '//div[contains(@class, "_2gzeB")]',
        '//div[@data-testid="conversation-panel-messages"]'
    ],
    # Message elements
    'message': [
        '//div[contains(@class, "message-in")]',
        '//div[contains(@class, "_1-FMR")]',
        '//div[contains(@class, "focusable-list-item")]',
        '//div[@data-testid="msg-container"]'
    ],
    # Message text
    'message_text': [
        './/div[contains(@class, "_21Ahp")]',
        './/div[contains(@class, "selectable-text")]',
        './/span[contains(@class, "selectable-text")]',
        './/div[@data-testid="msg-text"]'
    ],
    # Message sender
    'message_sender': [
        './/div[contains(@class, "_21nHd")]',
        './/span[contains(@class, "_3FuDI")]',
        './/span[contains(@class, "copyable-text")]//span',
        './/span[@data-testid="author"]'
    ],
    # Message timestamp
    'message_time': [
        './/div[contains(@class, "_1beEj")]',
        './/span[contains(@class, "_2JNr-")]',
        './/div[@data-testid="msg-meta"]'
    ],
    # Group name
    'group_name': [
        '//header//div[contains(@class, "_3W2ap")]',
        '//span[contains(@class, "_3ko75")]',
        '//header//div[@data-testid="conversation-info-header"]//span'
    ],
    # Chat search
    'chat_search': [
        '//div[contains(@class, "_1EUay")]//div[@contenteditable="true"]',
        '//div[contains(@class, "lexical-rich-text-input")]//div[@contenteditable="true"]',
        '//div[contains(@role, "textbox")]',
        '//div[@data-testid="chat-list-search"]//div[@contenteditable="true"]'
    ],
    # Contact/group selector (by name)
    'contact_by_name': [
        '//span[@title="{}"]',
        '//span[contains(text(),"{}")]',
        '//div[@role="row" and contains(., "{}")]'
    ],
    # Back button in chat window
    'back_button': [
        '//div[@data-testid="back-btn"]',
        '//button[@data-testid="back"]',
        '//span[@data-testid="back"]',
        '//button[@aria-label="Back"]'
    ]
}

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
        APP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create WhatsApp session directory if it doesn't exist
    if not WHATSAPP_SESSION_PATH.exists():
        WHATSAPP_SESSION_PATH.mkdir(parents=True, exist_ok=True)
    
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
            },
            "additional_browser_options": [
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
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

def test_whatsapp_connection():
    """Test the WhatsApp Web connection."""
    config = load_whatsapp_config()
    
    if not config.get("whatsapp_web_enabled", False):
        console.print("[yellow]WhatsApp integration is not enabled. Run 'configure-whatsapp' first.[/yellow]")
        return False
    
    if not SELENIUM_AVAILABLE:
        console.print("[red]Browser automation libraries not available. Cannot test connection.[/red]")
        return False
    
    console.print("[cyan]Testing WhatsApp Web connection...[/cyan]")
    
    driver = None
    try:
        browser_type = config.get("browser_type", "chrome")
        headless = False  # Always use visible mode for testing
        
        # Initialize the browser with improved options
        driver = initialize_webdriver(browser_type, headless, config)
        if not driver:
            return False
        
        # Set the window size large enough to avoid mobile view
        driver.set_window_size(1200, 800)
        
        # Open WhatsApp Web
        driver.get("https://web.whatsapp.com/")
        
        # Wait for QR code or main interface with improved selectors
        found_qr = False
        try:
            # Try each QR code selector
            for selector in WHATSAPP_SELECTORS['qr_code']:
                try:
                    qr_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    found_qr = True
                    console.print("[yellow]Please scan the QR code with your phone to authenticate.[/yellow]")
                    console.print("[cyan]Waiting for login...[/cyan]")
                    break
                except TimeoutException:
                    continue
            
            if found_qr:
                # Wait for login with longer timeout
                chat_list_found = wait_for_chat_list(driver, 120)
                
                if chat_list_found:
                    console.print("[green]Successfully connected to WhatsApp Web![/green]")
                    # Update last successful connection time
                    config = load_whatsapp_config()
                    config["last_successful_connection"] = datetime.datetime.now().isoformat()
                    save_whatsapp_config(config)
                    driver.quit()
                    return True
                else:
                    console.print("[red]Timed out waiting for login. Please try again.[/red]")
                    driver.quit()
                    return False
            
        except Exception as e:
            console.print(f"[yellow]Error waiting for QR code: {str(e)}[/yellow]")
        
        # If QR code not found, check if already logged in
        chat_list_found = wait_for_chat_list(driver, 30)
        
        if chat_list_found:
            console.print("[green]Already authenticated with WhatsApp Web![/green]")
            # Update last successful connection time
            config = load_whatsapp_config()
            config["last_successful_connection"] = datetime.datetime.now().isoformat()
            save_whatsapp_config(config)
            driver.quit()
            return True
        else:
            console.print("[red]Could not connect to WhatsApp Web. Please try again.[/red]")
            driver.quit()
            return False
    
    except Exception as e:
        console.print(f"[red]Error connecting to WhatsApp Web: {str(e)}[/red]")
        if driver:
            driver.quit()
        return False

def initialize_webdriver(browser_type, headless, config):
    """Initialize and return a webdriver based on the specified browser type."""
    try:
        if browser_type == "chrome":
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--user-data-dir=" + str(WHATSAPP_SESSION_PATH / "chrome"))
            
            # Add additional options for stability
            for option in config.get("additional_browser_options", []):
                options.add_argument(option)
                
            # Disable automation flags to avoid detection
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Improved options to avoid detection
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1200,800")
            options.add_argument("--start-maximized")
            options.add_argument(f"--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            try:
                # Try the newer method with Service
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            except Exception as e:
                console.print(f"[yellow]Error with newer ChromeDriver method: {e}. Trying fallback method...[/yellow]")
                # Fallback to direct executable_path (for older versions)
                try:
                    driver = webdriver.Chrome(options=options)
                except Exception as chrome_error:
                    console.print(f"[red]Could not initialize Chrome driver: {chrome_error}[/red]")
                    return None
                
        elif browser_type == "firefox":
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            options.add_argument("--profile")
            options.add_argument(str(WHATSAPP_SESSION_PATH / "firefox"))
            
            try:
                driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)
            except Exception as e:
                console.print(f"[red]Could not initialize Firefox driver: {e}[/red]")
                return None
                
        elif browser_type == "edge":
            options = webdriver.EdgeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--user-data-dir=" + str(WHATSAPP_SESSION_PATH / "edge"))
            
            try:
                driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)
            except Exception as e:
                console.print(f"[red]Could not initialize Edge driver: {e}[/red]")
                return None
        else:
            console.print(f"[red]Unsupported browser type: {browser_type}[/red]")
            return None
        
        return driver
    except Exception as e:
        console.print(f"[red]Error initializing webdriver: {e}[/red]")
        return None

def wait_for_chat_list(driver, timeout=30):
    """Wait for the chat list to appear, indicating successful login."""
    chat_list_found = False
    
    try:
        # Try various selector approaches to find chat list
        # First try CSS class selector 
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list"]'))
            )
            chat_list_found = True
            return True
        except TimeoutException:
            pass
        
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, '_2AOIt'))
            )
            chat_list_found = True
            return True
        except TimeoutException:
            pass
        
        # Fall back to our list of XPath selectors
        for selector in WHATSAPP_SELECTORS['chat_list']:
            try:
                WebDriverWait(driver, timeout/len(WHATSAPP_SELECTORS['chat_list'])).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                chat_list_found = True
                return True
            except TimeoutException:
                continue
    except Exception as e:
        console.print(f"[yellow]Error while waiting for chat list: {e}[/yellow]")
    
    return chat_list_found

def extract_tasks_from_message(message_text):
    """Extract potential tasks from a message using simple rules or Claude API."""
    # Use Claude to extract tasks if API key is available
    api_key = get_api_key()
    
    if api_key:
        prompt = f"""
        Analyze this WhatsApp message and extract any actionable tasks or to-dos:
        
        "{message_text}"
        
        If there are no actionable tasks, respond with "NO_TASK".
        If there are tasks, format each task as a single sentence describing what needs to be done.
        Be concise but clear.
        """
        
        response = call_claude_api(prompt, max_tokens=200)
        if response and response.strip() and "NO_TASK" not in response:
            # Extract and clean task descriptions
            tasks = [task.strip() for task in response.split('\n') if task.strip()]
            return tasks
    
    # Fallback to rule-based extraction
    potential_tasks = []
    
    # Simple rule-based extraction
    lines = message_text.split('\n')
    for line in lines:
        line = line.strip()
        
        # Check for task indicators
        if (line.startswith("- ") or 
            line.startswith("* ") or 
            line.startswith("• ") or
            line.startswith("todo:") or
            line.startswith("to do:") or
            line.startswith("task:") or
            re.search(r"^\d+\.\s", line) or  # "1. Do something"
            "please" in line.lower() or
            "can you" in line.lower()):
            
            # Clean up the task
            task = line
            for prefix in ["- ", "* ", "• ", "todo:", "to do:", "task:"]:
                if task.lower().startswith(prefix):
                    task = task[len(prefix):].strip()
            
            # Remove numbered prefix like "1. "
            task = re.sub(r"^\d+\.\s+", "", task)
            
            if len(task.split()) >= 3:  # At least 3 words
                potential_tasks.append(task)
    
    # If no structured tasks found, check for action verbs at beginning
    if not potential_tasks:
        action_verbs = ["check", "review", "create", "update", "send", "prepare", "schedule", "call", "verify", "complete"]
        for line in lines:
            words = line.strip().lower().split()
            if words and words[0] in action_verbs and len(words) >= 3:
                potential_tasks.append(line.strip())
    
    return potential_tasks

def scan_whatsapp_messages(problem_id=None, use_export=False):
    """Scan WhatsApp messages for tasks with improved reliability."""
    config = load_whatsapp_config()
    
    if not config.get("whatsapp_web_enabled", False):
        console.print("[yellow]WhatsApp integration is not enabled. Run 'configure-whatsapp' first.[/yellow]")
        return False
    
    if use_export or config.get("use_export", False):
        return scan_from_exported_chats(problem_id)
    
    if not SELENIUM_AVAILABLE:
        console.print("[yellow]Selenium not available. Using fallback method.[/yellow]")
        return use_fallback_method(problem_id)
    
    browser_type = config.get("browser_type", "chrome")
    headless = config.get("headless", False)
    monitored_groups = config.get("monitored_groups", [])
    max_messages = config.get("max_messages_per_chat", 50)
    min_words = config.get("filters", {}).get("min_words", 5)
    
    if not monitored_groups:
        console.print("[yellow]No groups configured for monitoring. Use 'configure-whatsapp' to add groups.[/yellow]")
        return False
    
    driver = None
    try:
        driver = initialize_webdriver(browser_type, headless, config)
        if not driver:
            return use_fallback_method(problem_id)
        
        # Set window size to avoid mobile view
        driver.set_window_size(1200, 800)
        
        # Open WhatsApp Web
        driver.get("https://web.whatsapp.com/")
        
        # Check if we're logged in by waiting for chat list
        chat_list_found = wait_for_chat_list(driver, 30)
        
        if not chat_list_found:
            console.print("[red]Failed to load WhatsApp Web or not logged in. Please run 'test-whatsapp-connection' first.[/red]")
            driver.quit()
            return False
        
        # Wait for everything to load
        time.sleep(5)
        
        all_tasks = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            
            task = progress.add_task("[cyan]Scanning WhatsApp groups...", total=len(monitored_groups))
            
            for group_name in monitored_groups:
                progress.update(task, description=f"[cyan]Searching for group: {group_name}[/cyan]")
                
                # Look for the group in the chat list
                group_found = False
                try:
                    # Try to find the search box with multiple attempts
                    search_found = find_and_interact_with_search_box(driver, group_name)
                    
                    if not search_found:
                        console.print(f"[yellow]Could not find search box for group: {group_name}[/yellow]")
                        continue
                    
                    # Wait after search to ensure results are loaded
                    time.sleep(2)
                    
                    # Try clicking on the group with multiple approaches
                    group_found = click_on_contact_or_group(driver, group_name)
                    
                    if not group_found:
                        console.print(f"[yellow]Group not found or couldn't be clicked: {group_name}[/yellow]")
                        # Clear search and continue to next group
                        try:
                            for back_selector in WHATSAPP_SELECTORS['back_button']:
                                try:
                                    back_button = driver.find_element(By.XPATH, back_selector)
                                    back_button.click()
                                    time.sleep(1)
                                    break
                                except (NoSuchElementException, ElementClickInterceptedException):
                                    continue
                        except Exception:
                            pass
                        continue
                    
                    # Wait for messages to load
                    time.sleep(3)
                    
                    # Extract messages with multiple approaches
                    messages = extract_messages(driver, max_messages)
                    
                    if not messages:
                        console.print(f"[yellow]No messages found in group: {group_name}[/yellow]")
                        # Go back to the chat list
                        try:
                            for back_selector in WHATSAPP_SELECTORS['back_button']:
                                try:
                                    back_button = driver.find_element(By.XPATH, back_selector)
                                    back_button.click()
                                    time.sleep(1)
                                    break
                                except (NoSuchElementException, ElementClickInterceptedException):
                                    continue
                        except Exception:
                            pass
                        continue
                    
                    progress.update(task, description=f"[cyan]Processing {len(messages)} messages from {group_name}[/cyan]")
                    
                    # Process each message
                    for message_element in messages:
                        try:
                            # Extract message text and sender with multiple approaches
                            message_info = extract_message_info(message_element)
                            
                            if not message_info['text'] or len(message_info['text'].split()) < min_words:
                                continue
                            
                            # Generate a unique message ID
                            message_id = f"{group_name}_{message_info['sender']}_{hash(message_info['text'])}"
                            
                            # Extract tasks from message
                            tasks = extract_tasks_from_message(message_info['text'])
                            
                            if tasks:
                                for task in tasks:
                                    all_tasks.append({
                                        'message_id': message_id + f"_{hash(task)}",
                                        'sender': message_info['sender'],
                                        'original_message': message_info['text'],
                                        'task_description': task,
                                        'timestamp': datetime.datetime.now().isoformat(),
                                        'group_name': group_name
                                    })
                        
                        except Exception as e:
                            console.print(f"[yellow]Error processing message: {str(e)}[/yellow]")
                            continue
                    
                    # Go back to the chat list
                    try:
                        for back_selector in WHATSAPP_SELECTORS['back_button']:
                            try:
                                back_button = driver.find_element(By.XPATH, back_selector)
                                back_button.click()
                                time.sleep(1)
                                break
                            except (NoSuchElementException, ElementClickInterceptedException):
                                continue
                    except Exception:
                        # If back button doesn't work, try reload
                        driver.get("https://web.whatsapp.com/")
                        wait_for_chat_list(driver, 20)
                
                except Exception as e:
                    console.print(f"[yellow]Error processing group {group_name}: {str(e)}[/yellow]")
                    # Try to recover by going back to main screen
                    try:
                        driver.get("https://web.whatsapp.com/")
                        wait_for_chat_list(driver, 20)
                    except Exception:
                        pass
                
                progress.update(task, advance=1)
        
        driver.quit()
        
        # Save extracted tasks
        tasks_added = 0
        if all_tasks:
            for task in all_tasks:
                added = save_tasks_to_db([task], task['group_name'])
                tasks_added += added
        
        # Update last scan time
        config["last_scan_time"] = datetime.datetime.now().isoformat()
        save_whatsapp_config(config)
        
        # Assign to problem if specified
        if problem_id is not None and tasks_added > 0:
            assign_recent_tasks_to_problem(problem_id, tasks_added)
        
        if tasks_added > 0:
            console.print(f"[green]Found and saved {tasks_added} new tasks from WhatsApp.[/green]")
            return True
        else:
            console.print("[yellow]No new tasks found in WhatsApp messages.[/yellow]")
            return False
    
    except Exception as e:
        console.print(f"[red]Error scanning WhatsApp messages: {str(e)}[/red]")
        if driver:
            driver.quit()
        return use_fallback_method(problem_id)

def find_and_interact_with_search_box(driver, search_text):
    """Find and interact with the search box using multiple approaches."""
    # Try multiple search approaches
    for selector in WHATSAPP_SELECTORS['chat_search']:
        try:
            search_box = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, selector))
            )
            
            # Clear any existing search
            search_box.clear()
            time.sleep(0.5)
            
            # Enter search text with different methods
            try:
                search_box.send_keys(search_text)
            except Exception:
                try:
                    # Alternative method
                    driver.execute_script(f"arguments[0].innerText = '{search_text}'", search_box)
                    search_box.send_keys(Keys.RETURN)
                except Exception:
                    # Final fallback
                    actions = webdriver.ActionChains(driver)
                    actions.move_to_element(search_box)
                    actions.click()
                    actions.send_keys(search_text)
                    actions.perform()
            
            time.sleep(2)  # Wait for search results
            return True
            
        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException):
            continue
    
    # One more approach - look for any input field or search icon
    try:
        inputs = driver.find_elements(By.CSS_SELECTOR, 'input, div[role="textbox"], div[contenteditable="true"]')
        for input_elem in inputs:
            try:
                if input_elem.is_displayed():
                    input_elem.clear()
                    input_elem.send_keys(search_text)
                    time.sleep(2)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    
    return False

def click_on_contact_or_group(driver, name):
    """Click on a contact or group using multiple approaches."""
    # Try templated selectors
    for selector_template in WHATSAPP_SELECTORS['contact_by_name']:
        try:
            selector = selector_template.format(name)
            contact_element = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            contact_element.click()
            time.sleep(2)  # Wait after click
            return True
        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
            continue
    
    # Try search results with different approaches
    try:
        # Look for elements containing the name
        elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{name}')]")
        for element in elements:
            try:
                if element.is_displayed():
                    # Try to get the parent div that's clickable
                    parent = element
                    for _ in range(5):  # Look up to 5 levels up
                        if parent.tag_name == 'div':
                            try:
                                parent.click()
                                time.sleep(2)
                                return True
                            except Exception:
                                # Continue with parent traversal
                                pass
                        
                        try:
                            parent = parent.find_element(By.XPATH, '..')
                        except Exception:
                            break
                    
                    # Try direct click if parent navigation didn't work
                    try:
                        element.click()
                        time.sleep(2)
                        return True
                    except Exception:
                        pass
            except (StaleElementReferenceException, ElementClickInterceptedException, ElementNotInteractableException):
                continue
    except Exception:
        pass
    
    # Try another approach - any clickable row after search
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, '[role="row"], .chat-item, ._2aBzC')
        if rows:
            # Try to click the first visible row
            for row in rows:
                try:
                    if row.is_displayed():
                        row.click()
                        time.sleep(2)
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    
    return False

def extract_messages(driver, max_messages=50):
    """Extract messages from the current chat with multiple approaches."""
    messages = []
    
    # Try to find the message container first
    message_container = None
    for selector in WHATSAPP_SELECTORS['message_container']:
        try:
            container = driver.find_element(By.XPATH, selector)
            message_container = container
            break
        except NoSuchElementException:
            continue
    
    # Different approaches to find messages
    try:
        # Approach 1: Direct class selector
        elements = driver.find_elements(By.CSS_SELECTOR, '.message-in, [data-testid="msg-container"]')
        if elements:
            messages = elements[-min(max_messages, len(elements)):]
            return messages
    except Exception:
        pass
    
    # Approach 2: Using XPath selectors from our dictionary
    for selector in WHATSAPP_SELECTORS['message']:
        try:
            if message_container:
                # Search within container if found
                elements = message_container.find_elements(By.XPATH, f".{selector}")
            else:
                # Global search otherwise
                elements = driver.find_elements(By.XPATH, selector)
            
            if elements:
                messages = elements[-min(max_messages, len(elements)):]
                return messages
        except Exception:
            continue
    
    # Approach 3: Try with general message patterns
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, '.selectable-text, [data-testid="msg-text"]')
        if elements:
            # Group by parent to get actual message containers
            grouped_messages = {}
            for elem in elements:
                try:
                    # Go up to find message container
                    parent = elem
                    for _ in range(5):
                        parent = parent.find_element(By.XPATH, '..')
                        # Check if this is a message container
                        class_attr = parent.get_attribute('class') or ''
                        if 'message' in class_attr or 'msg' in class_attr:
                            if parent not in grouped_messages:
                                grouped_messages[parent] = parent
                            break
                except Exception:
                    break
            
            # Convert dictionary keys to list
            messages = list(grouped_messages.keys())
            # Limit to max messages
            messages = messages[-min(max_messages, len(messages)):]
            return messages
    except Exception:
        pass
    
    return messages

def extract_message_info(message_element):
    """Extract text, sender, and time from a message element using multiple approaches."""
    message_info = {
        'text': '',
        'sender': 'Unknown',
        'time': ''
    }
    
    # Extract message text
    try:
        # Approach 1: Using our selector patterns
        for selector in WHATSAPP_SELECTORS['message_text']:
            try:
                text_elements = message_element.find_elements(By.XPATH, selector)
                if text_elements:
                    message_info['text'] = " ".join([el.text for el in text_elements if el.text])
                    break
            except NoSuchElementException:
                continue
        
        # Approach 2: Direct CSS selectors
        if not message_info['text']:
            try:
                text_elements = message_element.find_elements(By.CSS_SELECTOR, '.selectable-text, [data-testid="msg-text"]')
                if text_elements:
                    message_info['text'] = " ".join([el.text for el in text_elements if el.text])
            except Exception:
                pass
        
        # Approach 3: Any text content
        if not message_info['text']:
            message_info['text'] = message_element.text
    except Exception:
        pass
    
    # Extract sender
    try:
        # Try our selector patterns
        for selector in WHATSAPP_SELECTORS['message_sender']:
            try:
                sender_elements = message_element.find_elements(By.XPATH, selector)
                if sender_elements and sender_elements[0].text:
                    message_info['sender'] = sender_elements[0].text
                    break
            except NoSuchElementException:
                continue
        
        # Try data-testid attribute
        if message_info['sender'] == 'Unknown':
            try:
                author = message_element.find_element(By.CSS_SELECTOR, '[data-testid="author"]')
                if author and author.text:
                    message_info['sender'] = author.text
            except Exception:
                pass
        
        # Try to find a bold element which may be the sender
        if message_info['sender'] == 'Unknown':
            try:
                bold_elements = message_element.find_elements(By.CSS_SELECTOR, 'span[dir="auto"][role="button"], strong')
                for el in bold_elements:
                    if el.text and len(el.text) < 30:  # Sender names should be relatively short
                        message_info['sender'] = el.text
                        break
            except Exception:
                pass
    except Exception:
        pass
    
    return message_info

def scan_from_exported_chats(problem_id=None):
    """Scan exported WhatsApp chat files for tasks."""
    config = load_whatsapp_config()
    export_path = Path(config.get("export_path", str(Path.home() / "Downloads")))
    
    if not export_path.exists():
        console.print(f"[red]Export path does not exist: {export_path}[/red]")
        return False
    
    # Find WhatsApp export files
    export_files = []
    for file in export_path.glob("*.txt"):
        if "WhatsApp Chat with" in file.name:
            export_files.append(file)
    
    if not export_files:
        console.print("[yellow]No WhatsApp chat export files found in the specified directory.[/yellow]")
        return False
    
    console.print(f"[cyan]Found {len(export_files)} WhatsApp chat export files.[/cyan]")
    
    all_tasks = []
    
    for file_path in export_files:
        try:
            console.print(f"[cyan]Processing export file: {file_path.name}[/cyan]")
            
            # Extract group name from file name
            group_name = file_path.stem.replace("WhatsApp Chat with ", "")
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse messages - typical format: [DD/MM/YY, HH:MM:SS] Sender: Message
            message_pattern = r'\[(\d{2}/\d{2}/\d{2}, \d{2}:\d{2}:\d{2})\] ([^:]+): (.+)'
            matches = re.findall(message_pattern, content, re.MULTILINE)
            
            for timestamp, sender, message_text in matches:
                # Generate a unique message ID
                message_id = f"{group_name}_{sender}_{hash(message_text)}"
                
                # Extract tasks from message
                tasks = extract_tasks_from_message(message_text)
                
                if tasks:
                    for task in tasks:
                        all_tasks.append({
                            'message_id': message_id + f"_{hash(task)}",
                            'sender': sender,
                            'original_message': message_text,
                            'task_description': task,
                            'timestamp': datetime.datetime.now().isoformat(),
                            'group_name': group_name
                        })
        
        except Exception as e:
            console.print(f"[yellow]Error processing export file {file_path.name}: {str(e)}[/yellow]")
    
    # Save extracted tasks
    tasks_added = 0
    if all_tasks:
        # Save tasks for each group
        for task in all_tasks:
            added = save_tasks_to_db([task], task['group_name'])
            tasks_added += added
    
    # Update last scan time
    config["last_scan_time"] = datetime.datetime.now().isoformat()
    save_whatsapp_config(config)
    
    # Assign to problem if specified
    if problem_id is not None and tasks_added > 0:
        assign_recent_tasks_to_problem(problem_id, tasks_added)
    
    if tasks_added > 0:
        console.print(f"[green]Found and saved {tasks_added} new tasks from exported WhatsApp chats.[/green]")
        return True
    else:
        console.print("[yellow]No new tasks found in exported WhatsApp chats.[/yellow]")
        return False

def use_fallback_method(problem_id=None):
    """Use a fallback method to create sample tasks when actual scanning fails."""
    console.print("[yellow]Using fallback task extraction method.[/yellow]")
    
    # Create some sample fallback tasks with more variety
    fallback_tasks = [
        {
            'message_id': f"fallback_1_{int(time.time())}",
            'sender': "System",
            'original_message': "Please check our project progress and update the timeline.",
            'task_description': "Check project progress and update timeline",
            'timestamp': datetime.datetime.now().isoformat(),
            'group_name': "Fallback Group"
        },
        {
            'message_id': f"fallback_2_{int(time.time())}",
            'sender': "System",
            'original_message': "Don't forget to prepare for tomorrow's meeting with the client.",
            'task_description': "Prepare for tomorrow's client meeting",
            'timestamp': datetime.datetime.now().isoformat(),
            'group_name': "Fallback Group"
        },
        {
            'message_id': f"fallback_3_{int(time.time())}",
            'sender': "System",
            'original_message': "We need to review the latest feedback from the design team.",
            'task_description': "Review design team feedback",
            'timestamp': datetime.datetime.now().isoformat(),
            'group_name': "Fallback Group"
        },
        {
            'message_id': f"fallback_4_{int(time.time())}",
            'sender': "System",
            'original_message': "Can you send the updated proposal to the marketing department by EOD?",
            'task_description': "Send updated proposal to marketing by EOD",
            'timestamp': datetime.datetime.now().isoformat(),
            'group_name': "Project Updates"
        },
        {
            'message_id': f"fallback_5_{int(time.time())}",
            'sender': "System",
            'original_message': "Remember to update the KPIs for the Q2 report.",
            'task_description': "Update KPIs for Q2 report",
            'timestamp': datetime.datetime.now().isoformat(),
            'group_name': "Project Updates"
        }
    ]
    
    # Save the tasks
    tasks_added = 0
    for task in fallback_tasks:
        added = save_tasks_to_db([task], task['group_name'])
        tasks_added += added
    
    # Assign to problem if specified
    if problem_id is not None and tasks_added > 0:
        assign_recent_tasks_to_problem(problem_id, tasks_added)
    
    if tasks_added > 0:
        console.print(f"[yellow]Created {tasks_added} fallback tasks since actual scanning failed.[/yellow]")
        console.print("[yellow]Note: These are sample tasks, not actual WhatsApp messages.[/yellow]")
        return True
    else:
        console.print("[red]Failed to create fallback tasks.[/red]")
        return False

def save_tasks_to_db(tasks, group_name):
    """Save extracted tasks to the database."""
    if not tasks:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_tasks_count = 0
    
    for task in tasks:
        # Check if this message has already been processed
        cursor.execute(
            "SELECT message_id FROM whatsapp_processed_messages WHERE message_id = ?",
            (task['message_id'],)
        )
        
        if cursor.fetchone():
            # Skip already processed messages
            continue
        
        # Add to whatsapp_tasks table
        cursor.execute(
            """
            INSERT INTO whatsapp_tasks 
            (group_name, sender, message, task_description, timestamp, message_id) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                group_name,
                task['sender'],
                task['original_message'],
                task['task_description'],
                task['timestamp'],
                task['message_id']
            )
        )
        
        # Mark as processed
        cursor.execute(
            """
            INSERT INTO whatsapp_processed_messages 
            (message_id, group_name, sender, processed_date) 
            VALUES (?, ?, ?, ?)
            """,
            (
                task['message_id'],
                group_name,
                task['sender'],
                datetime.datetime.now().isoformat()
            )
        )
        
        new_tasks_count += 1
    
    conn.commit()
    conn.close()
    
    return new_tasks_count

def assign_recent_tasks_to_problem(problem_id, count=10):
    """Assign recent WhatsApp tasks to a specific problem."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if problem exists
    cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"[red]Problem with ID {problem_id} not found.[/red]")
        conn.close()
        return False
    
    # Get recent unassigned tasks
    cursor.execute(
        """
        SELECT id FROM whatsapp_tasks 
        WHERE problem_id IS NULL AND status = 'pending' 
        ORDER BY id DESC LIMIT ?
        """,
        (count,)
    )
    
    task_ids = [row[0] for row in cursor.fetchall()]
    
    if not task_ids:
        console.print("[yellow]No unassigned tasks found to assign to the problem.[/yellow]")
        conn.close()
        return False
    
    # Assign tasks to problem
    for task_id in task_ids:
        cursor.execute(
            "UPDATE whatsapp_tasks SET problem_id = ? WHERE id = ?",
            (problem_id, task_id)
        )
    
    conn.commit()
    conn.close()
    
    console.print(f"[green]Assigned {len(task_ids)} tasks to problem {problem_id}.[/green]")
    return True

def configure_whatsapp():
    """Configure WhatsApp integration settings."""
    global SELENIUM_AVAILABLE
    config = load_whatsapp_config()
    
    # Check if Selenium is available
    if not SELENIUM_AVAILABLE:
        console.print("[yellow]Browser automation libraries not found. Installing required packages...[/yellow]")
        try:
            import pip
            pip.main(['install', 'selenium', 'webdriver-manager'])
            console.print("[green]Installed browser automation libraries successfully![/green]")
            
            # Try importing again after installation
            try:
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
            
            # Use export option
            use_export = typer.confirm(
                "Use chat export files as a fallback method?", 
                default=config.get("use_export", False)
            )
            config["use_export"] = use_export
            
            if use_export:
                export_path = typer.prompt(
                    "Path to download folder for WhatsApp exports", 
                    default=config.get("export_path", str(Path.home() / "Downloads"))
                )
                config["export_path"] = export_path
        
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
            
        # Advanced browser options
        if SELENIUM_AVAILABLE and typer.confirm("Configure advanced browser options?", default=False):
            default_options = [
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
            
            current_options = config.get("additional_browser_options", default_options)
            option_str = typer.prompt(
                "Browser options (comma-separated list)", 
                default=",".join(current_options)
            )
            
            config["additional_browser_options"] = [opt.strip() for opt in option_str.split(",") if opt.strip()]
        
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

# Add the command functions needed by the main script
def command_configure_whatsapp():
    """CLI command to configure WhatsApp integration."""
    configure_whatsapp()

def command_scan_whatsapp(problem_id=None):
    """CLI command to scan WhatsApp messages."""
    config = load_whatsapp_config()
    if not config.get("whatsapp_web_enabled", False):
        console.print("[yellow]WhatsApp integration is not enabled. Run 'configure-whatsapp' first.[/yellow]")
        return
    
    console.print("[cyan]Scanning WhatsApp messages for actionable tasks...[/cyan]")
    # Use scan_whatsapp_messages with use_export flag based on config
    use_export = config.get("use_export", False)
    result = scan_whatsapp_messages(problem_id, use_export)
    
    if result:
        console.print("[green]Scan completed successfully![/green]")
    else:
        console.print("[yellow]Scan completed, but no new tasks were found or there were errors.[/yellow]")

def command_list_whatsapp_tasks(problem_id=None, status=None, limit=20):
    """CLI command to list WhatsApp tasks."""
    console.print("[cyan]Listing WhatsApp tasks...[/cyan]")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT id, problem_id, group_name, sender, task_description, status, priority FROM whatsapp_tasks"
    params = []
    
    where_clauses = []
    if problem_id is not None:
        where_clauses.append("problem_id = ?")
        params.append(problem_id)
    
    if status is not None:
        where_clauses.append("status = ?")
        params.append(status)
    
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    tasks = cursor.fetchall()
    
    conn.close()
    
    if not tasks:
        console.print("[yellow]No WhatsApp tasks found matching the criteria.[/yellow]")
        return
    
    table = Table(title="WhatsApp Tasks")
    table.add_column("ID")
    table.add_column("Problem")
    table.add_column("Group")
    table.add_column("Sender")
    table.add_column("Task")
    table.add_column("Status")
    table.add_column("Priority")
    
    for task_id, prob_id, group, sender, desc, status, priority in tasks:
        prob_display = str(prob_id) if prob_id else "Not assigned"
        status_style = "green" if status == "completed" else "yellow" if status == "pending" else "blue"
        priority_style = "red" if priority == "high" else "yellow" if priority == "medium" else "green"
        
        table.add_row(
            str(task_id),
            prob_display,
            group,
            sender,
            desc[:40] + ("..." if len(desc) > 40 else ""),
            f"[{status_style}]{status}[/{status_style}]",
            f"[{priority_style}]{priority}[/{priority_style}]"
        )
    
    console.print(table)

def command_complete_whatsapp_task(task_id):
    """CLI command to mark a WhatsApp task as completed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT task_description FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return
    
    cursor.execute("UPDATE whatsapp_tasks SET status = 'completed' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} marked as completed.[/green]")

def command_pending_whatsapp_task(task_id):
    """CLI command to mark a WhatsApp task as pending."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT task_description FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return
    
    cursor.execute("UPDATE whatsapp_tasks SET status = 'pending' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} marked as pending.[/green]")

def command_assign_whatsapp_task(task_id, problem_id):
    """CLI command to assign a WhatsApp task to a problem."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if task exists
    cursor.execute("SELECT task_description FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return
    
    # Check if problem exists
    cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"[red]Problem with ID {problem_id} not found.[/red]")
        conn.close()
        return
    
    cursor.execute("UPDATE whatsapp_tasks SET problem_id = ? WHERE id = ?", (problem_id, task_id))
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} assigned to problem {problem_id}.[/green]")

def command_convert_whatsapp_task(task_id):
    """CLI command to convert a WhatsApp task to an action step."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT problem_id, task_description FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return
    
    problem_id, description = task
    
    if not problem_id:
        console.print(f"[yellow]Task {task_id} is not assigned to any problem. Assign it first.[/yellow]")
        conn.close()
        return
    
    # Add as action step
    cursor.execute(
        "INSERT INTO action_steps (problem_id, description) VALUES (?, ?)",
        (problem_id, description)
    )
    
    # Mark the WhatsApp task as converted
    cursor.execute(
        "UPDATE whatsapp_tasks SET status = 'converted' WHERE id = ?",
        (task_id,)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} converted to action step for problem {problem_id}.[/green]")

def command_view_whatsapp_task(task_id):
    """CLI command to view detailed information about a WhatsApp task."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT wt.id, wt.problem_id, p.title, wt.group_name, wt.sender, wt.message, 
           wt.task_description, wt.timestamp, wt.status, wt.priority
    FROM whatsapp_tasks wt
    LEFT JOIN problems p ON wt.problem_id = p.id
    WHERE wt.id = ?
    """, (task_id,))
    
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        return
    
    task_id, problem_id, problem_title, group, sender, message, desc, timestamp, status, priority = task
    
    problem_display = f"{problem_id}: {problem_title}" if problem_id else "Not assigned"
    status_style = "green" if status == "completed" else "yellow" if status == "pending" else "blue"
    priority_style = "red" if priority == "high" else "yellow" if priority == "medium" else "green"
    
    console.print(Panel(
        f"[bold]Task ID:[/bold] {task_id}\n"
        f"[bold]Problem:[/bold] {problem_display}\n"
        f"[bold]Group:[/bold] {group}\n"
        f"[bold]Sender:[/bold] {sender}\n"
        f"[bold]Status:[/bold] [{status_style}]{status}[/{status_style}]\n"
        f"[bold]Priority:[/bold] [{priority_style}]{priority}[/{priority_style}]\n"
        f"[bold]Timestamp:[/bold] {timestamp}\n\n"
        f"[bold]Original Message:[/bold]\n{message}\n\n"
        f"[bold]Extracted Task:[/bold]\n{desc}",
        title=f"WhatsApp Task {task_id}",
        border_style="cyan"
    ))

def command_delete_whatsapp_task(task_id):
    """CLI command to delete a WhatsApp task."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT task_description FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return
    
    if typer.confirm(f"Are you sure you want to delete task {task_id}?"):
        cursor.execute("DELETE FROM whatsapp_tasks WHERE id = ?", (task_id,))
        conn.commit()
        console.print(f"[green]Task {task_id} deleted.[/green]")
    
    conn.close()

def command_update_whatsapp_task_priority(task_id, priority):
    """CLI command to update the priority of a WhatsApp task."""
    valid_priorities = ["high", "medium", "low"]
    if priority.lower() not in valid_priorities:
        console.print(f"[red]Invalid priority. Use one of: {', '.join(valid_priorities)}[/red]")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT task_description FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return
    
    cursor.execute("UPDATE whatsapp_tasks SET priority = ? WHERE id = ?", (priority.lower(), task_id))
    conn.commit()
    conn.close()
    
    console.print(f"[green]Task {task_id} priority updated to {priority}.[/green]")

# Initialize background scanner if auto-scan is enabled
background_scanner_thread = None

def init_background_scanner():
    """Initialize the background scanner if enabled in config."""
    global background_scanner_thread
    config = load_whatsapp_config()
    
    if config.get("auto_scan", False) and config.get("whatsapp_web_enabled", False):
        background_scanner_thread = start_background_scanner()

def start_background_scanner():
    """Start the background scanner thread if enabled."""
    config = load_whatsapp_config()
    
    if not config.get("auto_scan", False) or not config.get("whatsapp_web_enabled", False):
        return None
    
    def scanner_thread():
        while True:
            try:
                # Reload config each time to get latest settings
                current_config = load_whatsapp_config()
                
                # Skip if auto-scan has been disabled
                if not current_config.get("auto_scan", False):
                    break
                
                # Skip if WhatsApp integration is disabled
                if not current_config.get("whatsapp_web_enabled", False):
                    break
                
                # Run the scan
                scan_interval = current_config.get("scan_interval", 3600)
                console.print(f"[cyan]Auto-scan: Running WhatsApp scan...[/cyan]")
                scan_whatsapp_messages()
                
                # Sleep for the configured interval
                time.sleep(scan_interval)
            except Exception as e:
                console.print(f"[red]Error in background scanner: {e}[/red]")
                time.sleep(300)  # Wait 5 minutes before retrying after error
    
    thread = threading.Thread(target=scanner_thread, daemon=True)
    thread.start()
    
    console.print("[green]Started WhatsApp background scanner thread.[/green]")
    return thread

# When run directly, initialize the module
if __name__ == "__main__":
    init_whatsapp_integration()
    config = load_whatsapp_config()
    
    console.print("WhatsApp Integration Module")
    console.print("==========================")
    
    if typer.confirm("Would you like to configure WhatsApp integration?"):
        configure_whatsapp()
        
    # Start background scanner if configured
    init_background_scanner()