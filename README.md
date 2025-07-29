
# 🤖 botBrigade

## Product Requirements & Documentation

### Overview
botBrigade is a lightweight, local-only web application for scheduling, running, and managing shell commands or scripts on a user’s machine. It is designed for personal automation, with a focus on privacy (no cloud, no external database), simplicity, and transparency. All data is stored locally in a SQLite database (`tasks.db`) and log files. The app provides a web interface for managing tasks, viewing logs, and monitoring scheduled executions.

---

## Table of Contents
1. [Features](#features)
2. [Architecture](#architecture)
3. [Data Model](#data-model)
4. [User Interface](#user-interface)
5. [Setup & Installation](#setup--installation)
6. [Usage Guide](#usage-guide)
7. [Technical Details](#technical-details)
8. [Extensibility](#extensibility)
9. [Security Considerations](#security-considerations)
10. [License](#license)

---

## Features

- **Task Scheduling**
  - Add, edit, delete, enable, or disable scheduled tasks
  - One-time, interval, or recurring (weekday/time range) scheduling
  - Manual run of any task
  - Per-task log viewing
- **Web Interface**
  - Dashboard for task overview and management
  - Task creation/editing form
  - Log viewer for each task
- **Storage**
  - All task data stored in a local SQLite database (`tasks.db`)
  - Logs stored in `logs/` (one file per task)
- **Execution**
  - Tasks run as shell commands/scripts using the user’s permissions
  - Output and errors are captured and logged
- **No Cloud, No Database**
  - All data is local; no external dependencies except Python packages

---

## Architecture

**Tech Stack:**
- Python 3
- Flask (web server & UI)
- APScheduler (task scheduling)
// ...existing code...
// Removed CSV (task storage) as tasks are now stored in SQLite
- Subprocess (command execution)
- Bootstrap (UI styling)

**File Structure:**
- `app.py` — Main Flask app, routes, and web server
- `scheduler.py` — Task scheduling logic (APScheduler integration)
- `storage.py` — SQLite storage and data access
- `tasks.db` — SQLite database for task definitions (name, command, schedule, status, etc.)
- `logs/` — Per-task log files
- `templates/` — HTML templates (dashboard, forms, logs)
- `requirements.txt` — Python dependencies

**Data Flow:**
1. User interacts with the web UI (Flask routes)
2. Task CRUD operations update the SQLite database (`tasks.db`) via `storage.py`
3. Scheduler (`scheduler.py`) loads tasks and manages APScheduler jobs
4. When a task runs, output/errors are written to `logs/<task_name>.log`
5. UI displays logs and task status

---

## Data Model

**tasks.db** (SQLite table: `tasks`):
- `name` (TEXT, primary key)
- `command` (TEXT, shell command/script to run)
- `schedule` (TEXT, date/time, interval, or recurring pattern)
- `status` (TEXT, enabled/disabled)
- `last_run` (TEXT, timestamp)
- `order` (INTEGER, for custom ordering)

**logs/**
- Each task has a log file named after the task or its ID
- Log files contain timestamped output and error messages

---

## User Interface

**Pages:**
- **Dashboard** (`/`): List all tasks, status, next run, actions (edit, delete, enable/disable, run, view logs)
- **Add/Edit Task** (`/add`, `/edit/<id>`): Form for task details (name, command, schedule, enabled)
- **Logs** (`/logs/<id>`): View output/error logs for a specific task
- **Scheduled** (`/scheduled`): List of upcoming scheduled runs

**UI Elements:**
- Bootstrap-based tables, forms, and buttons
- Status indicators (enabled/disabled, last run, next run)
- Log viewer with scrollable output

---

## Setup & Installation

1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd <repo-directory>
   ```
2. **Create a virtual environment (recommended):**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Run the app:**
   ```sh
   python app.py
   ```
5. **Open your browser:**
   Visit [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Stopping the App:**
- If running in terminal: Press <kbd>Ctrl</kbd>+<kbd>C</kbd>
- If running as a background service (macOS launchd):
  ```sh
  launchctl unload ~/Library/LaunchAgents/com.yourname.taskscheduler.plist
  ```

---

## Usage Guide

### Task Scheduling Syntax
- **One-time:** `YYYY-MM-DD HH:MM` (e.g., `2025-07-28 14:00`)
- **Interval:** `interval:5m`, `interval:2h`, `interval:1d` (minutes, hours, days)
- **Weekday Recurring:** `weekdays:09:00-17:00:30m` (run every 30m between 9am-5pm on weekdays)

### Task Management
- **Add Task:** Click "Add New Task" and fill in the form
- **Edit/Delete/Enable/Disable:** Use dashboard buttons
- **Manual Run:** Click "Run" to execute a task immediately
- **View Logs:** Click "Logs" to see output/errors for each task

### Logs
- Logs are stored in `logs/` directory, one file per task
- Each log entry is timestamped and includes stdout/stderr

---

## Technical Details

- **Flask App (`app.py`):**
  - Handles all web routes and UI rendering
  - Communicates with `storage.py` and `scheduler.py`
- **Scheduler (`scheduler.py`):**
  - Uses APScheduler to manage job timing and execution
  - Loads tasks from the SQLite database, schedules jobs, handles run/stop/enable/disable
- **Storage (`storage.py`):**
  - Reads/writes all task data in `tasks.db` (SQLite)
  - Ensures atomic updates to prevent data loss
- **Templates (`templates/`):**
  - Jinja2 HTML templates for dashboard, forms, logs, etc.
- **Logs:**
  - Each task’s output/error is appended to its log file in `logs/`
- **Security:**
  - All commands/scripts run with the permissions of the user running the app
  - No remote access or cloud storage

---

## Extensibility

- **Add support for more schedule types** (e.g., cron expressions)
- **Integrate notifications** (e.g., email, Slack)
- **User authentication** (for multi-user or remote scenarios)
- **Import/export tasks** (optional: CSV, JSON)
- **API endpoints** for automation

---

## Security Considerations

- Only run trusted commands/scripts
- App is intended for local, personal use only
- All logs and data are stored locally
- No network/cloud access by default

---

## License

MIT