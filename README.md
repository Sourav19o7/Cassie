# Empathic Problem Solver CLI

A command-line tool for macOS that helps you solve problems through empathetic understanding, structured KPI setting, progress tracking, and actionable recommendations - now powered by Claude Haiku AI!

## Features

- **AI-Powered Empathetic Responses**: Receive personalized understanding of your challenges via Claude Haiku
- **Intelligent KPI Generation**: Get relevant metrics tailored to your specific problem
- **Smart Action Planning**: Receive context-aware step-by-step plans to achieve your goals
- **Progress Tracking**: Monitor your progress with moving averages and trends
- **AI-Driven Recommendations**: Get data-driven suggestions that adapt to your progress
- **In-Depth Analysis**: Request detailed problem analysis from Claude Haiku
- **Periodic Reminders**: Receive scheduled notifications to update your KPIs and track progress

## Installation

### Option 1: One-line Installation (Recommended)

```bash
curl -L https://your-private-server/distribute.sh | bash
```

This will download the latest version of Empathic Problem Solver CLI and install it on your system.

### Option 2: Manual Installation

1. Download the installer script:
```bash
curl -L https://your-private-server/distribute.sh -o install-empathic-solver.sh
```

2. Make it executable:
```bash
chmod +x install-empathic-solver.sh
```

3. Run the installer:
```bash
./install-empathic-solver.sh
```

### Option 3: From Source Code

If you have access to the source code:

1. Ensure you have Python 3.8+ installed
2. Navigate to the source directory
3. Run the installation script:
```bash
bash install.sh
```

## First-Time Setup

After installation, set up your Claude API key:

```bash
empathic-solver configure
```

You'll be prompted to enter your API key and select your preferences.

## Usage

### Creating a new problem

```bash
empathic-solver new
```

You'll be prompted to enter a title and description for your problem. The tool will then:
1. Provide an AI-generated empathetic response
2. Generate relevant KPIs tailored to your problem
3. Suggest specific action steps
4. Show initial recommendations
5. Optionally set up reminders for KPI updates

### Listing your active problems

```bash
empathic-solver list
```

This will display all your active problems with their IDs.

### Viewing a problem's details

```bash
empathic-solver view 1
```

Replace `1` with the ID of the problem you want to view.

### Getting an in-depth AI analysis

```bash
empathic-solver analyze 1
```

This will provide a comprehensive AI analysis of your problem and progress.

### Updating a KPI value

```bash
empathic-solver update-kpi 3 5.0
```

This updates KPI with ID 3 to a new value of 5.0.

### Marking an action step as completed

```bash
empathic-solver complete-step 2
```

This marks the action step with ID 2 as completed.

### Setting up reminders

```bash
empathic-solver reminder-set 1 --frequency daily --time 09:00
```

This sets a daily reminder at 9:00 AM to update KPIs for problem with ID 1.

For weekly reminders, specify the days:
```bash
empathic-solver reminder-set 1 --frequency weekly --time 10:00 --days "Monday,Wednesday,Friday"
```

For monthly reminders, specify the day of the month:
```bash
empathic-solver reminder-set 1 --frequency monthly --time 15:30 --day-of-month 1
```

### Managing reminders

```bash
empathic-solver reminders-list         # List all reminders
empathic-solver reminder-disable 1     # Temporarily disable a reminder
empathic-solver reminder-enable 1      # Re-enable a disabled reminder
empathic-solver reminder-delete 1      # Remove a reminder completely
empathic-solver reminder-test 1        # Test the notification for a reminder
```

### Adding new action steps

```bash
empathic-solver add-step 1
# You'll be prompted to enter the step description
```

### Adding new KPIs

```bash
empathic-solver add-kpi 1
# You'll be prompted to enter the KPI description and target value
```

### Marking a problem as completed

```bash
empathic-solver complete 1
```

This marks the entire problem with ID 1 as completed.

### Reactivating a completed problem

```bash
empathic-solver reactivate 1
```

This reactivates a previously completed problem.

### Exporting problem data

```bash
empathic-solver export 1 --output-file=my_problem.json
```

This exports all data for problem with ID 1 to the specified file.

### Importing problem data

```bash
empathic-solver import-problem my_problem.json
```

This imports problem data from a previously exported file.

### Updating your Claude AI configuration

```bash
empathic-solver configure
```

This allows you to update your API key and Claude model preferences.

## Example Workflow

1. Configure the tool with your Claude API key:
   ```bash
   empathic-solver configure
   # Enter your Claude API key when prompted
   ```

2. Create a new problem:
   ```bash
   empathic-solver new
   # Enter title: "Complete website redesign"
   # Enter description: "I need to redesign our company website but I'm feeling overwhelmed by the scope of the project."
   # Set up a reminder when prompted
   ```

3. View the AI-generated KPIs and action steps:
   ```bash
   empathic-solver view 1
   ```

4. As you make progress, update your KPI values:
   ```bash
   empathic-solver update-kpi 1 25.0
   ```

5. Mark steps as completed:
   ```bash
   empathic-solver complete-step 1
   ```

6. Get an in-depth AI analysis of your progress:
   ```bash
   empathic-solver analyze 1
   ```

7. When finished, mark the problem as completed:
   ```bash
   empathic-solver complete 1
   ```

## Reminder System

The reminder system helps you stay on track with your problem-solving progress:

- Notifications appear on your desktop when it's time to update your KPIs
- Supports daily, weekly, and monthly schedules
- You can customize which days of the week or day of the month
- Reminders can be temporarily disabled or permanently deleted
- Notifications adapt to your operating system (macOS, Windows, or Linux)

When creating a new problem, you'll be prompted to set up a reminder automatically. You can also set them up later using the `reminder-set` command.

## Data Storage

All your problem data is stored locally in a SQLite database at `~/.empathic_solver/problems.db`. Your Claude API key is securely stored in your system's keychain.

## Claude AI Integration

This tool uses Claude Haiku to provide:
- Empathetic understanding of your problems
- Intelligent KPI generation based on problem context
- Personalized action steps
- Smart recommendations that adapt to your progress
- In-depth analysis of your situation

Your Claude API key is required to unlock these AI-powered features. Without an API key, the tool will fall back to rule-based responses.

## Troubleshooting

If you encounter any issues:

1. Make sure you have Python 3.8 or later installed
2. Check that the executable is in your PATH
3. Verify your Claude API key is working correctly
4. Try running `empathic-solver configure` to update your settings
5. Check your internet connection for AI-powered features

### Reminder Issues

If reminders aren't working:

1. Ensure your system allows notifications from Python applications
2. On macOS, check System Preferences > Notifications
3. On Windows, check Settings > System > Notifications & actions
4. Try running `empathic-solver reminder-test 1` to check notifications
5. Make sure the application is running when reminders are scheduled
6. If using a virtual environment, ensure it's activated

## License

Proprietary software. All rights reserved.