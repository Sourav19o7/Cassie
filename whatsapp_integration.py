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

# Initialize app constants first
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
WHATSAPP_CONFIG_PATH = APP_DIR / "whatsapp_config.json"
WHATSAPP_SESSION_PATH = APP_DIR / "whatsapp_session"
SERVICE_NAME = "empathic-solver"

console = Console()

# Define SELENIUM_AVAILABLE globally before using it
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
        # Stub for get_whatsapp_driver function that would normally be defined
        # We'll just simulate the function for now
        console.print("[yellow]Driver initialization is implemented in the full module.[/yellow]")
        return True
        
    except Exception as e:
        console.print(f"[red]Error testing WhatsApp Web connection: {e}[/red]")
        return False

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
    console.print("[yellow]This functionality would scan WhatsApp messages in the configured groups.[/yellow]")
    console.print("[yellow]For now, this is a placeholder as full scanning requires Selenium setup.[/yellow]")

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

# When run directly, initialize the module
if __name__ == "__main__":
    # Initialize and test the module
    init_whatsapp_integration()
    config = load_whatsapp_config()
    
    console.print("WhatsApp Integration Module")
    console.print("==========================")
    
    if typer.confirm("Would you like to configure WhatsApp integration?"):
        configure_whatsapp()