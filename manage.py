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
def list_blogs():
    from sqlalchemy import func
    from commitblog import db, Blogger
    bloggers = Blogger.query \
                    .order_by(db.session.query(
                        func.count(Blogger.commit_posts)))
    for blogger in bloggers.all():
        print('{: 3d} {}'.format(len(blogger.commit_posts), blogger.username))


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
        """)
    query = migs[q]
    db.engine.execute(query.execution_options(autocommit=True))


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
