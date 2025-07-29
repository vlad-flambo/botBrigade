from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import storage
import subprocess
from datetime import datetime
import os
import scheduler
import sys
import threading
import signal
import io
import csv  # Used only for optional import/export, not for main storage

# Only import rumps if on macOS
try:
    import rumps
    MACOS = True
except ImportError:
    MACOS = False

app = Flask(__name__)
app.secret_key = 'replace-this-with-a-unique-secret-key'

LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

def parse_log_entries(log_content):
    entries = []
    for entry in log_content.split('--- '):
        entry = entry.strip()
        if not entry:
            continue
        header_end = entry.find('\n')
        if header_end == -1:
            continue
        header = entry[:header_end].strip()
        body = entry[header_end+1:].strip()
        if ' run at ' in header:
            _type, _time = header.split(' run at ', 1)
            entries.append({'type': _type.strip(), 'time': _time.strip(), 'body': body})
    return sorted(entries, key=lambda e: e['time'], reverse=True)

@app.route('/')
def dashboard():
    tasks = storage.load_tasks()
    error = request.args.get('error')
    return render_template('dashboard.html', tasks=tasks, error=error)

@app.route('/tasks', methods=['GET', 'POST'])
def manage_tasks():
    tasks = storage.load_tasks()
    edit_name = request.args.get('edit')
    delete_name = request.args.get('delete')
    task = None
    error = None

    # Handle delete
    if request.method == 'POST' and delete_name:
        storage.delete_task(delete_name)
        scheduler.remove_task_schedule(delete_name)
        flash(f"Task '{delete_name}' deleted.", 'success')
        return redirect(url_for('dashboard'))

    # Handle add/edit
    if request.method == 'POST' and not delete_name:
        form = request.form
        new_task = {
            'name': form['name'],
            'command': form['command'],
            'schedule': form['schedule'],
            'status': form['status'],
            'last_run': ''
        }
        if edit_name:
            if edit_name != new_task['name']:
                # Renaming: check if new name exists
                if any(t['name'] == new_task['name'] for t in tasks):
                    error = f"Task name '{new_task['name']}' already exists."
                    flash(error, 'danger')
                    return render_template('task_form.html', task=new_task, error=error)
                # Rename in DB
                storage.rename_task(edit_name, new_task['name'])
                # Rename log file if exists
                import os
                old_log = os.path.join('logs', f"{edit_name}.log")
                new_log = os.path.join('logs', f"{new_task['name']}.log")
                if os.path.exists(old_log):
                    os.rename(old_log, new_log)
                # Remove old schedule, add new
                scheduler.remove_task_schedule(edit_name)
                storage.edit_task(new_task['name'], new_task)
                scheduler.add_or_update_task_schedule(new_task)
            else:
                storage.edit_task(edit_name, new_task)
                scheduler.add_or_update_task_schedule(new_task)
            flash(f"Task '{edit_name}' updated.", 'success')
        else:
            try:
                storage.add_task(new_task)
                scheduler.add_or_update_task_schedule(new_task)
                flash(f"Task '{new_task['name']}' added.", 'success')
            except ValueError as e:
                error = str(e)
                flash(error, 'danger')
                return render_template('task_form.html', task=new_task, error=error)
        return redirect(url_for('dashboard'))

    # Pre-fill form for editing
    if edit_name:
        for t in tasks:
            if t['name'] == edit_name:
                task = t
                break
    return render_template('task_form.html', task=task, error=error)

@app.route('/tasks/reorder', methods=['POST'])
def reorder_tasks():
    data = request.get_json()
    task_names = data.get('task_names', [])
    if not isinstance(task_names, list):
        return jsonify({'success': False, 'error': 'Invalid data'}), 400
    storage.set_task_order(task_names)
    return jsonify({'success': True})

@app.route('/tasks/delete/<task_name>', methods=['POST'])
def delete_task(task_name):
    storage.delete_task(task_name)
    scheduler.remove_task_schedule(task_name)
    flash(f"Task '{task_name}' deleted.", 'success')
    return redirect(url_for('dashboard'))

@app.route('/run/<task_name>', methods=['POST'])
def run_task(task_name):
    tasks = storage.load_tasks()
    task = next((t for t in tasks if t['name'] == task_name), None)
    if not task:
        return redirect(url_for('dashboard'))
    # Run the command
    try:
        result = subprocess.run(task['command'], shell=True, capture_output=True, text=True, timeout=3600)
        output = result.stdout
        error = result.stderr
        returncode = result.returncode
    except Exception as e:
        output = ''
        error = str(e)
        returncode = -1
    # Log the result
    log_path = os.path.join(LOGS_DIR, f"{task_name}.log")
    with open(log_path, 'a') as f:
        f.write(f"\n--- One-off run at {datetime.now().isoformat()} ---\n")
        f.write(f"Command: {task['command']}\n")
        f.write(f"Return code: {returncode}\n")
        if output:
            f.write(f"Output:\n{output}\n")
        if error:
            f.write(f"Error:\n{error}\n")
    # Update last_run in the database
    task['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    storage.edit_task(task_name, task)
    return redirect(url_for('dashboard'))

@app.route('/logs/<task_name>')
def view_logs(task_name):
    log_path = os.path.join(LOGS_DIR, f"{task_name}.log")
    if os.path.exists(log_path):
        with open(log_path) as f:
            log_content = f.read()
        log_entries = parse_log_entries(log_content)
    else:
        log_entries = []
    return render_template('logs.html', task_name=task_name, log_entries=log_entries)

@app.route('/toggle/<task_name>', methods=['POST'])
def toggle_task(task_name):
    tasks = storage.load_tasks()
    task = next((t for t in tasks if t['name'] == task_name), None)
    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('dashboard'))
    # Toggle status
    task['status'] = 'disabled' if task['status'] == 'enabled' else 'enabled'
    storage.edit_task(task_name, task)
    scheduler.add_or_update_task_schedule(task)
    flash(f"Task '{task_name}' {'enabled' if task['status'] == 'enabled' else 'disabled'}.", 'info')
    return redirect(url_for('dashboard'))

@app.route('/scheduled')
def scheduled_jobs():
    jobs = scheduler.scheduler.get_jobs()
    return render_template('scheduled.html', jobs=jobs)

@app.route('/scheduled/disable_all', methods=['POST'])
def scheduled_disable_all():
    scheduler.scheduler.remove_all_jobs()
    flash('All scheduled tasks have been disabled.', 'info')
    return redirect(url_for('scheduled_jobs'))

@app.route('/export_jobs')
def export_jobs():
    tasks = storage.load_tasks()
    output = io.StringIO()
    # Export tasks to CSV (optional feature, not main storage)
    writer = csv.DictWriter(output, fieldnames=storage.FIELDNAMES)
    writer.writeheader()
    for task in tasks:
        writer.writerow(task)
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',  # CSV export is optional
        as_attachment=True,
        download_name='jobs_export.csv'  # CSV export is optional
    )

@app.route('/import_jobs', methods=['POST'])
def import_jobs():
    # Import tasks from CSV (optional feature, not main storage)
    if 'csv_file' not in request.files:
        flash('No file part in the request.', 'danger')
        return redirect(url_for('dashboard'))
    file = request.files['csv_file']
    if file.filename == '':
        flash('No selected file.', 'danger')
        return redirect(url_for('dashboard'))
    try:
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)  # CSV import is optional
        count = 0
        for row in reader:
            # Only use known fields
            task = {k: row.get(k, '') for k in storage.FIELDNAMES}
            if not task['name']:
                continue
            try:
                storage.add_task(task)
                count += 1
            except ValueError:
                # If task exists, update it
                storage.edit_task(task['name'], task)
                count += 1
        flash(f'Imported {count} tasks from CSV (optional feature).', 'success')
    except Exception as e:
        flash(f'Failed to import tasks: {e}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/bulk_action', methods=['POST'])
def bulk_action():
    action = request.form.get('action')
    selected = request.form.getlist('selected_tasks')
    if not selected:
        flash('No tasks selected.', 'danger')
        return redirect(url_for('dashboard'))
    if action == 'edit':
        if len(selected) != 1:
            flash('Please select exactly one task to edit.', 'danger')
            return redirect(url_for('dashboard'))
        return redirect(url_for('manage_tasks', edit=selected[0]))
    elif action == 'logs':
        if len(selected) != 1:
            flash('Please select exactly one task to view logs.', 'danger')
            return redirect(url_for('dashboard'))
        return redirect(url_for('view_logs', task_name=selected[0]))
    elif action == 'run':
        count = 0
        for name in selected:
            tasks = storage.load_tasks()
            task = next((t for t in tasks if t['name'] == name), None)
            if not task:
                continue
            try:
                result = subprocess.run(task['command'], shell=True, capture_output=True, text=True, timeout=3600)
                output = result.stdout
                error = result.stderr
                returncode = result.returncode
            except Exception as e:
                output = ''
                error = str(e)
                returncode = -1
            log_path = os.path.join(LOGS_DIR, f"{name}.log")
            with open(log_path, 'a') as f:
                f.write(f"\n--- One-off run at {datetime.now().isoformat()} ---\n")
                f.write(f"Command: {task['command']}\n")
                f.write(f"Return code: {returncode}\n")
                if output:
                    f.write(f"Output:\n{output}\n")
                if error:
                    f.write(f"Error:\n{error}\n")
            task['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            storage.edit_task(name, task)
            count += 1
        flash(f'Ran {count} selected tasks.', 'success')
        return redirect(url_for('dashboard'))
    elif action == 'delete':
        count = 0
        for name in selected:
            storage.delete_task(name)
            scheduler.remove_task_schedule(name)
            count += 1
        flash(f'Deleted {count} selected tasks.', 'success')
        return redirect(url_for('dashboard'))
    elif action == 'toggle':
        count = 0
        for name in selected:
            tasks = storage.load_tasks()
            task = next((t for t in tasks if t['name'] == name), None)
            if not task:
                continue
            task['status'] = 'disabled' if task['status'] == 'enabled' else 'enabled'
            storage.edit_task(name, task)
            scheduler.add_or_update_task_schedule(task)
            count += 1
        flash(f'Toggled enabled/disabled for {count} selected tasks.', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Unknown action.', 'danger')
        return redirect(url_for('dashboard'))

# Function for APScheduler to call
# This is separate from the Flask route and does not return a response
def run_task_job(task_name):
    tasks = storage.load_tasks()
    task = next((t for t in tasks if t['name'] == task_name), None)
    if not task:
        return
    try:
        result = subprocess.run(task['command'], shell=True, capture_output=True, text=True, timeout=3600)
        output = result.stdout
        error = result.stderr
        returncode = result.returncode
    except Exception as e:
        output = ''
        error = str(e)
        returncode = -1
    log_path = os.path.join(LOGS_DIR, f"{task_name}.log")
    with open(log_path, 'a') as f:
        f.write(f"\n--- Scheduled run at {datetime.now().isoformat()} ---\n")
        f.write(f"Command: {task['command']}\n")
        f.write(f"Return code: {returncode}\n")
        if output:
            f.write(f"Output:\n{output}\n")
        if error:
            f.write(f"Error:\n{error}\n")
    # Update last_run in the database
    task['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    storage.edit_task(task_name, task)

# --- Flask background thread logic ---
flask_thread = None

def run_flask():
    scheduler.start()
    app.run(debug=False, use_reloader=False)

# --- Menu bar integration ---
class BotBrigadeMenuBar(rumps.App):
    def __init__(self):
        super().__init__("🤖", icon=None, quit_button="Quit")
        self.menu = ["Open botBrigade"]

    @rumps.clicked("Open botBrigade")
    def open_app(self, _):
        import webbrowser
        webbrowser.open("http://127.0.0.1:5000")

    def quit_app(self, _):
        rumps.quit_application()
        os._exit(0)  # Force kill all threads and Flask

    def run(self):
        super().run()

if __name__ == '__main__':
    if MACOS:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        BotBrigadeMenuBar().run()
    else:
        run_flask() 