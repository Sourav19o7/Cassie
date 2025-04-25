"""
WhatsApp Integration Module for Empathic Problem Solver CLI
Enables scanning WhatsApp messages and extracting actionable tasks using Selenium automation.
"""

import os
import re
import json
import sqlite3
import datetime
from pathlib import Path
import typer
from typing import List, Dict, Optional, Union, Tuple
from rich.console import Console  # Make sure this import is at the top
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests
import keyring
import time
import threading
import base64
import io
from PIL import Image
import qrcode

# Initialize console first before using it anywhere
console = Console()

# Initialize app constants
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
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
    
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

def get_whatsapp_driver(config=None):
    """Initialize and return a Selenium WebDriver for WhatsApp Web."""
    if not SELENIUM_AVAILABLE:
        raise ImportError("Selenium is not available. Please install selenium and webdriver-manager packages.")
    
    if config is None:
        config = load_whatsapp_config()
    
    browser_type = config.get("browser_type", "chrome").lower()
    headless = config.get("headless", False)
    
    # Create driver based on browser type
    if browser_type == "chrome":
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--mute-audio")
        
        # Set user data directory for session persistence
        user_data_dir = WHATSAPP_SESSION_PATH / "chrome"
        options.add_argument(f"--user-data-dir={user_data_dir}")
        
        # Install Chrome driver using webdriver_manager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    
    elif browser_type == "firefox":
        options = webdriver.FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        
        # Set Firefox profile for session persistence
        profile_path = WHATSAPP_SESSION_PATH / "firefox"
        if not profile_path.exists():
            profile_path.mkdir(parents=True, exist_ok=True)
        
        # Install Firefox driver using webdriver_manager
        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)
    
    elif browser_type == "edge":
        options = webdriver.EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--disable-notifications")
        
        # Set user data directory for session persistence
        user_data_dir = WHATSAPP_SESSION_PATH / "edge"
        options.add_argument(f"--user-data-dir={user_data_dir}")
        
        # Install Edge driver using webdriver_manager
        service = Service(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
    
    else:
        raise ValueError(f"Unsupported browser type: {browser_type}")
    
    # Set implicit wait time
    driver.implicitly_wait(10)
    
    return driver

def is_authenticated(driver):
    """Check if the browser is authenticated with WhatsApp Web."""
    try:
        # Check for QR code (not authenticated)
        qr_code = driver.find_elements(By.XPATH, '//div[@data-ref]')
        if qr_code:
            return False
        
        # Check for chat list (authenticated)
        chat_list = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-testid="chat-list"]'))
        )
        return True
    except:
        # If we're not sure, assume not authenticated
        return False

def get_qr_code(driver):
    """Extract the QR code from WhatsApp Web page."""
    try:
        # Find the canvas element containing the QR code
        qr_canvas = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//canvas[contains(@aria-label, "Scan me!")]'))
        )
        
        # Get the canvas data URL
        data_url = driver.execute_script("return arguments[0].toDataURL('image/png');", qr_canvas)
        
        # Convert data URL to image
        header, encoded = data_url.split(",", 1)
        binary_data = base64.b64decode(encoded)
        
        # Create a PIL Image from binary data
        image = Image.open(io.BytesIO(binary_data))
        
        # Save to file for debugging
        qr_path = WHATSAPP_SESSION_PATH / "whatsapp_qr.png"
        image.save(qr_path)
        
        return str(qr_path)
    except Exception as e:
        console.print(f"[yellow]Could not extract QR code: {e}[/yellow]")
        return None

def display_qr_terminal(qr_path):
    """Display a text-based QR code in the terminal."""
    try:
        img = Image.open(qr_path)
        # Convert to black and white
        img = img.convert("1")
        width, height = img.size
        
        # Sample pixels to create ASCII art
        ascii_qr = []
        for y in range(0, height, 2):
            line = ""
            for x in range(0, width, 1):
                if x < width and y < height:
                    pixel = img.getpixel((x, y))
                    line += "██" if pixel == 0 else "  "
            ascii_qr.append(line)
        
        console.print(Panel("\n".join(ascii_qr), title="Scan this QR code with WhatsApp on your phone", border_style="green"))
        console.print("[yellow]QR code image also saved to: " + qr_path + "[/yellow]")
    except Exception as e:
        console.print(f"[red]Could not display QR code: {e}[/red]")
        console.print(f"[yellow]Please open the QR code image at: {qr_path}[/yellow]")

def wait_for_authentication(driver, max_wait=60):
    """Wait for the user to authenticate with WhatsApp Web."""
    console.print("[cyan]Waiting for WhatsApp authentication...[/cyan]")
    
    start_time = time.time()
    authenticated = False
    
    qr_displayed = False
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Waiting for authentication...[/cyan]"),
        transient=True
    ) as progress:
        task = progress.add_task("Waiting...", total=max_wait)
        
        while time.time() - start_time < max_wait:
            # Check if already authenticated
            if is_authenticated(driver):
                authenticated = True
                break
            
            # If not authenticated and QR not displayed yet, try to display it
            if not qr_displayed:
                qr_path = get_qr_code(driver)
                if qr_path:
                    progress.stop()
                    display_qr_terminal(qr_path)
                    qr_displayed = True
                    progress.start()
            
            # Update progress bar
            elapsed = time.time() - start_time
            progress.update(task, completed=elapsed)
            
            time.sleep(2)
    
    if authenticated:
        console.print("[green]Successfully authenticated with WhatsApp Web![/green]")
        return True
    else:
        console.print("[red]Authentication timed out. Please try again.[/red]")
        return False

def navigate_to_chat(driver, chat_name):
    """Navigate to a specific chat by name."""
    try:
        # Look for the chat in the list
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@title="Search input textbox"]'))
        )
        search_box.clear()
        search_box.send_keys(chat_name)
        time.sleep(2)  # Wait for search results
        
        # Click on the chat that matches the exact name
        chat_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, f'//span[@title="{chat_name}"]'))
        )
        chat_element.click()
        time.sleep(2)  # Wait for chat to load
        
        # Verify we're in the right chat
        chat_header = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, f'//div[@data-testid="conversation-header"]//span[contains(@title, "{chat_name}")]'))
        )
        
        return True
    except Exception as e:
        console.print(f"[yellow]Could not navigate to chat '{chat_name}': {e}[/yellow]")
        return False

def get_chat_messages(driver, max_messages=50):
    """Get recent messages from the current chat."""
    try:
        # Find the message container
        message_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-testid="conversation-panel-messages"]'))
        )
        
        # Scroll up to load more messages
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollTop - 1000", message_container)
        time.sleep(1)
        
        # Get all message elements
        message_elements = message_container.find_elements(By.XPATH, './/div[contains(@class, "message-in") or contains(@class, "message-out")]')
        
        # Limit to max_messages
        message_elements = message_elements[-max_messages:] if len(message_elements) > max_messages else message_elements
        
        messages = []
        for msg_elem in message_elements:
            try:
                # Get message ID for deduplication
                data_id = msg_elem.get_attribute('data-id')
                
                # Determine if message is incoming or outgoing
                is_incoming = 'message-in' in msg_elem.get_attribute('class')
                
                # Get sender (for group chats)
                sender_elem = msg_elem.find_elements(By.XPATH, './/span[@data-testid="author"]')
                sender = sender_elem[0].text if sender_elem else "You" if not is_incoming else "Unknown"
                
                # Get message text
                msg_text_elem = msg_elem.find_elements(By.XPATH, './/div[@data-testid="msg-text"]')
                if not msg_text_elem:
                    # This might be a media message, look for caption
                    msg_text_elem = msg_elem.find_elements(By.XPATH, './/div[contains(@class, "copyable-text")]')
                
                if msg_text_elem:
                    msg_text = msg_text_elem[0].text
                else:
                    # Skip non-text messages
                    continue
                
                # Get timestamp
                timestamp_elem = msg_elem.find_elements(By.XPATH, './/div[@data-testid="msg-meta"]')
                timestamp = timestamp_elem[0].text if timestamp_elem else "Unknown"
                
                # Only process incoming messages
                if is_incoming:
                    messages.append({
                        'message_id': data_id,
                        'sender': sender,
                        'text': msg_text,
                        'timestamp': timestamp,
                        'is_incoming': is_incoming
                    })
            except StaleElementReferenceException:
                # Element might have become stale, skip it
                continue
            except Exception as e:
                # Skip problematic messages
                continue
        
        return messages
    except Exception as e:
        console.print(f"[yellow]Error getting messages: {e}[/yellow]")
        return []

def extract_tasks_from_messages(messages, config):
    """Extract potential tasks from messages using Claude AI."""
    if not messages:
        return []
    
    # Filter messages based on config
    min_words = config.get("filters", {}).get("min_words", 5)
    filtered_messages = [m for m in messages if len(m['text'].split()) >= min_words]
    
    # If no suitable messages, return empty list
    if not filtered_messages:
        return []
    
    # Check if API key is available
    api_key = get_api_key()
    if not api_key:
        # Fall back to rule-based extraction
        return rule_based_task_extraction(filtered_messages)
    
    # Prepare message batch for Claude
    message_batch = "\n\n".join([
        f"Sender: {msg['sender']}\nMessage: {msg['text']}\nTimestamp: {msg['timestamp']}\nID: {msg['message_id']}"
        for msg in filtered_messages[:10]  # Limit to 10 messages at a time for API
    ])
    
    prompt = f"""
    Analyze these WhatsApp messages and identify any actionable tasks, todos, or requests:

    {message_batch}

    For each message that contains a task or request, extract:
    1. The message ID
    2. A clear, actionable task description
    
    Format your response as a JSON array of objects, each with "message_id" and "task" fields.
    Only include messages that actually contain tasks or action items - not general statements, questions without requests, or casual conversation.
    
    Example:
    [
      {{"message_id": "12345", "task": "Schedule team meeting for next Tuesday"}},
      {{"message_id": "67890", "task": "Send updated project proposal to client"}}
    ]
    
    If no tasks are found, return an empty array: []
    """
    
    response = call_claude_api(prompt, max_tokens=800)
    
    if not response:
        return rule_based_task_extraction(filtered_messages)
    
    try:
        # Extract JSON from the response
        json_str = response.strip()
        # Find the first '[' and last ']' to extract just the JSON array
        start = json_str.find('[')
        end = json_str.rfind(']') + 1
        if start != -1 and end != 0:
            json_str = json_str[start:end]
            tasks = json.loads(json_str)
            
            # Map tasks back to full message data
            message_map = {msg['message_id']: msg for msg in filtered_messages}
            task_results = []
            
            for task in tasks:
                message_id = task.get('message_id')
                if message_id in message_map:
                    task_results.append({
                        'message_id': message_id,
                        'sender': message_map[message_id]['sender'],
                        'original_message': message_map[message_id]['text'],
                        'task_description': task.get('task'),
                        'timestamp': message_map[message_id]['timestamp']
                    })
            
            return task_results
    except Exception as e:
        console.print(f"[yellow]Error parsing Claude task extraction response: {e}. Using rule-based extraction.[/yellow]")
    
    # Fall back to rule-based extraction if API call fails
    return rule_based_task_extraction(filtered_messages)

def rule_based_task_extraction(messages):
    """Extract potential tasks from messages using rule-based methods."""
    task_indicators = [
        r'\bplease\b',
        r'\bcan you\b',
        r'\bcould you\b',
        r'\bshould\b',
        r'\bneed to\b',
        r'\bhave to\b',
        r'\bmust\b',
        r'\brequire\b',
        r'\bremember to\b',
        r'\bdon\'t forget\b',
        r'\bdo\b',
        r'\btodo\b',
        r'\btask\b',
        r'\bassignment\b',
        r'\bdeadline\b',
        r'\bby tomorrow\b',
        r'\bby next\b',
        r'\bsend\b',
        r'\bcheck\b',
        r'\breview\b',
        r'\bcreate\b',
        r'\bupdate\b',
        r'\bfinish\b',
        r'\bcomplete\b'
    ]
    
    pattern = re.compile("|".join(task_indicators), re.IGNORECASE)
    tasks = []
    
    for msg in messages:
        if pattern.search(msg['text']):
            # Extract relevant sentence as the task
            sentences = re.split(r'[.!?]', msg['text'])
            task_sentences = [s.strip() for s in sentences if pattern.search(s)]
            
            if task_sentences:
                task_description = task_sentences[0]
            else:
                # Use first sentence if no specific task sentence found
                task_description = sentences[0].strip() if sentences else msg['text']
            
            tasks.append({
                'message_id': msg['message_id'],
                'sender': msg['sender'],
                'original_message': msg['text'],
                'task_description': task_description,
                'timestamp': msg['timestamp']
            })
    
    return tasks

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

def scan_whatsapp_messages(problem_id=None, use_export=False):
    """Scan WhatsApp messages for tasks."""
    config = load_whatsapp_config()
    
    if not config.get("whatsapp_web_enabled", False):
        console.print("[yellow]WhatsApp integration is not enabled. Run 'configure-whatsapp' first.[/yellow]")
        return False
    
    # Check if using export method
    if use_export or config.get("use_export", False):
        return scan_from_exports(problem_id)
    
    # Check if Selenium is available
    if not SELENIUM_AVAILABLE:
        console.print("[red]Browser automation libraries not available. Cannot scan WhatsApp.[/red]")
        console.print("[yellow]Try using export method with --use-export flag.[/yellow]")
        return False
    
    try:
        # Get the configured groups
        monitored_groups = config.get("monitored_groups", [])
        if not monitored_groups:
            console.print("[yellow]No monitored groups configured. Please run 'configure-whatsapp' to add groups.[/yellow]")
            return False
        
        # Initialize the driver
        driver = get_whatsapp_driver(config)
        console.print("[cyan]Opening WhatsApp Web...[/cyan]")
        
        # Open WhatsApp Web
        driver.get("https://web.whatsapp.com/")
        
        # Wait for authentication
        if not is_authenticated(driver):
            auth_success = wait_for_authentication(driver, max_wait=120)
            if not auth_success:
                driver.quit()
                return False
        
        # Scan each monitored group
        total_new_tasks = 0
        max_messages = config.get("max_messages_per_chat", 50)
        
        for group in monitored_groups:
            console.print(f"[cyan]Scanning group: {group}[/cyan]")
            
            # Navigate to the group chat
            if navigate_to_chat(driver, group):
                # Get messages
                messages = get_chat_messages(driver, max_messages)
                console.print(f"Found {len(messages)} messages in {group}")
                
                # Extract tasks
                tasks = extract_tasks_from_messages(messages, config)
                console.print(f"Extracted {len(tasks)} potential tasks")
                
                # Save tasks to database
                new_tasks = save_tasks_to_db(tasks, group)
                console.print(f"[green]Added {new_tasks} new tasks to the database[/green]")
                
                total_new_tasks += new_tasks
            else:
                console.print(f"[yellow]Could not access group: {group}[/yellow]")
        
        # Update last scan time
        config["last_scan_time"] = datetime.datetime.now().isoformat()
        save_whatsapp_config(config)
        
        # Assign tasks to problem if specified
        if problem_id and total_new_tasks > 0:
            assign_recent_tasks_to_problem(problem_id, total_new_tasks)
        
        driver.quit()
        
        return total_new_tasks > 0
    
    except Exception as e:
        console.print(f"[red]Error scanning WhatsApp messages: {e}[/red]")
        return False

def scan_from_exports(problem_id=None):
    """Scan WhatsApp message exports for tasks."""
    config = load_whatsapp_config()
    export_path = Path(config.get("export_path", str(Path.home() / "Downloads")))
    
    if not export_path.exists():
        console.print(f"[red]Export path does not exist: {export_path}[/red]")
        return False
    
    # Find WhatsApp chat exports (typically named "WhatsApp Chat with X.txt")
    export_files = list(export_path.glob("WhatsApp Chat with *.txt"))
    
    if not export_files:
        console.print("[yellow]No WhatsApp chat export files found. Please export chats from WhatsApp.[/yellow]")
        return False
    
    console.print(f"[cyan]Found {len(export_files)} WhatsApp chat export files[/cyan]")
    
    total_new_tasks = 0
    
    for export_file in export_files:
        try:
            group_name = export_file.stem.replace("WhatsApp Chat with ", "")
            console.print(f"[cyan]Processing export: {group_name}[/cyan]")
            
            # Check if this group should be monitored
            monitored_groups = config.get("monitored_groups", [])
            if monitored_groups and group_name not in monitored_groups:
                console.print(f"[yellow]Skipping {group_name} as it is not in monitored groups[/yellow]")
                continue
            
            # Read and parse the file
            with open(export_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse chat export
            messages = parse_whatsapp_export(content)
            console.print(f"Parsed {len(messages)} messages from export")
            
            # Extract tasks
            tasks = extract_tasks_from_messages(messages, config)
            console.print(f"Extracted {len(tasks)} potential tasks")
            
            # Save tasks to database
            new_tasks = save_tasks_to_db(tasks, group_name)
            console.print(f"[green]Added {new_tasks} new tasks to the database[/green]")
            
            total_new_tasks += new_tasks
            
        except Exception as e:
            console.print(f"[yellow]Error processing {export_file}: {e}[/yellow]")
    
    # Update last scan time
    config["last_scan_time"] = datetime.datetime.now().isoformat()
    save_whatsapp_config(config)
    
    # Assign tasks to problem if specified
    if problem_id and total_new_tasks > 0:
        assign_recent_tasks_to_problem(problem_id, total_new_tasks)
    
    return total_new_tasks > 0

def parse_whatsapp_export(content):
    """Parse WhatsApp chat export content into message objects."""
    # Regex pattern for WhatsApp export format
    pattern = r'(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?(?: [AP]M)?) - ([^:]+): (.+)'
    
    messages = []
    message_id = 1000  # Start with a high number to avoid conflicts
    
    for line in content.split('\n'):
        match = re.match(pattern, line)
        if match:
            timestamp, sender, text = match.groups()
            
            # Generate a unique message ID
            message_id += 1
            
            messages.append({
                'message_id': f"export_{message_id}",
                'sender': sender.strip(),
                'text': text.strip(),
                'timestamp': timestamp,
                'is_incoming': True  # Assume all exported messages are incoming
            })
    
    return messages

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

def convert_task_to_action_step(task_id):
    """Convert a WhatsApp task to a problem action step."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT problem_id, task_description FROM whatsapp_tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        console.print(f"[red]Task with ID {task_id} not found.[/red]")
        conn.close()
        return False
    
    problem_id, description = task
    
    if not problem_id:
        console.print(f"[yellow]Task {task_id} is not assigned to any problem. Please assign it first.[/yellow]")
        conn.close()
        return False
    
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
    return True

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
        
        # Initialize the driver
        driver = get_whatsapp_driver(config)
        
        # Open WhatsApp Web
        driver.get("https://web.whatsapp.com/")
        
        # Check authentication status
        auth_status = is_authenticated(driver)
        
        if auth_status:
            console.print("[green]Already authenticated with WhatsApp Web![/green]")
        else:
            console.print("[yellow]Not authenticated. Please scan the QR code with your phone.[/yellow]")
            auth_success = wait_for_authentication(driver, max_wait=120)
            if auth_success:
                console.print("[green]Authentication successful![/green]")
            else:
                console.print("[red]Authentication failed. Please try again later.[/red]")
                driver.quit()
                return False
        
        # Test accessing a chat (if we have monitored groups)
        monitored_groups = config.get("monitored_groups", [])
        if monitored_groups:
            test_group = monitored_groups[0]
            console.print(f"[cyan]Testing access to group: {test_group}[/cyan]")
            
            if navigate_to_chat(driver, test_group):
                console.print(f"[green]Successfully accessed group: {test_group}[/green]")
                
                # Test getting messages
                messages = get_chat_messages(driver, 5)
                console.print(f"[green]Successfully retrieved {len(messages)} messages[/green]")
            else:
                console.print(f"[red]Could not access group: {test_group}[/red]")
                driver.quit()
                return False
        
        driver.quit()
        return True
        
    except Exception as e:
        console.print(f"[red]Error testing WhatsApp Web connection: {e}[/red]")
        return False

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
    result = scan_whatsapp_messages(problem_id)
    
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
# This runs when the module is imported
background_scanner_thread = None

def init_background_scanner():
    """Initialize the background scanner if enabled in config."""
    global background_scanner_thread
    config = load_whatsapp_config()
    
    if config.get("auto_scan", False) and config.get("whatsapp_web_enabled", False):
        background_scanner_thread = start_background_scanner()

# When run directly, initialize the module
if __name__ == "__main__":
    # Initialize and test the module
    init_whatsapp_integration()
    config = load_whatsapp_config()
    
    console.print("WhatsApp Integration Module")
    console.print("==========================")
    
    if typer.confirm("Would you like to configure WhatsApp integration?"):
        configure_whatsapp()
        
    # Start background scanner if configured
    init_background_scanner()