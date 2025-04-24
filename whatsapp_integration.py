"""
WhatsApp Integration Module for Empathic Problem Solver CLI
Enables scanning WhatsApp messages and extracting actionable tasks.
"""

import os
import re
import json
import sqlite3
import datetime
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
import requests
import keyring

# Path constants
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
WHATSAPP_CONFIG_PATH = APP_DIR / "whatsapp_config.json"
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
    
    # Create WhatsApp config if it doesn't exist
    if not WHATSAPP_CONFIG_PATH.exists():
        config = {
            "whatsapp_web_enabled": False,
            "last_scan_time": None,
            "monitored_groups": [],
            "scan_interval": 3600  # Default scan interval in seconds (1 hour)
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
        FOREIGN KEY (problem_id) REFERENCES problems (id)
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
    
    # Enable/disable WhatsApp Web integration
    web_enabled = typer.confirm(
        "Enable WhatsApp Web integration?", 
        default=config.get("whatsapp_web_enabled", False)
    )
    config["whatsapp_web_enabled"] = web_enabled
    
    if web_enabled:
        # Configure scan interval
        scan_interval = typer.prompt(
            "How often to scan messages (in minutes)", 
            default=config.get("scan_interval", 3600) // 60,
            type=int
        )
        config["scan_interval"] = scan_interval * 60  # Convert to seconds
        
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
        
        console.print(f"WhatsApp integration configured to scan {len(existing_groups)} groups every {scan_interval} minutes.")
    else:
        console.print("WhatsApp integration disabled.")
    
    save_whatsapp_config(config)
    
    if web_enabled:
        console.print(Panel("""
        [bold]WhatsApp Web Integration Instructions:[/bold]
        
        1. Make sure you're logged into WhatsApp Web at https://web.whatsapp.com/
        2. The CLI will scan your messages during regular usage
        3. You can manually scan for tasks using the 'scan-whatsapp' command
        
        [yellow]Note: This integration requires WhatsApp Web to be open in your browser.[/yellow]
        """, title="Setup Instructions"))
    
    return config

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
    
    # Format messages for Claude
    message_text = "\n\n".join([
        f"Group: {msg['group']}\nSender: {msg['sender']}\nTime: {msg['timestamp']}\nMessage: {msg['message']}"
        for msg in messages
    ])
    
    prompt = f"""
    Please analyze these WhatsApp messages and extract any actionable tasks or todo items.
    For each task you identify, please provide:
    1. A clear task description
    2. The priority level (high, medium, or low)
    3. The group and sender it came from
    
    Only extract tasks that represent actual action items or requests - ignore general conversation.
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
            for i, task in enumerate(tasks):
                # Find the original message this task came from
                for msg in messages:
                    if msg['group'] == task['group'] and msg['sender'] == task['sender']:
                        task['message'] = msg['message']
                        task['timestamp'] = msg['timestamp']
                        break
                
                # Set problem_id if provided
                if problem_id:
                    task['problem_id'] = problem_id
            
            return tasks
        return []
    except Exception as e:
        console.print(f"[yellow]Error parsing Claude response: {str(e)}[/yellow]")
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
            
            cursor.execute(
                """
                INSERT INTO whatsapp_tasks 
                (problem_id, group_name, sender, message, task_description, timestamp, status, priority)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    problem_id,
                    task['group'],
                    task['sender'],
                    task.get('message', ''),
                    task['task_description'],
                    task.get('timestamp', datetime.datetime.now().isoformat()),
                    task['priority']
                )
            )
            tasks_added += 1
        except Exception as e:
            console.print(f"[yellow]Error saving task: {e}[/yellow]")
    
    conn.commit()
    conn.close()
    
    return tasks_added

def get_whatsapp_messages():
    """
    Get WhatsApp messages through web interface or exported chat.
    
    In a real implementation, this would use browser automation tools like Selenium
    to interact with WhatsApp Web, or parse exported chat files.
    
    For this implementation, we'll use a simulated approach.
    """
    config = load_whatsapp_config()
    
    if not config.get("whatsapp_web_enabled", False):
        console.print("[yellow]WhatsApp integration is not enabled. Run 'configure-whatsapp' first.[/yellow]")
        return []
    
    monitored_groups = config.get("monitored_groups", [])
    if not monitored_groups:
        console.print("[yellow]No WhatsApp groups configured for monitoring.[/yellow]")
        return []
    
    # In a real implementation, this would access WhatsApp Web
    # For now, we'll return an example response for demonstration
    console.print("[cyan]Scanning WhatsApp messages...[/cyan]")
    
    # Simulated messages for demonstration
    last_scan_time = config.get("last_scan_time")
    
    # Update last scan time
    config["last_scan_time"] = datetime.datetime.now().isoformat()
    save_whatsapp_config(config)
    
    # Prompt user to enter messages for testing
    if typer.confirm("Would you like to enter test messages? (In a real implementation, this would automatically scan WhatsApp Web)"):
        test_messages = []
        group = typer.prompt("Enter group name")
        
        while typer.confirm("Add a message?"):
            sender = typer.prompt("Sender name")
            message = typer.prompt("Message")
            timestamp = datetime.datetime.now().isoformat()
            
            test_messages.append({
                "group": group,
                "sender": sender,
                "message": message,
                "timestamp": timestamp
            })
        
        return test_messages
    
    # Example messages for demonstration
    return [
        {
            "group": "Project Team",
            "sender": "John Smith",
            "message": "Can someone please research pricing options for the new software by tomorrow?",
            "timestamp": datetime.datetime.now().isoformat()
        },
        {
            "group": "Project Team",
            "sender": "Mary Johnson",
            "message": "I'll handle the client presentation next week. Let's aim for Tuesday.",
            "timestamp": datetime.datetime.now().isoformat()
        },
        {
            "group": "Family Group",
            "sender": "Mom",
            "message": "Don't forget we have dinner on Sunday at 6pm",
            "timestamp": datetime.datetime.now().isoformat()
        }
    ]

def scan_whatsapp_for_tasks(problem_id=None):
    """
    Scan WhatsApp messages and extract actionable tasks.
    
    Args:
        problem_id: Optional ID of problem to associate tasks with
    
    Returns:
        Number of tasks extracted
    """
    messages = get_whatsapp_messages()
    if not messages:
        return 0
    
    tasks = extract_tasks_from_messages(messages, problem_id)
    count = save_tasks_to_database(tasks)
    
    return count

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
        
        date = datetime.datetime.fromisoformat(timestamp).strftime("%Y-%m-%d")
        
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
               timestamp, status, priority
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
    
    task_id, problem_id, group, sender, message, description, timestamp, status, priority = task
    
    # Get problem title if available
    problem_title = "Not assigned"
    if problem_id:
        cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
        problem = cursor.fetchone()
        if problem:
            problem_title = problem[0]
    
    conn.close()
    
    # Format date
    date = datetime.datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
    
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
    console.print("1. Mark as completed: whatsapp-complete-task", task_id)
    console.print("2. Assign to problem: whatsapp-assign-task", task_id, "<problem_id>")
    console.print("3. Convert to action step: whatsapp-convert-task", task_id)
    
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
    count = scan_whatsapp_for_tasks(problem_id)
    
    if count > 0:
        console.print(f"[green]Found {count} actionable tasks from WhatsApp messages![/green]")
        list_whatsapp_tasks(limit=count)
    else:
        console.print("[yellow]No actionable tasks found in recent WhatsApp messages.[/yellow]")

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

# Example of how to use this module
if __name__ == "__main__":
    # This could be used for testing the module directly
    init_whatsapp_integration()
    print("WhatsApp integration module initialized")
    
    # Test task extraction
    messages = [
        {
            "group": "Project Team",
            "sender": "John Smith",
            "message": "Can someone please research pricing options for the new software by tomorrow?",
            "timestamp": datetime.datetime.now().isoformat()
        },
        {
            "group": "Project Team",
            "sender": "Mary Johnson",
            "message": "I'll handle the client presentation next week. Let's aim for Tuesday.",
            "timestamp": datetime.datetime.now().isoformat()
        }
    ]
    
    tasks = extract_tasks_from_messages(messages)
    print(f"Extracted {len(tasks)} tasks:")
    for task in tasks:
        print(f"- {task['task_description']} (Priority: {task['priority']})")