#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    manage
    ~~~~~~

    Management utilities for commit --blog
"""

from flask.ext.script import Manager
from commitblog import create_app


manager = Manager(create_app)


@manager.command
def init_db():
    from commitblog import db
    db.create_all()


if __name__ == '__main__':
    manager.run()
