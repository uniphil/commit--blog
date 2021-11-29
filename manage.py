#!venv/bin/python
# -*- coding: utf-8 -*-
"""
    manage
    ~~~~~~

    Management utilities for commit --blog
"""

from flask_script import Manager
from commitblog import create_app


try:
    from dotenv import load_dotenv
    load_dotenv(verbose=True)
except ImportError:
    from sys import stderr
    print('python-dotenv not installed, not trying to load .env', file=stderr)
    pass


manager = Manager(create_app)


@manager.command
def init_db():
    from commitblog import db
    db.create_all()


@manager.command
def reinit_db():
    from commitblog import db
    db.drop_all()
    db.create_all()


@manager.command
def make_admin(username):
    from commitblog import db, Blogger
    hopeful = Blogger.query.filter(Blogger.username == username).first()
    assert hopeful is not None, f'no blogger found for username "{username}"'
    hopeful.admin = True
    db.session.add(hopeful)
    db.session.commit()


@manager.command
def migrate(q):
    from commitblog import db
    from sqlalchemy.sql import text
    migs = {}
    migs['q1'] = text("""
        alter table commit_post
        add column markdown_renderer varchar null
        """)
    migs['q2'] = text("""
        alter table blogger
        add column admin boolean not null default false
        check (admin in (0, 1))
        """)
    migs['q3'] = text("""
        alter table blogger
        add column gh_email_choice boolean check
        (gh_email_choice in (0, 1))
        """)
    query = migs[q]
    db.engine.execute(query.execution_options(autocommit=True))


@manager.command
def run_tasks():
    import tasks
    tasks.run()


@manager.command
def test_email():
    import tasks
    from models import Task
    tasks.email(Task(details={
        'message': 'hello',
        'recipient': 'uniphil+recip@gmail.com',
        'variables': {'value': 42},
    }))


@manager.command
def grunserver():
    """run locally in a prod-ish way with gunicorn"""
    import subprocess
    try:
        subprocess.run([
            'gunicorn',
            'wsgi:app',
            '--no-sendfile',
            '--workers=2',
            '--worker-class=gevent',
            '--bind=0.0.0.0:5000',
            '--reload',
        ])
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    manager.run()
