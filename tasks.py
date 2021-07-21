from flask import current_app
from models import db, Repo, Task
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
import pygit2
import sys
import time


def take_task(of_type=None, max_retry=3):
    q = Task.query \
        .order_by(Task.created.asc()) \
        .filter(Task.started.is_(None))

    if of_type is not None:
        q = q.filter(Task.task == of_type)

    try:
        with db.session.begin_nested():
            if task := q.first():
                task.started = func.now()
                db.session.add(task)
    except OperationalError:
        db.session.rollback()
        if max_retry > 0:
            return take_task(of_type, max_retry - 1)

    return task


def get_tasks(of_type=None, poll_interval=1):
    while True:
        if task := take_task(of_type):
            yield task
        time.sleep(poll_interval)


_task_handlers = {}
def handle_task(handler):
    _task_handlers[handler.__name__] = handler
    return handler


def _init_remote(repo, name, url):
    remote = repo.remotes.create(name, url, "+refs/*:refs/*")
    mirror_var = "remote.{}.mirror".format(name.decode())
    repo.config[mirror_var] = True
    return remote

@handle_task
def clone(task):
    full_name = task.details['full_name']
    repo = Repo.query.filter(Repo.full_name == full_name).one()
    git_dir = current_app.config['GIT_REPO_DIR']
    repo_dir = f'{git_dir}/{repo.id}.git'
    pygit2.clone_repository(f'https://github.com/{full_name}', repo_dir,
        bare=True, remote=_init_remote)


def run(task_type=None):
    print('hello! i am a task runner.')
    if task_type is None:
        print(f'running tasks with handlers for:', ','.join(_task_handlers), file=sys.stderr)
    else:
        print(f'running for only {task_type} tasks', file=sys.stderr)

    for task in get_tasks(task_type):
        try:
            handler = _task_handlers[task.task]
        except KeyError:
            print(f'handler not found for task {task.task}', file=sys.stderr)
            raise
        print(f'found task {task.task} ({task.id}) task. handling...', file=sys.stderr)
        try:
            handler(task)
        except Exception as e:
            print(f'oh no, task {task.task} errored out: {task}:\n{e}', file=sys.stderr)
        else:
            task.completed = func.now()
            db.session.add(task)
            try:
                db.session.commit()
            except OperationalError as e:
                print(f'oh no, task {task.task} completed, but committing completionerrored out: {task}:\n{e}', file=sys.stderr)
                db.session.rollback()
            else:
                print(f'\tcompleted task {task.task} ({task.id}). woo!', file=sys.stderr)

