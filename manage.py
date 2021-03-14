#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    manage
    ~~~~~~

    Management utilities for commit --blog
"""

from flask_script import Manager
from commitblog import create_app


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
def grunserver():
    """run locally in a prod-ish way with gunicorn"""
    import subprocess
    try:
        subprocess.run([
            'gunicorn',
            'wsgi:app',
            '--no-sendfile',
            '--workers=2',
            '--bind=0.0.0.0:5000',
            '--reload',
        ])
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    manager.run()
