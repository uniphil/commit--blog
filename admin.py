from flask import Blueprint, abort, render_template
from flask_login import current_user
from models import Blogger, CommitPost, Task


admin = Blueprint('admin', __name__)


@admin.before_request
def only_admins():
    if not current_user.admin:
        abort(401)


@admin.route('/')
def index():
    authors = Blogger.query.limit(24)
    posts = CommitPost.query.order_by(CommitPost.datetime.desc()).limit(24)
    waiting_tasks = Task.query.filter(Task.started.is_(None)).order_by(Task.created.desc()).limit(24)
    active_tasks = Task.query.filter((Task.started != None) & Task.completed.is_(None)).order_by(Task.started.desc()).limit(24)
    completed_tasks = Task.query.filter(Task.completed != None).order_by(Task.completed.desc()).limit(24)
    return render_template('admin.html',
        authors=authors, posts=posts, waiting_tasks=waiting_tasks,
        active_tasks=active_tasks, completed_tasks=completed_tasks)
