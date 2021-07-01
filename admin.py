from flask import Blueprint, abort, render_template
from flask_login import current_user
from models import Blogger, CommitPost


admin = Blueprint('admin', __name__)


@admin.before_request
def only_admins():
    if not current_user.admin:
        abort(401)


@admin.route('/')
def index():
    authors = Blogger.query.limit(24)
    posts = CommitPost.query.order_by(CommitPost.datetime.desc()).limit(24)
    return render_template('admin.html', authors=authors, posts=posts)
