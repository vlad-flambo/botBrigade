import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'tasks.db')
FIELDNAMES = ['name', 'command', 'schedule', 'status', 'last_run']

# Ensure the tasks table exists and has an 'order' column
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        name TEXT PRIMARY KEY,
        command TEXT NOT NULL,
        schedule TEXT NOT NULL,
        status TEXT NOT NULL,
        last_run TEXT,
        "order" INTEGER DEFAULT 0
    )
''')
# Add 'order' column if missing
try:
    c.execute('ALTER TABLE tasks ADD COLUMN "order" INTEGER DEFAULT 0')
except sqlite3.OperationalError:
    pass
conn.commit()
conn.close()

def load_tasks():
    tasks = []
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for row in c.execute('SELECT name, command, schedule, status, last_run FROM tasks ORDER BY "order" ASC, name ASC'):
        row = list(row)
        if row[4] is None:
            row[4] = ''
        task = dict(zip(FIELDNAMES, row))
        tasks.append(task)
    conn.close()
    return tasks

def add_task(task):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO tasks (name, command, schedule, status, last_run) VALUES (?, ?, ?, ?, ?)',
                  (task['name'], task['command'], task['schedule'], task['status'], task.get('last_run', '')))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Task with name '{task['name']}' already exists.")
    conn.close()

def edit_task(name, new_task):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE tasks SET command=?, schedule=?, status=?, last_run=? WHERE name=?
    ''', (new_task['command'], new_task['schedule'], new_task['status'], new_task.get('last_run', ''), name))
    conn.commit()
    conn.close()

def delete_task(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE name=?', (name,))
    conn.commit()
    conn.close()

def rename_task(old_name, new_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE tasks SET name=? WHERE name=?', (new_name, old_name))
    conn.commit()
    conn.close()

def save_tasks(tasks):
    # Not needed with SQLite, but kept for compatibility
    pass

def set_task_order(task_names):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for idx, name in enumerate(task_names):
        c.execute('UPDATE tasks SET "order"=? WHERE name=?', (idx, name))
    conn.commit()
    conn.close() 