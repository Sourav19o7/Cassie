"""
Reminders module for Empathic Problem Solver CLI
Provides functionality for scheduling and managing periodic reminders
"""

import os
import json
import sqlite3
import datetime
import time
import threading
import schedule
from pathlib import Path
from rich.console import Console
from typing import List, Dict, Optional
import subprocess
import platform
import sys

# Access application directories from empathic_solver module
APP_DIR = Path.home() / ".empathic_solver"
DB_PATH = APP_DIR / "problems.db"
REMINDERS_PATH = APP_DIR / "reminders.json"
console = Console()

class Reminder:
    """Class representing a reminder for KPI updates"""
    def __init__(self, 
                 problem_id: int, 
                 frequency: str, 
                 time: str, 
                 weekdays: Optional[List[str]] = None,
                 day_of_month: Optional[int] = None,
                 enabled: bool = True,
                 last_triggered: Optional[str] = None):
        self.problem_id = problem_id
        self.frequency = frequency  # 'daily', 'weekly', 'monthly', 'custom'
        self.time = time  # Format: "HH:MM"
        self.weekdays = weekdays  # List of weekdays for weekly reminders
        self.day_of_month = day_of_month  # Day of month for monthly reminders
        self.enabled = enabled
        self.last_triggered = last_triggered
    
    def to_dict(self) -> Dict:
        """Convert reminder to dictionary for JSON serialization"""
        return {
            "problem_id": self.problem_id,
            "frequency": self.frequency,
            "time": self.time,
            "weekdays": self.weekdays,
            "day_of_month": self.day_of_month,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Reminder':
        """Create a Reminder object from dictionary data"""
        return cls(
            problem_id=data.get("problem_id"),
            frequency=data.get("frequency"),
            time=data.get("time"),
            weekdays=data.get("weekdays"),
            day_of_month=data.get("day_of_month"),
            enabled=data.get("enabled", True),
            last_triggered=data.get("last_triggered")
        )

class ReminderManager:
    """Manager for handling reminder operations"""
    def __init__(self):
        self.reminders = []
        self.scheduler_thread = None
        self.running = False
        self.load_reminders()
    
    def load_reminders(self) -> None:
        """Load reminders from JSON file"""
        if not REMINDERS_PATH.exists():
            self.reminders = []
            self.save_reminders()
            return
        
        try:
            with open(REMINDERS_PATH, 'r') as f:
                data = json.load(f)
                self.reminders = [Reminder.from_dict(r) for r in data]
        except Exception as e:
            console.print(f"[yellow]Error loading reminders: {e}[/yellow]")
            self.reminders = []
    
    def save_reminders(self) -> None:
        """Save reminders to JSON file"""
        try:
            with open(REMINDERS_PATH, 'w') as f:
                data = [r.to_dict() for r in self.reminders]
                json.dump(data, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving reminders: {e}[/red]")
    
    def add_reminder(self, reminder: Reminder) -> None:
        """Add a new reminder"""
        self.reminders.append(reminder)
        self.save_reminders()
        self.schedule_reminder(reminder)
    
    def update_reminder(self, problem_id: int, reminder_data: Dict) -> bool:
        """Update an existing reminder for a problem"""
        for i, r in enumerate(self.reminders):
            if r.problem_id == problem_id:
                # Update properties
                for key, value in reminder_data.items():
                    if hasattr(r, key):
                        setattr(r, key, value)
                
                self.save_reminders()
                self.reschedule_reminders()
                return True
        return False
    
    def delete_reminder(self, problem_id: int) -> bool:
        """Delete a reminder for a problem"""
        for i, r in enumerate(self.reminders):
            if r.problem_id == problem_id:
                del self.reminders[i]
                self.save_reminders()
                self.reschedule_reminders()
                return True
        return False
    
    def get_reminder(self, problem_id: int) -> Optional[Reminder]:
        """Get a reminder by problem ID"""
        for r in self.reminders:
            if r.problem_id == problem_id:
                return r
        return None
    
    def list_reminders(self) -> List[Dict]:
        """Get all reminders with problem titles"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        result = []
        
        for reminder in self.reminders:
            # Get problem title
            cursor.execute("SELECT title FROM problems WHERE id = ?", (reminder.problem_id,))
            row = cursor.fetchone()
            title = row[0] if row else "Unknown problem"
            
            result.append({
                "problem_id": reminder.problem_id,
                "title": title,
                "frequency": reminder.frequency,
                "time": reminder.time,
                "weekdays": reminder.weekdays,
                "day_of_month": reminder.day_of_month,
                "enabled": reminder.enabled,
                "last_triggered": reminder.last_triggered
            })
        
        conn.close()
        return result
    
    def trigger_reminder(self, problem_id: int) -> None:
        """Trigger a reminder notification for a problem"""
        # Update last triggered time
        for r in self.reminders:
            if r.problem_id == problem_id:
                r.last_triggered = datetime.datetime.now().isoformat()
        
        self.save_reminders()
        
        # Get problem details for notification
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM problems WHERE id = ?", (problem_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return
        
        title = row[0]
        conn.close()
        
        # Send notification based on platform
        self.send_notification(
            title="Empathic Problem Solver Reminder",
            message=f"Time to update KPIs for: {title}",
            problem_id=problem_id
        )
    
    def send_notification(self, title: str, message: str, problem_id: int) -> None:
        """Send a desktop notification based on the platform"""
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                # Using osascript for macOS notifications
                script = f'''
                display notification "{message}" with title "{title}" subtitle "Problem #{problem_id}"
                '''
                subprocess.run(["osascript", "-e", script], check=True)
                
            elif system == "Linux":
                # Using notify-send for Linux
                subprocess.run(["notify-send", title, message], check=True)
                
            elif system == "Windows":
                # Using PowerShell for Windows 10+
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

                $app_id = 'EmpathicProblemSolver'
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $template = @"
                <toast>
                    <visual>
                        <binding template="ToastText02">
                            <text id="1">{title}</text>
                            <text id="2">{message}</text>
                        </binding>
                    </visual>
                </toast>
                "@
                $xml.LoadXml($template)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app_id).Show($xml)
                '''
                subprocess.run(["powershell", "-Command", ps_script], check=True)
            
            # Also print to console in case notification fails or for terminal-only environments
            console.print(f"[bold blue]REMINDER:[/bold blue] {message}")
            
        except Exception as e:
            console.print(f"[yellow]Notification failed: {e}[/yellow]")
            console.print(f"[bold blue]REMINDER:[/bold blue] {message}")
    
    def schedule_reminder(self, reminder: Reminder) -> None:
        """Schedule a single reminder with the scheduler"""
        if not reminder.enabled:
            return
        
        problem_id = reminder.problem_id
        time_str = reminder.time
        
        # Define the job function
        def job():
            self.trigger_reminder(problem_id)
        
        # Schedule based on frequency
        if reminder.frequency == 'daily':
            schedule.every().day.at(time_str).do(job)
            
        elif reminder.frequency == 'weekly' and reminder.weekdays:
            for day in reminder.weekdays:
                if day.lower() == 'monday':
                    schedule.every().monday.at(time_str).do(job)
                elif day.lower() == 'tuesday':
                    schedule.every().tuesday.at(time_str).do(job)
                elif day.lower() == 'wednesday':
                    schedule.every().wednesday.at(time_str).do(job)
                elif day.lower() == 'thursday':
                    schedule.every().thursday.at(time_str).do(job)
                elif day.lower() == 'friday':
                    schedule.every().friday.at(time_str).do(job)
                elif day.lower() == 'saturday':
                    schedule.every().saturday.at(time_str).do(job)
                elif day.lower() == 'sunday':
                    schedule.every().sunday.at(time_str).do(job)
                    
        elif reminder.frequency == 'monthly' and reminder.day_of_month:
            # Schedule for a specific day of month
            schedule.every().month.at(f"{reminder.day_of_month:02d} {time_str}").do(job)
    
    def reschedule_reminders(self) -> None:
        """Clear all scheduled jobs and reschedule from reminders list"""
        schedule.clear()
        for reminder in self.reminders:
            if reminder.enabled:
                self.schedule_reminder(reminder)
    
    def start_scheduler(self) -> None:
        """Start the scheduler thread if not running"""
        if self.running:
            return
        
        self.running = True
        
        def run_scheduler():
            self.reschedule_reminders()
            while self.running:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
    
    def stop_scheduler(self) -> None:
        """Stop the scheduler thread"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)
            self.scheduler_thread = None

# Global instance for access from app
reminder_manager = ReminderManager()

def init_reminders():
    """Initialize the reminder system"""
    reminder_manager.start_scheduler()
    return reminder_manager

def get_reminder_manager():
    """Get the global reminder manager instance"""
    return reminder_manager

def check_due_reminders():
    """Check for any reminders that should have triggered while app was closed"""
    now = datetime.datetime.now()
    today = now.date()
    
    for reminder in reminder_manager.reminders:
        if not reminder.enabled or not reminder.last_triggered:
            continue
        
        last_time = datetime.datetime.fromisoformat(reminder.last_triggered)
        last_date = last_time.date()
        
        # Calculate next expected trigger time based on frequency
        next_trigger = None
        
        if reminder.frequency == 'daily':
            # Next trigger should be last_date + 1 day
            next_trigger = datetime.datetime.combine(last_date + datetime.timedelta(days=1), 
                                                   datetime.datetime.strptime(reminder.time, "%H:%M").time())
            
        elif reminder.frequency == 'weekly' and reminder.weekdays:
            # Convert day names to integers (0=Monday, 6=Sunday)
            day_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 
                       'friday': 4, 'saturday': 5, 'sunday': 6}
            current_weekday = last_date.weekday()
            
            # Find next weekday in the reminder list
            weekday_ints = [day_map[day.lower()] for day in reminder.weekdays if day.lower() in day_map]
            if weekday_ints:
                # Sort weekdays and find the next one after the current weekday
                weekday_ints.sort()
                next_weekday = None
                
                for day in weekday_ints:
                    if day > current_weekday:
                        next_weekday = day
                        break
                
                # If we didn't find a later day this week, use the first day next week
                if next_weekday is None:
                    next_weekday = weekday_ints[0]
                    days_ahead = 7 - current_weekday + next_weekday
                else:
                    days_ahead = next_weekday - current_weekday
                
                next_trigger = datetime.datetime.combine(last_date + datetime.timedelta(days=days_ahead),
                                                       datetime.datetime.strptime(reminder.time, "%H:%M").time())
                
        elif reminder.frequency == 'monthly' and reminder.day_of_month:
            # Move to next month, same day
            if last_date.month == 12:
                next_month = 1
                next_year = last_date.year + 1
            else:
                next_month = last_date.month + 1
                next_year = last_date.year
            
            # Ensure valid day for month
            day = min(reminder.day_of_month, 28)  # Safety for February
            
            next_trigger = datetime.datetime.combine(
                datetime.date(next_year, next_month, day),
                datetime.datetime.strptime(reminder.time, "%H:%M").time()
            )
        
        # If next trigger time is in the past, trigger the reminder
        if next_trigger and next_trigger < now:
            reminder_manager.trigger_reminder(reminder.problem_id)

def format_reminder_schedule(reminder: Reminder) -> str:
    """Format a reminder's schedule for display"""
    if reminder.frequency == 'daily':
        return f"Daily at {reminder.time}"
    elif reminder.frequency == 'weekly' and reminder.weekdays:
        days = ", ".join(reminder.weekdays)
        return f"Weekly on {days} at {reminder.time}"
    elif reminder.frequency == 'monthly' and reminder.day_of_month:
        return f"Monthly on day {reminder.day_of_month} at {reminder.time}"
    else:
        return f"Custom schedule at {reminder.time}"

# Testing function when run directly
if __name__ == "__main__":
    # Initialize reminders
    rm = init_reminders()
    
    # Test reminder (will only work if database exists with this problem ID)
    test_reminder = Reminder(
        problem_id=1,
        frequency="daily",
        time="14:30",
        enabled=True
    )
    
    rm.add_reminder(test_reminder)
    print("Added test reminder. Press Ctrl+C to exit.")
    
    try:
        # Run indefinitely for testing
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping scheduler...")
        rm.stop_scheduler()
        print("Done.")