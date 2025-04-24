#!/usr/bin/env python3
"""
Empathic Problem Solver CLI - A personal agent that helps solve problems through
empathetic understanding, KPI tracking, and data-driven recommendations.
Powered by Claude Haiku for AI-driven insights.
"""

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

# Initialize Typer app
app = typer.Typer(help="Empathic Problem Solver CLI")
console = Console()

# Create application data directory
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
CONFIG_PATH = APP_DIR / "config.json"

# Constants
SERVICE_NAME = "empathic-solver"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-3-haiku-20240307"

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
            "api_key_set": False
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)

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

def get_api_key():
    """Get the Claude API key from keyring."""
    api_key = keyring.get_password(SERVICE_NAME, "claude_api_key")
    return api_key

def set_api_key(api_key):
    """Save the Claude API key to keyring."""
    keyring.set_password(SERVICE_NAME, "claude_api_key", api_key)
    
    # Update config
    config = load_config()
    config["api_key_set"] = True
    save_config(config)

def call_claude_api(prompt, model=None, max_tokens=500):
    """Call the Claude API with the given prompt."""
    config = load_config()
    
    if model is None:
        model = config.get("model", DEFAULT_MODEL)
    
    api_key = get_api_key()
    if not api_key:
        console.print("[yellow]Claude API key not set. Using fallback methods.[/yellow]")
        return None
    
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
        console.print("[cyan]Thinking...[/cyan]")
        
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

def get_empathetic_response(problem_description: str) -> str:
    """Generate an empathetic response based on the problem description using Claude."""
    config = load_config()
    
    if config.get("use_ai", True) and config.get("api_key_set", False):
        prompt = f"""
        As an empathetic problem-solving assistant, provide a brief, caring response to someone facing this challenge:
        
        "{problem_description}"
        
        Your response should:
        1. Show understanding of their feelings
        2. Be encouraging and supportive
        3. Be concise (2-3 sentences)
        4. Avoid generic platitudes
        5. Don't mention that we'll break down the problem into parts or set KPIs - just be empathetic
        """
        
        response = call_claude_api(prompt)
        if response:
            return response.strip()
    
    # Fallback to rule-based responses if API call fails or is disabled
    problem_description = problem_description.lower()
    
    responses = {
        'stress': "I understand that you're feeling stressed. That's a common reaction when facing difficult challenges. Let's work through this together.",
        'overwhelm': "It sounds like you're feeling overwhelmed, which is completely understandable. We'll find a way to make this more manageable.",
        'stuck': "Being stuck can be frustrating. I appreciate you sharing this challenge, and I'm here to help you find a path forward.",
        'difficult': "You're facing a difficult situation, and that takes courage to address. I'm here to support you through this process.",
        'worry': "I hear your concern. It's natural to worry about important matters, and your awareness shows how much you care.",
        'deadline': "Deadlines can create significant pressure. I understand the time constraints you're under and want to help you succeed.",
        'conflict': "Navigating conflicts can be challenging. I appreciate your willingness to address this situation and find resolution.",
        'motivation': "Finding motivation can be difficult. Your awareness of this challenge is already a meaningful first step.",
        'tired': "Feeling tired or burned out is your mind and body telling you something important. Your wellbeing matters in this process.",
        'confused': "It's normal to feel confused when facing complex situations. Clarity will come as we work through this methodically."
    }
    
    for keyword, response in responses.items():
        if keyword in problem_description:
            return response
    
    # Default response if no keywords match
    return "I understand you're facing a challenge. Your willingness to address it shows commitment, and I'm here to support you through this process."

def generate_kpis(problem_description: str) -> List[Dict]:
    """Generate relevant KPIs based on the problem description using Claude."""
    config = load_config()
    
    if config.get("use_ai", True) and config.get("api_key_set", False):
        prompt = f"""
        As an expert in metrics and KPIs, analyze this problem description and generate relevant KPIs to track progress:
        
        "{problem_description}"
        
        For each KPI, provide:
        1. A clear description
        2. A reasonable target value
        
        Format your response as a JSON array of objects, each with "description" and "target_value" fields.
        Example: 
        [
          {{"description": "Study hours per week", "target_value": 10}},
          {{"description": "Practice sessions completed", "target_value": 5}}
        ]
        
        Generate 3-5 specific, measurable KPIs that directly relate to the problem.
        """
        
        response = call_claude_api(prompt)
        if response:
            try:
                # Extract JSON from the response
                json_str = response.strip()
                # Find the first '[' and last ']' to extract just the JSON array
                start = json_str.find('[')
                end = json_str.rfind(']') + 1
                if start != -1 and end != 0:
                    json_str = json_str[start:end]
                    return json.loads(json_str)
            except Exception as e:
                console.print(f"[yellow]Error parsing Claude KPI response: {str(e)}. Using fallback KPIs.[/yellow]")
    
    # Fallback to rule-based KPI generation if API call fails or is disabled
    problem_description = problem_description.lower()
    kpis = []
    
    # Work/productivity related KPIs
    if any(word in problem_description for word in ['work', 'productivity', 'efficiency', 'output', 'perform']):
        kpis.extend([
            {"description": "Tasks completed per day", "target_value": 5},
            {"description": "Focus time in hours", "target_value": 4},
            {"description": "Satisfaction with daily output (1-10)", "target_value": 8}
        ])
    
    # Learning/skill related KPIs
    if any(word in problem_description for word in ['learn', 'study', 'skill', 'knowledge', 'improve', 'better']):
        kpis.extend([
            {"description": "Study hours per week", "target_value": 10},
            {"description": "Practice sessions completed", "target_value": 5},
            {"description": "Concepts mastered", "target_value": 3}
        ])
    
    # Health/wellness related KPIs
    if any(word in problem_description for word in ['health', 'wellness', 'fitness', 'stress', 'sleep', 'mental']):
        kpis.extend([
            {"description": "Exercise sessions per week", "target_value": 4},
            {"description": "Hours of quality sleep per night", "target_value": 7},
            {"description": "Stress level reduction (1-10, lower is better)", "target_value": 3}
        ])
    
    # Project/goal related KPIs
    if any(word in problem_description for word in ['project', 'goal', 'objective', 'deadline', 'achieve', 'milestone']):
        kpis.extend([
            {"description": "Milestone completion percentage", "target_value": 100},
            {"description": "Hours dedicated to project per week", "target_value": 15},
            {"description": "Blockers resolved", "target_value": 5}
        ])
    
    # Relationship/social KPIs
    if any(word in problem_description for word in ['relationship', 'social', 'friend', 'family', 'communicate', 'team']):
        kpis.extend([
            {"description": "Quality interactions per week", "target_value": 5},
            {"description": "Conflict resolution success rate (%)", "target_value": 90},
            {"description": "Communication satisfaction (1-10)", "target_value": 8}
        ])
    
    # Financial KPIs
    if any(word in problem_description for word in ['finance', 'money', 'budget', 'save', 'spend', 'income']):
        kpis.extend([
            {"description": "Monthly savings target ($)", "target_value": 500},
            {"description": "Expense reduction (%)", "target_value": 15},
            {"description": "Additional income streams", "target_value": 1}
        ])
    
    # If no specific KPIs were generated, add some general ones
    if not kpis:
        kpis = [
            {"description": "Progress satisfaction (1-10)", "target_value": 8},
            {"description": "Obstacles overcome", "target_value": 5},
            {"description": "Time invested in hours", "target_value": 20}
        ]
    
    # Limit to 5 most relevant KPIs
    return kpis[:5]

def generate_action_steps(problem_description: str, kpis: List[Dict]) -> List[str]:
    """Generate action steps based on the problem description and KPIs using Claude."""
    config = load_config()
    
    if config.get("use_ai", True) and config.get("api_key_set", False):
        # Format KPIs as a string for the prompt
        kpi_str = "\n".join([f"- {kpi['description']} (Target: {kpi['target_value']})" for kpi in kpis])
        
        prompt = f"""
        As an expert problem solver, create a list of specific action steps to address this problem:
        
        Problem: "{problem_description}"
        
        KPIs to achieve:
        {kpi_str}
        
        Provide 5-8 concrete, actionable steps that will help achieve these KPIs. 
        Each step should be specific enough to be actionable but brief (one sentence).
        
        Format your response as a JSON array of strings.
        Example: ["Research best practices", "Schedule daily focus time", "Create a tracking system"]
        """
        
        response = call_claude_api(prompt)
        if response:
            try:
                # Extract JSON from the response
                json_str = response.strip()
                # Find the first '[' and last ']' to extract just the JSON array
                start = json_str.find('[')
                end = json_str.rfind(']') + 1
                if start != -1 and end != 0:
                    json_str = json_str[start:end]
                    return json.loads(json_str)
            except Exception as e:
                console.print(f"[yellow]Error parsing Claude action steps response: {str(e)}. Using fallback steps.[/yellow]")
    
    # Fallback to rule-based action step generation if API call fails or is disabled
    problem_description = problem_description.lower()
    
    # Start with some universal steps
    action_steps = [
        "Define the specific boundaries and scope of the problem",
        "Research best practices and potential solutions"
    ]
    
    # Add steps for tracking each KPI
    for kpi in kpis:
        action_steps.append(f"Track progress on: {kpi['description']}")
    
    # Add domain-specific steps
    if any(word in problem_description for word in ['work', 'productivity', 'efficiency']):
        action_steps.extend([
            "Implement time-blocking for focused work sessions",
            "Identify and eliminate the top 3 distractions in your environment",
            "Create templates for recurring tasks to save time"
        ])
    
    if any(word in problem_description for word in ['learn', 'study', 'skill']):
        action_steps.extend([
            "Break down learning goals into digestible modules",
            "Schedule regular practice sessions with clear objectives",
            "Set up a system to get feedback on your progress"
        ])
    
    if any(word in problem_description for word in ['health', 'wellness', 'fitness']):
        action_steps.extend([
            "Create a sustainable daily routine that supports your health",
            "Identify and reduce major sources of stress",
            "Establish accountability mechanisms for health habits"
        ])
    
    if any(word in problem_description for word in ['project', 'goal', 'deadline']):
        action_steps.extend([
            "Break the project into clear milestones with deadlines",
            "Identify potential bottlenecks and prepare contingency plans",
            "Schedule regular project reviews to stay on track"
        ])
    
    # Add some generic but helpful action steps
    action_steps.extend([
        "Set aside dedicated time each day to work on this problem",
        "Review progress weekly and adjust approach as needed",
        "Seek feedback from relevant stakeholders or peers",
        "Document lessons learned and successful strategies"
    ])
    
    # Return up to 8 steps
    return action_steps[:8]

def calculate_moving_average(problem_id: int, kpi_id: int, window: int = 5) -> Dict:
    """Calculate moving average for a KPI's progress."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT value, timestamp FROM progress_logs WHERE problem_id = ? AND kpi_id = ? ORDER BY timestamp",
        conn, 
        params=(problem_id, kpi_id)
    )
    conn.close()
    
    if len(df) == 0:
        return {"trend": "No data", "moving_avg": None}
    
    if len(df) < 2:
        return {"trend": "Insufficient data", "moving_avg": None}
    
    # Convert to datetime for proper time series analysis
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    
    # Calculate moving average
    window_size = min(window, len(df))
    df['moving_avg'] = df['value'].rolling(window=window_size).mean()
    
    # Determine trend
    recent_avg = df['moving_avg'].iloc[-1] if not pd.isna(df['moving_avg'].iloc[-1]) else df['value'].iloc[-1]
    
    if len(df) < 3:
        trend = "Neutral (need more data)"
    else:
        # Use linear regression to determine trend
        x = np.arange(len(df[-3:]))
        y = df['value'].iloc[-3:].values
        slope = np.polyfit(x, y, 1)[0]
        
        if slope > 0.1:
            trend = "Improving"
        elif slope < -0.1:
            trend = "Declining"
        else:
            trend = "Stable"
    
    return {
        "trend": trend,
        "moving_avg": recent_avg if not pd.isna(recent_avg) else df['value'].mean()
    }

def get_recommendations(problem_id: int) -> List[str]:
    """Generate recommendations based on progress trends using Claude."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get problem details
    cursor.execute("SELECT title, description FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    if not problem:
        return ["Problem not found"]
    
    title, description = problem
    
    # Get all KPIs for the problem
    cursor.execute("SELECT id, description, target_value, current_value FROM kpis WHERE problem_id = ?", 
                  (problem_id,))
    kpis = cursor.fetchall()
    
    # Get action steps
    cursor.execute("SELECT id, description, status FROM action_steps WHERE problem_id = ?", 
                  (problem_id,))
    action_steps = cursor.fetchall()
    
    conn.close()
    
    config = load_config()
    
    if config.get("use_ai", True) and config.get("api_key_set", False):
        # Prepare KPI data
        kpi_data = []
        for kpi_id, description, target, current in kpis:
            trend_data = calculate_moving_average(problem_id, kpi_id)
            progress_pct = (current / target * 100) if target > 0 else 0
            
            kpi_data.append({
                "description": description,
                "target_value": target,
                "current_value": current,
                "progress_percentage": progress_pct,
                "trend": trend_data["trend"]
            })
        
        # Prepare action steps data
        steps_data = []
        for step_id, description, status in action_steps:
            steps_data.append({
                "description": description,
                "status": status
            })
        
        # Create the prompt for Claude
        prompt = f"""
        As a problem-solving advisor, analyze this problem and progress data to provide targeted recommendations:
        
        Problem: "{title}: {description}"
        
        KPI Progress:
        {json.dumps(kpi_data, indent=2)}
        
        Action Steps:
        {json.dumps(steps_data, indent=2)}
        
        Based on this data, provide 3-5 specific, actionable recommendations to help make progress.
        Focus on KPIs with low progress or declining trends, and suggest concrete next steps.
        
        Format your response as a JSON array of strings, with each string being a single recommendation.
        Example: ["Focus on increasing 'Study hours' which is at 30% of target", "Address declining trend in 'Practice sessions'"]
        """
        
        response = call_claude_api(prompt)
        if response:
            try:
                # Extract JSON from the response
                json_str = response.strip()
                # Find the first '[' and last ']' to extract just the JSON array
                start = json_str.find('[')
                end = json_str.rfind(']') + 1
                if start != -1 and end != 0:
                    json_str = json_str[start:end]
                    return json.loads(json_str)
            except Exception as e:
                console.print(f"[yellow]Error parsing Claude recommendations response: {str(e)}. Using fallback recommendations.[/yellow]")
    
    # Fallback to rule-based recommendations if API call fails or is disabled
    recommendations = []
    
    # Analyze each KPI
    for kpi_id, description, target, current in kpis:
        trend_data = calculate_moving_average(problem_id, kpi_id)
        
        # Calculate progress percentage
        progress_pct = (current / target * 100) if target > 0 else 0
        
        if progress_pct < 30:
            recommendations.append(f"Focus on increasing '{description}' which is at {progress_pct:.1f}% of target")
        
        if trend_data["trend"] == "Declining":
            recommendations.append(f"Address declining trend in '{description}'")
        elif trend_data["trend"] == "Stable" and progress_pct < 70:
            recommendations.append(f"Find ways to accelerate progress on '{description}'")
        elif trend_data["trend"] == "Improving" and progress_pct > 90:
            recommendations.append(f"Consider increasing the target for '{description}' as you're exceeding expectations")
    
    # Check for incomplete action steps
    pending_steps = [desc for _, desc, status in action_steps if status != 'completed']
    if pending_steps:
        recommendations.append(f"Complete the {len(pending_steps)} remaining action steps")
        if len(pending_steps) >= 3:
            recommendations.append("Consider prioritizing action steps to make steady progress")
    
    # If all KPIs are doing well, suggest maintenance
    all_good = True
    for kpi_id, description, target, current in kpis:
        progress_pct = (current / target * 100) if target > 0 else 0
        trend_data = calculate_moving_average(problem_id, kpi_id)
        if progress_pct < 70 or trend_data["trend"] == "Declining":
            all_good = False
            break
    
    if all_good and len(pending_steps) <= 2:
        recommendations.append("Maintain current strategies as they're working well")
        recommendations.append("Document what's working for future reference")
    
    # If no specific recommendations, add general ones
    if not recommendations:
        recommendations = [
            "Continue with current approach as progress looks good",
            "Consider increasing targets if you find current goals too easy",
            "Document successful strategies for future reference"
        ]
    
    return recommendations[:5]  # Limit to top 5 recommendations

@app.command()
def configure():
    """Configure the application settings."""
    config = load_config()
    
    # API Key
    current_key = get_api_key()
    if current_key:
        console.print("Claude API key is currently set.")
        if typer.confirm("Do you want to update your API key?"):
            new_key = getpass.getpass("Enter your Claude API key: ")
            set_api_key(new_key)
            console.print("[green]API key updated successfully.[/green]")
    else:
        console.print("Claude API key is not set.")
        if typer.confirm("Do you want to set your API key now?"):
            new_key = getpass.getpass("Enter your Claude API key: ")
            set_api_key(new_key)
            console.print("[green]API key set successfully.[/green]")
    
    # Use AI
    use_ai = typer.confirm("Do you want to use Claude AI for responses?", default=config.get("use_ai", True))
    config["use_ai"] = use_ai
    
    # Claude model
    if use_ai:
        models = [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229"
        ]
        current_model = config.get("model", DEFAULT_MODEL)
        console.print(f"Current model: [bold]{current_model}[/bold]")
        console.print("Available models:")
        for i, model in enumerate(models, 1):
            console.print(f"{i}. {model}")
        
        choice = typer.prompt("Select a model (1-3)", default="1")
        try:
            model_idx = int(choice) - 1
            if 0 <= model_idx < len(models):
                config["model"] = models[model_idx]
        except ValueError:
            console.print("[yellow]Invalid choice. Keeping current model.[/yellow]")
    
    # Max tokens
    max_tokens = typer.prompt("Maximum tokens for Claude responses", default=str(config.get("max_tokens", 500)))
    try:
        config["max_tokens"] = int(max_tokens)
    except ValueError:
        console.print("[yellow]Invalid value. Using default of 500.[/yellow]")
        config["max_tokens"] = 500
    
    # Save config
    save_config(config)
    console.print("[green]Configuration updated successfully.[/green]")

@app.command()
def new(title: str = typer.Option(..., prompt=True, help="Short title for your problem"),
        description: str = typer.Option(..., prompt=True, help="Detailed description of the problem")):
    """Create a new problem to track."""
    init_app()
    
    # Check if API key is set, prompt if needed
    config = load_config()
    if config.get("use_ai", True) and not config.get("api_key_set", False):
        console.print("[yellow]Claude API key is not set. AI features will be limited.[/yellow]")
        if typer.confirm("Would you like to set your Claude API key now?"):
            api_key = getpass.getpass("Enter your Claude API key: ")
            set_api_key(api_key)
            console.print("[green]API key set successfully.[/green]")
    
    # Get empathetic response
    empathetic_response = get_empathetic_response(description)
    console.print(Panel(empathetic_response, title="Understanding Your Challenge", border_style="blue"))
    
    console.print("[cyan]Generating KPIs...[/cyan]")
    # Generate KPIs
    kpis = generate_kpis(description)
    
    console.print("[cyan]Creating action plan...[/cyan]")
    # Generate action steps
    action_steps = generate_action_steps(description, kpis)
    
    # Store in database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Add problem
    cursor.execute(
        "INSERT INTO problems (title, description, created_date) VALUES (?, ?, ?)",
        (title, description, datetime.datetime.now().isoformat())
    )
    problem_id = cursor.lastrowid
    
    # Add KPIs
    for kpi in kpis:
        cursor.execute(
            "INSERT INTO kpis (problem_id, description, target_value, current_value) VALUES (?, ?, ?, ?)",
            (problem_id, kpi["description"], kpi["target_value"], 0)
        )
    
    # Add action steps
    for step in action_steps:
        cursor.execute(
            "INSERT INTO action_steps (problem_id, description) VALUES (?, ?)",
            (problem_id, step)
        )
    
    conn.commit()
    conn.close()
    
    # Display the new problem
    display_problem(problem_id)

@app.command()
def list():
    """List all active problems."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, title, created_date FROM problems WHERE status = 'active'")
    problems = cursor.fetchall()
    
    conn.close()
    
    if not problems:
        console.print("No active problems found. Create one with 'new' command.")
        return
    
    table = Table(title="Active Problems")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Created Date")
    
    for problem_id, title, created_date in problems:
        created = datetime.datetime.fromisoformat(created_date).strftime("%Y-%m-%d")
        table.add_row(str(problem_id), title, created)
    
    console.print(table)

@app.command()
def view(problem_id: int = typer.Argument(..., help="ID of the problem to view")):
    """View details of a specific problem."""
    init_app()
    display_problem(problem_id)

def display_problem(problem_id: int):
    """Display comprehensive information about a problem."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get problem details
    cursor.execute("SELECT title, description FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"Problem with ID {problem_id} not found.")
        return
    
    title, description = problem
    
    # Get KPIs
    cursor.execute("SELECT id, description, target_value, current_value FROM kpis WHERE problem_id = ?", 
                  (problem_id,))
    kpis = cursor.fetchall()
    
    # Get action steps
    cursor.execute("SELECT id, description, status FROM action_steps WHERE problem_id = ?", 
                  (problem_id,))
    action_steps = cursor.fetchall()
    
    conn.close()
    
    # Display problem overview
    console.print(Panel(f"[bold]{title}[/bold]\n\n{description}", 
                        title="Problem Overview", 
                        border_style="green"))
    
    # Display KPIs
    kpi_table = Table(title="Key Performance Indicators (KPIs)")
    kpi_table.add_column("ID")
    kpi_table.add_column("Description")
    kpi_table.add_column("Target")
    kpi_table.add_column("Current")
    kpi_table.add_column("Progress")
    kpi_table.add_column("Trend")
    
    for kpi_id, description, target, current in kpis:
        progress_pct = (current / target * 100) if target > 0 else 0
        trend_data = calculate_moving_average(problem_id, kpi_id)
        
        progress_style = "green" if progress_pct >= 75 else "yellow" if progress_pct >= 25 else "red"
        trend_style = "green" if trend_data["trend"] == "Improving" else "red" if trend_data["trend"] == "Declining" else "yellow"
        
        kpi_table.add_row(
            str(kpi_id),
            description,
            f"{target}",
            f"{current}",
            f"[{progress_style}]{progress_pct:.1f}%[/{progress_style}]",
            f"[{trend_style}]{trend_data['trend']}[/{trend_style}]"
        )
    
    console.print(kpi_table)
    
    # Display action steps
    action_table = Table(title="Action Steps")
    action_table.add_column("ID")
    action_table.add_column("Description")
    action_table.add_column("Status")
    
    for step_id, description, status in action_steps:
        status_style = "green" if status == "completed" else "yellow"
        action_table.add_row(
            str(step_id),
            description,
            f"[{status_style}]{status}[/{status_style}]"
        )
    
    console.print(action_table)
    
    # Display recommendations without progress indicator
    console.print("\n[bold]Generating recommendations based on your progress...[/bold]")
    time.sleep(1)  # Simple delay instead of progress bar
    recommendations = get_recommendations(problem_id)
    
    rec_md = "## Recommendations\n\n" + "\n".join([f"- {r}" for r in recommendations])
    console.print(Markdown(rec_md))

@app.command()
def update_kpi(
    kpi_id: int = typer.Argument(..., help="ID of the KPI to update"),
    value: float = typer.Argument(..., help="New current value for the KPI")
):
    """Update the current value of a KPI."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get KPI details
    cursor.execute("SELECT problem_id, description, current_value FROM kpis WHERE id = ?", (kpi_id,))
    kpi = cursor.fetchone()
    
    if not kpi:
        console.print(f"KPI with ID {kpi_id} not found.")
        return
    
    problem_id, description, current_value = kpi
    
    # Update KPI value
    cursor.execute(
        "UPDATE kpis SET current_value = ? WHERE id = ?",
        (value, kpi_id)
    )
    
    # Log progress
    cursor.execute(
        "INSERT INTO progress_logs (problem_id, kpi_id, value, timestamp) VALUES (?, ?, ?, ?)",
        (problem_id, kpi_id, value, datetime.datetime.now().isoformat())
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"Updated KPI '[bold]{description}[/bold]' from {current_value} to {value}")
    
    # Show trend after update
    trend_data = calculate_moving_average(problem_id, kpi_id)
    console.print(f"Current trend: [bold]{trend_data['trend']}[/bold]")
    
    # Ask if user wants to see full problem details
    if typer.confirm("Would you like to see the full problem details?"):
        display_problem(problem_id)

@app.command()
def complete_step(
    step_id: int = typer.Argument(..., help="ID of the action step to mark as completed")
):
    """Mark an action step as completed."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get step details
    cursor.execute("SELECT problem_id, description FROM action_steps WHERE id = ?", (step_id,))
    step = cursor.fetchone()
    
    if not step:
        console.print(f"Action step with ID {step_id} not found.")
        return
    
    problem_id, description = step
    
    # Update step status
    cursor.execute(
        "UPDATE action_steps SET status = 'completed' WHERE id = ?",
        (step_id,)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"Marked step '[bold]{description}[/bold]' as completed!")
    
    # Ask if user wants to see full problem details
    if typer.confirm("Would you like to see the full problem details?"):
        display_problem(problem_id)

@app.command()
def uncomplete_step(
    step_id: int = typer.Argument(..., help="ID of the action step to mark as pending")
):
    """Mark a completed action step as pending again."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get step details
    cursor.execute("SELECT problem_id, description FROM action_steps WHERE id = ?", (step_id,))
    step = cursor.fetchone()
    
    if not step:
        console.print(f"Action step with ID {step_id} not found.")
        return
    
    problem_id, description = step
    
    # Update step status
    cursor.execute(
        "UPDATE action_steps SET status = 'pending' WHERE id = ?",
        (step_id,)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"Marked step '[bold]{description}[/bold]' as pending.")
    
    # Ask if user wants to see full problem details
    if typer.confirm("Would you like to see the full problem details?"):
        display_problem(problem_id)

@app.command()
def add_step(
    problem_id: int = typer.Argument(..., help="ID of the problem to add a step to"),
    description: str = typer.Option(..., prompt=True, help="Description of the new action step")
):
    """Add a new action step to a problem."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if problem exists
    cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"Problem with ID {problem_id} not found.")
        return
    
    # Add action step
    cursor.execute(
        "INSERT INTO action_steps (problem_id, description) VALUES (?, ?)",
        (problem_id, description)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"Added new action step: '[bold]{description}[/bold]'")
    
    # Ask if user wants to see full problem details
    if typer.confirm("Would you like to see the full problem details?"):
        display_problem(problem_id)

@app.command()
def add_kpi(
    problem_id: int = typer.Argument(..., help="ID of the problem to add a KPI to"),
    description: str = typer.Option(..., prompt=True, help="Description of the new KPI"),
    target: float = typer.Option(..., prompt=True, help="Target value for the new KPI")
):
    """Add a new KPI to a problem."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if problem exists
    cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"Problem with ID {problem_id} not found.")
        return
    
    # Add KPI
    cursor.execute(
        "INSERT INTO kpis (problem_id, description, target_value, current_value) VALUES (?, ?, ?, ?)",
        (problem_id, description, target, 0)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"Added new KPI: '[bold]{description}[/bold]' with target {target}")
    
    # Ask if user wants to see full problem details
    if typer.confirm("Would you like to see the full problem details?"):
        display_problem(problem_id)

@app.command()
def complete(
    problem_id: int = typer.Argument(..., help="ID of the problem to mark as completed")
):
    """Mark a problem as completed."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get problem details
    cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"Problem with ID {problem_id} not found.")
        return
    
    title = problem[0]
    
    # Update problem status
    cursor.execute(
        "UPDATE problems SET status = 'completed' WHERE id = ?",
        (problem_id,)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"Marked problem '[bold]{title}[/bold]' as completed! Congratulations!")

@app.command()
def reactivate(
    problem_id: int = typer.Argument(..., help="ID of the completed problem to reactivate")
):
    """Reactivate a completed problem."""
    init_app()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get problem details
    cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"Problem with ID {problem_id} not found.")
        return
    
    title = problem[0]
    
    # Update problem status
    cursor.execute(
        "UPDATE problems SET status = 'active' WHERE id = ?",
        (problem_id,)
    )
    
    conn.commit()
    conn.close()
    
    console.print(f"Reactivated problem '[bold]{title}[/bold]'")
    
    # Ask if user wants to see full problem details
    if typer.confirm("Would you like to see the full problem details?"):
        display_problem(problem_id)

@app.command()
def export(
    problem_id: int = typer.Argument(..., help="ID of the problem to export"),
    output_file: str = typer.Option(None, help="Output file path (default: problem_[id].json)")
):
    """Export problem data to a JSON file."""
    init_app()
    
    if not output_file:
        output_file = f"problem_{problem_id}.json"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Get problem details
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"Problem with ID {problem_id} not found.")
        return
    
    problem_dict = dict(problem)
    
    # Get KPIs
    cursor.execute("SELECT * FROM kpis WHERE problem_id = ?", (problem_id,))
    kpis = [dict(row) for row in cursor.fetchall()]
    
    # Get action steps
    cursor.execute("SELECT * FROM action_steps WHERE problem_id = ?", (problem_id,))
    action_steps = [dict(row) for row in cursor.fetchall()]
    
    # Get progress logs
    cursor.execute("SELECT * FROM progress_logs WHERE problem_id = ?", (problem_id,))
    progress_logs = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Assemble export data
    export_data = {
        "problem": problem_dict,
        "kpis": kpis,
        "action_steps": action_steps,
        "progress_logs": progress_logs,
        "exported_date": datetime.datetime.now().isoformat()
    }
    
    # Write to file
    with open(output_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    console.print(f"Problem data exported to [bold]{output_file}[/bold]")

@app.command()
def import_problem(
    input_file: str = typer.Argument(..., help="JSON file containing problem data")
):
    """Import problem data from a JSON file."""
    init_app()
    
    try:
        with open(input_file, 'r') as f:
            import_data = json.load(f)
    except Exception as e:
        console.print(f"Error reading file: {e}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Extract problem data
        problem = import_data.get("problem", {})
        
        # Insert problem
        cursor.execute(
            "INSERT INTO problems (title, description, created_date, status) VALUES (?, ?, ?, ?)",
            (problem.get("title"), problem.get("description"), problem.get("created_date"), problem.get("status", "active"))
        )
        new_problem_id = cursor.lastrowid
        
        # Insert KPIs
        for kpi in import_data.get("kpis", []):
            cursor.execute(
                "INSERT INTO kpis (problem_id, description, target_value, current_value) VALUES (?, ?, ?, ?)",
                (new_problem_id, kpi.get("description"), kpi.get("target_value"), kpi.get("current_value", 0))
            )
        
        # Insert action steps
        for step in import_data.get("action_steps", []):
            cursor.execute(
                "INSERT INTO action_steps (problem_id, description, status) VALUES (?, ?, ?)",
                (new_problem_id, step.get("description"), step.get("status", "pending"))
            )
        
        # Insert progress logs
        for log in import_data.get("progress_logs", []):
            # Find the new KPI ID based on description
            cursor.execute(
                "SELECT id FROM kpis WHERE problem_id = ? AND description = ?",
                (new_problem_id, next((k["description"] for k in import_data.get("kpis", []) if k["id"] == log.get("kpi_id")), ""))
            )
            kpi_result = cursor.fetchone()
            
            if kpi_result:
                new_kpi_id = kpi_result[0]
                cursor.execute(
                    "INSERT INTO progress_logs (problem_id, kpi_id, value, timestamp) VALUES (?, ?, ?, ?)",
                    (new_problem_id, new_kpi_id, log.get("value"), log.get("timestamp"))
                )
        
        conn.commit()
        console.print(f"Problem imported successfully with ID: [bold]{new_problem_id}[/bold]")
        
        # Display the imported problem
        display_problem(new_problem_id)
        
    except Exception as e:
        conn.rollback()
        console.print(f"Error importing problem: {e}")
    finally:
        conn.close()

@app.command()
def version():
    """Display the version of Empathic Problem Solver."""
    console.print("Empathic Problem Solver CLI v1.1.0")
    console.print("Powered by Claude Haiku AI")
    console.print("Created by Your Name")
    console.print("Copyright (c) 2025")

@app.command()
def analyze(
    problem_id: int = typer.Argument(..., help="ID of the problem to analyze"),
):
    """Get an in-depth AI analysis of your problem and progress."""
    init_app()
    
    config = load_config()
    if not config.get("api_key_set", False):
        console.print("[yellow]Claude API key is not set. Please run 'empathic-solver configure' to set it up.[/yellow]")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get problem details
    cursor.execute("SELECT title, description FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()
    
    if not problem:
        console.print(f"Problem with ID {problem_id} not found.")
        return
    
    title, description = problem
    
    # Get KPIs
    cursor.execute("SELECT id, description, target_value, current_value FROM kpis WHERE problem_id = ?", 
                  (problem_id,))
    kpis = cursor.fetchall()
    
    # Get action steps
    cursor.execute("SELECT id, description, status FROM action_steps WHERE problem_id = ?", 
                  (problem_id,))
    action_steps = cursor.fetchall()
    
    conn.close()
    
    # Prepare data for analysis
    kpi_data = []
    for kpi_id, description, target, current in kpis:
        trend_data = calculate_moving_average(problem_id, kpi_id)
        progress_pct = (current / target * 100) if target > 0 else 0
        
        kpi_data.append({
            "description": description,
            "target_value": target,
            "current_value": current,
            "progress_percentage": progress_pct,
            "trend": trend_data["trend"]
        })
    
    # Prepare action steps data
    steps_data = []
    for step_id, description, status in action_steps:
        steps_data.append({
            "description": description,
            "status": status
        })
    
    # Create the prompt for Claude
    prompt = f"""
    You are an expert problem-solving coach. Analyze this problem and progress data to provide an in-depth analysis:
    
    Problem: "{title}: {description}"
    
    KPI Progress:
    {json.dumps(kpi_data, indent=2)}
    
    Action Steps:
    {json.dumps(steps_data, indent=2)}
    
    Please provide:
    
    1. A concise assessment of overall progress
    2. Specific strengths in the current approach
    3. Key areas that need attention
    4. Strategic recommendations for next steps
    5. Long-term considerations for sustained success
    
    Your analysis should be thoughtful, specific to this situation, and actionable.
    """
    
    console.print(Panel(f"[bold]{title}[/bold]\n\n{description}", 
                        title="Problem Being Analyzed", 
                        border_style="green"))
    
    console.print("\n[bold]Generating in-depth analysis...[/bold]")
    time.sleep(2)  # Simple delay instead of progress bar
    analysis = call_claude_api(prompt, max_tokens=1000)
    
    if analysis:
        console.print(Panel(analysis, title="AI Analysis", border_style="cyan"))
    else:
        console.print("[red]Failed to generate analysis. Please check your API key and try again.[/red]")

if __name__ == "__main__":
    app()