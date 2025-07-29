from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta, time
import storage
import app
import threading
import re
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import logging
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_MISSED, EVENT_JOB_ERROR

# Set up persistent job store
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
}
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler_lock = threading.Lock()

# Set up logging to a file for scheduler events
logging.basicConfig(
    filename='scheduler.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Listener for task events
def job_listener(event):
    if event.code == EVENT_JOB_EXECUTED:
        logging.info(f"Task executed: {event.job_id}")
    elif event.code == EVENT_JOB_MISSED:
        logging.warning(f"Task MISSED: {event.job_id}")
    elif event.code == EVENT_JOB_ERROR:
        logging.error(f"Task ERROR: {event.job_id}")

scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_MISSED | EVENT_JOB_ERROR)

# Helper to parse schedule string
# Supports: 'YYYY-MM-DD HH:MM' (one-time), 'interval:5m', 'interval:2h', 'interval:1d',
# and 'weekdays:<start>-<end>:<interval>' (e.g., 'weekdays:09:00-17:00:30m')
def parse_schedule(schedule_str):
    if schedule_str.startswith('interval:'):
        val = schedule_str.split(':', 1)[1]
        if val.endswith('m'):
            return IntervalTrigger(minutes=int(val[:-1]))
        elif val.endswith('h'):
            return IntervalTrigger(hours=int(val[:-1]))
        elif val.endswith('d'):
            return IntervalTrigger(days=int(val[:-1]))
    elif schedule_str.startswith('weekdays:'):
        # Format: weekdays:HH:MM-HH:MM:Xm (e.g., weekdays:09:00-17:00:30m)
        match = re.match(r'weekdays:(\d{2}:\d{2})-(\d{2}:\d{2}):(\d+)([mh])', schedule_str)
        if match:
            start_str, end_str, interval_val, interval_unit = match.groups()
            start_hour, start_minute = map(int, start_str.split(':'))
            end_hour, end_minute = map(int, end_str.split(':'))
            interval = int(interval_val)
            # Only support minute or hour intervals for now
            triggers = []
            # Calculate all times between start and end at the given interval
            t = time(start_hour, start_minute)
            end_t = time(end_hour, end_minute)
            times = []
            while True:
                times.append((t.hour, t.minute))
                if interval_unit == 'm':
                    dt = (datetime.combine(datetime.today(), t) + timedelta(minutes=interval)).time()
                else:
                    dt = (datetime.combine(datetime.today(), t) + timedelta(hours=interval)).time()
                if (dt.hour, dt.minute) > (end_t.hour, end_t.minute):
                    break
                t = dt
            # Create a CronTrigger for each time
            for hour, minute in times:
                triggers.append(CronTrigger(day_of_week='mon-fri', hour=hour, minute=minute))
            # Return a list of triggers (handled in schedule_all_tasks)
            return triggers
    else:
        # Assume date/time string
        try:
            run_date = datetime.strptime(schedule_str, '%Y-%m-%d %H:%M')
            return DateTrigger(run_date=run_date)
        except Exception:
            return None

# Schedule all enabled tasks on startup
def schedule_all_tasks():
    with scheduler_lock:
        scheduler.remove_all_jobs()
        tasks = storage.load_tasks()
        for task in tasks:
            if task['status'] == 'enabled':
                triggers = parse_schedule(task['schedule'])
                if isinstance(triggers, list):
                    for idx, trigger in enumerate(triggers):
                        scheduler.add_job(
                            func=app.run_task_job,
                            trigger=trigger,
                            args=[task['name']],
                            id=f"{task['name']}_{idx}",
                            replace_existing=True,
                            misfire_grace_time=3600  # 1 hour
                        )
                elif triggers:
                    scheduler.add_job(
                        func=app.run_task_job,
                        trigger=triggers,
                        args=[task['name']],
                        id=task['name'],
                        replace_existing=True,
                        misfire_grace_time=3600  # 1 hour
                    )

def add_or_update_task_schedule(task):
    with scheduler_lock:
        if task['status'] != 'enabled':
            # Remove all jobs for this task
            for job in list(scheduler.get_jobs()):
                if job.id.startswith(task['name']):
                    scheduler.remove_job(job.id, jobstore=None)
            return
        triggers = parse_schedule(task['schedule'])
        if isinstance(triggers, list):
            for idx, trigger in enumerate(triggers):
                scheduler.add_job(
                    func=app.run_task_job,
                    trigger=trigger,
                    args=[task['name']],
                    id=f"{task['name']}_{idx}",
                    replace_existing=True,
                    misfire_grace_time=3600  # 1 hour
                )
        elif triggers:
            scheduler.add_job(
                func=app.run_task_job,
                trigger=triggers,
                args=[task['name']],
                id=task['name'],
                replace_existing=True,
                misfire_grace_time=3600  # 1 hour
            )

def remove_task_schedule(task_name):
    with scheduler_lock:
        for job in list(scheduler.get_jobs()):
            if job.id.startswith(task_name):
                scheduler.remove_job(job.id, jobstore=None)

def start():
    schedule_all_tasks()
    # Log all tasks and their next run times
    jobs = scheduler.get_jobs()
    for job in jobs:
        nrt = getattr(job, 'next_run_time', None)
        logging.info(f"Scheduled task: {job.id}, next run: {nrt}")
    scheduler.start() 