"""
Simplified WhatsApp Web Integration for Empathic Problem Solver CLI.
This is a minimal version that focuses just on connecting to WhatsApp Web reliably.
"""

import os
import time
import sqlite3
import json
import datetime
from pathlib import Path
from rich.console import Console
from typing import List, Dict, Optional

# Initialize console
console = Console()

# App directories
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
WHATSAPP_CONFIG_PATH = APP_DIR / "whatsapp_config.json"
WHATSAPP_SESSION_PATH = APP_DIR / "whatsapp_session"

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    # For saving screenshots to debug
    import base64
    
    # Check if Chrome is available
    CHROME_AVAILABLE = True
except ImportError:
    CHROME_AVAILABLE = False
    console.print("[red]Selenium or Chrome not available. WhatsApp integration will be limited.[/red]")

def init_directories():
    """Ensure all required directories exist."""
    APP_DIR.mkdir(exist_ok=True)
    WHATSAPP_SESSION_PATH.mkdir(exist_ok=True)

def load_config():
    """Load WhatsApp configuration or create default."""
    if not WHATSAPP_CONFIG_PATH.exists():
        config = {
            "enabled": False,
            "groups": [],
            "debug_mode": True,
            "screenshot_on_error": True
        }
        with open(WHATSAPP_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        return config
    
    with open(WHATSAPP_CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(config):
    """Save WhatsApp configuration."""
    with open(WHATSAPP_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def take_screenshot(driver, name="whatsapp_debug"):
    """Take a screenshot for debugging purposes."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = APP_DIR / filename
        driver.save_screenshot(str(filepath))
        console.print(f"[yellow]Screenshot saved to {filepath}[/yellow]")
        return True
    except Exception as e:
        console.print(f"[red]Failed to take screenshot: {e}[/red]")
        return False

def get_driver():
    """Create and configure a Chrome WebDriver instance."""
    if not CHROME_AVAILABLE:
        console.print("[red]Chrome WebDriver not available.[/red]")
        return None
    
    options = webdriver.ChromeOptions()
    
    # Set user data directory to store session
    user_data_dir = str(WHATSAPP_SESSION_PATH / "chrome_profile")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    # Add options to avoid detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Add options for stability
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-web-security")
    
    # Set window size
    options.add_argument("--window-size=1200,800")
    
    try:
        # Try to use standalone Chrome first (most compatible)
        driver = webdriver.Chrome(options=options)
        console.print("[green]Chrome WebDriver initialized successfully.[/green]")
        return driver
    except Exception as e:
        console.print(f"[yellow]Error initializing Chrome: {e}. Trying alternate method...[/yellow]")
        
        try:
            # Try using webdriver manager if available
            from webdriver_manager.chrome import ChromeDriverManager
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            console.print("[green]Chrome WebDriver initialized with ChromeDriverManager.[/green]")
            return driver
        except Exception as e2:
            console.print(f"[red]Failed to initialize Chrome WebDriver: {e2}[/red]")
            return None

def connect_to_whatsapp():
    """Connect to WhatsApp Web and validate the connection."""
    config = load_config()
    driver = get_driver()
    
    if not driver:
        console.print("[red]Failed to initialize browser.[/red]")
        return False
    
    try:
        # Navigate to WhatsApp Web
        console.print("[cyan]Opening WhatsApp Web...[/cyan]")
        driver.get("https://web.whatsapp.com/")
        
        # Take initial screenshot for debugging
        if config.get("debug_mode", True):
            take_screenshot(driver, "whatsapp_initial")
        
        # Wait for either QR code or main chat interface
        console.print("[cyan]Waiting for QR code or login...[/cyan]")
        
        # Wait for QR code first
        qr_found = False
        try:
            qr_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "landing-wrapper")]'))
            )
            qr_found = True
            console.print("[yellow]Please scan the QR code with your phone to log in.[/yellow]")
            
            # Take screenshot of QR code
            if config.get("debug_mode", True):
                take_screenshot(driver, "whatsapp_qr_code")
            
        except TimeoutException:
            console.print("[cyan]No QR code found. Checking if already logged in...[/cyan]")
        
        # Try different selectors for the main chat list
        chat_selectors = [
            # Class name selectors
            (By.CLASS_NAME, '_2AOIt'),  # From reference
            (By.CLASS_NAME, 'two'),
            (By.CLASS_NAME, 'app'),
            (By.CLASS_NAME, 'landing-wrapper'),
            
            # XPath selectors
            (By.XPATH, '//div[@id="app"]'),
            (By.XPATH, '//div[contains(@class, "app")]'),
            (By.XPATH, '//div[contains(@class, "two")]'),
            
            # More specific selectors
            (By.XPATH, '//div[contains(@class, "chat-list")]'),
            (By.XPATH, '//div[contains(@id, "pane-side")]')
        ]
        
        # Wait for any sign of the main interface
        logged_in = False
        for selector_type, selector in chat_selectors:
            try:
                # Use a longer timeout if QR was shown
                timeout = 120 if qr_found else 20
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((selector_type, selector))
                )
                logged_in = True
                console.print(f"[green]Found main interface element: {selector}[/green]")
                
                # Take screenshot of logged in state
                if config.get("debug_mode", True):
                    take_screenshot(driver, "whatsapp_logged_in")
                
                break
            except TimeoutException:
                continue
        
        if not logged_in:
            console.print("[red]Failed to detect login to WhatsApp Web.[/red]")
            
            # Take final state screenshot
            if config.get("screenshot_on_error", True):
                take_screenshot(driver, "whatsapp_error")
                
            driver.quit()
            return False
        
        # Try to interact with the page to confirm it's working
        try:
            console.print("[cyan]Testing page interaction...[/cyan]")
            # Look for common elements
            elements = driver.find_elements(By.XPATH, '//div[contains(@class, "chat")]')
            console.print(f"[green]Found {len(elements)} chat-related elements.[/green]")
            
            # Take success screenshot
            take_screenshot(driver, "whatsapp_success")
            
            # Success - update config
            config["last_successful_connection"] = datetime.datetime.now().isoformat()
            save_config(config)
            
            console.print("[green]Successfully connected to WhatsApp Web![/green]")
            driver.quit()
            return True
            
        except Exception as e:
            console.print(f"[red]Error interacting with page: {e}[/red]")
            if config.get("screenshot_on_error", True):
                take_screenshot(driver, "whatsapp_interaction_error")
            driver.quit()
            return False
    
    except Exception as e:
        console.print(f"[red]Error connecting to WhatsApp Web: {e}[/red]")
        if driver and config.get("screenshot_on_error", True):
            take_screenshot(driver, "whatsapp_exception")
        if driver:
            driver.quit()
        return False

def scan_messages(group_name=None):
    """Scan for messages in a specific group or all groups."""
    if not CHROME_AVAILABLE:
        console.print("[red]Chrome WebDriver not available. Cannot scan messages.[/red]")
        return False
    
    config = load_config()
    driver = get_driver()
    
    if not driver:
        console.print("[red]Failed to initialize browser.[/red]")
        return False
    
    try:
        # Navigate to WhatsApp Web
        console.print("[cyan]Opening WhatsApp Web...[/cyan]")
        driver.get("https://web.whatsapp.com/")
        
        # Wait for the page to load
        logged_in = False
        for selector in ['_2AOIt', 'app', 'two']:
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CLASS_NAME, selector))
                )
                logged_in = True
                break
            except TimeoutException:
                continue
        
        if not logged_in:
            console.print("[red]Failed to load WhatsApp Web or not logged in.[/red]")
            take_screenshot(driver, "whatsapp_not_logged_in")
            driver.quit()
            return False
        
        console.print("[green]WhatsApp Web loaded successfully.[/green]")
        
        # Allow extra time for all elements to load
        time.sleep(5)
        take_screenshot(driver, "whatsapp_loaded")
        
        # If group name is specified, try to open that chat
        if group_name:
            console.print(f"[cyan]Searching for group: {group_name}[/cyan]")
            
            # Try to find search box
            search_found = False
            search_selectors = [
                (By.XPATH, '//div[@contenteditable="true"]'),
                (By.XPATH, '//div[contains(@class, "copyable-text") and @contenteditable="true"]'),
                (By.XPATH, '//div[contains(@title, "Search")]'),
                (By.XPATH, '//div[contains(@class, "lexical-rich-text-input")]//div[@contenteditable="true"]')
            ]
            
            for selector_type, selector in search_selectors:
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                    search_found = True
                    console.print(f"[green]Found search box using selector: {selector}[/green]")
                    search_box.clear()
                    search_box.send_keys(group_name)
                    time.sleep(3)  # Wait for search results
                    take_screenshot(driver, "whatsapp_search_results")
                    break
                except (TimeoutException, NoSuchElementException) as e:
                    console.print(f"[yellow]Search selector {selector} failed: {e}[/yellow]")
                    continue
            
            if not search_found:
                console.print("[red]Could not find search box.[/red]")
                take_screenshot(driver, "whatsapp_no_search")
                driver.quit()
                return False
            
            # Try to find and click the group in search results
            group_found = False
            contact_selectors = [
                f'//span[@title="{group_name}"]',
                f'//span[text()="{group_name}"]',
                f'//span[contains(text(),"{group_name}")]'
            ]
            
            for selector in contact_selectors:
                try:
                    contact = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    contact.click()
                    group_found = True
                    console.print(f"[green]Found and clicked group: {group_name}[/green]")
                    time.sleep(2)  # Wait for chat to load
                    take_screenshot(driver, "whatsapp_group_opened")
                    break
                except (TimeoutException, NoSuchElementException) as e:
                    console.print(f"[yellow]Group selector {selector} failed: {e}[/yellow]")
                    continue
            
            if not group_found:
                console.print(f"[red]Could not find or click group: {group_name}[/red]")
                take_screenshot(driver, "whatsapp_group_not_found")
                driver.quit()
                return False
        
        # Try to extract messages
        console.print("[cyan]Trying to extract messages...[/cyan]")
        
        # Try different message selectors
        message_found = False
        message_selectors = [
            (By.CLASS_NAME, '_21Ahp'),  # From reference
            (By.XPATH, '//div[contains(@class, "message-in")]'),
            (By.XPATH, '//div[contains(@class, "message")]'),
            (By.XPATH, '//div[contains(@class, "FTBzM")]'),
            (By.XPATH, '//div[contains(@class, "copyable-text")]')
        ]
        
        for selector_type, selector in message_selectors:
            try:
                messages = driver.find_elements(selector_type, selector)
                if messages:
                    message_found = True
                    console.print(f"[green]Found {len(messages)} messages using selector: {selector}[/green]")
                    
                    # Print first few messages for debugging
                    for i, message in enumerate(messages[:5], 1):
                        try:
                            console.print(f"[cyan]Message {i}: {message.text[:100]}...[/cyan]")
                        except:
                            console.print(f"[yellow]Could not get text from message {i}[/yellow]")
                    
                    break
            except Exception as e:
                console.print(f"[yellow]Message selector {selector} failed: {e}[/yellow]")
                continue
        
        if not message_found:
            console.print("[red]Could not find any messages.[/red]")
            take_screenshot(driver, "whatsapp_no_messages")
        
        # Success - we've demonstrated we can connect and access elements
        take_screenshot(driver, "whatsapp_scan_complete")
        console.print("[green]WhatsApp Web scan completed.[/green]")
        driver.quit()
        return message_found
    
    except Exception as e:
        console.print(f"[red]Error scanning WhatsApp: {e}[/red]")
        if driver:
            take_screenshot(driver, "whatsapp_scan_error")
            driver.quit()
        return False

def configure_whatsapp():
    """Configure WhatsApp integration settings."""
    init_directories()
    config = load_config()
    
    # Check if Chrome is available
    if not CHROME_AVAILABLE:
        console.print("[red]Chrome WebDriver not available. WhatsApp integration requires Selenium and Chrome.[/red]")
        console.print("[yellow]Please install required packages with: pip install selenium webdriver-manager[/yellow]")
        return False
    
    console.print("[bold cyan]WhatsApp Web Integration Configuration[/bold cyan]")
    
    # Basic configuration
    config["enabled"] = True
    config["debug_mode"] = True
    config["screenshot_on_error"] = True
    
    # Configure groups to monitor
    groups = config.get("groups", [])
    console.print(f"Currently monitoring {len(groups)} groups:")
    for i, group in enumerate(groups, 1):
        console.print(f"{i}. {group}")
    
    # Ask to add a group
    if not groups or input("Add a group to monitor? (y/n): ").lower() == 'y':
        group_name = input("Enter the exact name of the WhatsApp group or contact: ")
        if group_name and group_name not in groups:
            groups.append(group_name)
            console.print(f"[green]Added group: {group_name}[/green]")
    
    config["groups"] = groups
    save_config(config)
    
    # Test connection
    console.print("[bold cyan]Testing WhatsApp Web connection...[/bold cyan]")
    if connect_to_whatsapp():
        console.print("[green]WhatsApp Web connection test successful![/green]")
        
        # Test scanning messages
        if groups and input("Test scanning messages from a group? (y/n): ").lower() == 'y':
            group_to_test = groups[0]
            console.print(f"[cyan]Testing message scanning with group: {group_to_test}[/cyan]")
            if scan_messages(group_to_test):
                console.print("[green]Message scanning test successful![/green]")
            else:
                console.print("[yellow]Message scanning test failed. Check screenshots for details.[/yellow]")
        
        return True
    else:
        console.print("[red]WhatsApp Web connection test failed.[/red]")
        return False

if __name__ == "__main__":
    init_directories()
    console.print("[bold]WhatsApp Web Integration Tester[/bold]")
    console.print("This script tests the connection to WhatsApp Web.")
    
    if input("Configure WhatsApp integration? (y/n): ").lower() == 'y':
        configure_whatsapp()
    elif input("Test WhatsApp connection? (y/n): ").lower() == 'y':
        connect_to_whatsapp()
    elif input("Test scanning messages? (y/n): ").lower() == 'y':
        config = load_config()
        groups = config.get("groups", [])
        if groups:
            scan_messages(groups[0])
        else:
            console.print("[yellow]No groups configured. Run with configuration option first.[/yellow]")