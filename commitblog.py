# -*- coding: utf-8 -*-
"""
    commitblog
    ~~~~~~~~~~

    Turn your commit messages into a blog.

    :license: MPL
    :copyright: uniphil 2014
"""

from os import environ
from rauth.service import OAuth2Service
from flask import (Flask, Blueprint, request, flash, render_template, redirect,
                   url_for, json, abort)
from flask.ext.login import (LoginManager, UserMixin, current_user, login_user,
                             logout_user)
from flask.ext.sqlalchemy import SQLAlchemy


login_manager = LoginManager()
db = SQLAlchemy()
pages = Blueprint('pages', __name__)
blog = Blueprint('blog', __name__)
gh = Blueprint('gh', __name__)


@login_manager.user_loader
def load_user(blogger_id):
    return Blogger.query.get(blogger_id)


class Blogger(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    gh_id = db.Column(db.String(32), unique=True)
    username = db.Column(db.String(39), unique=True)  # GH max is 39
    name = db.Column(db.String(128))
    avatar_url = db.Column(db.String(256))
    access_token = db.Column(db.String(40))  # GH tokens seem to always be 40 chars

    @classmethod
    def gh_get_or_create(cls, session):
        user_obj = session.get('user').json()
        user = cls.query.filter_by(gh_id=str(user_obj['id'])).first()
        if user is None:
            user = cls(
                gh_id=user_obj['id'],
                username=user_obj['login'],
                name=user_obj['name'],
                avatar_url=user_obj['avatar_url'],
                access_token=session.access_token,
            )
            db.session.add(user)
            db.session.commit()
        return user


class Repo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    full_name = db.Column(db.String(180), unique=True)  # for storage path
    description = db.Column(db.String(384))


class CommitPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hex = db.Column(db.String(40))
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'))
    blogger_id = db.Column(db.Integer, db.ForeignKey('blogger.id'))

    repo = db.relationship('Repo')
    blogger = db.relationship('Blogger', backref=db.backref('commit_posts'))


@pages.route('/')
def hello():
    return render_template('hello.html')


@blog.route('/', subdomain='<blogger>')
def list(blogger):
    blog_author = Blogger.query.filter_by(username=blogger).first() or abort(404)
    my_blog = (current_user == blog_author)
    return render_template('blog-list.html', my_blog=my_blog, blogger=blog_author)


@gh.record
def setup_github(state):
    state.blueprint.api = OAuth2Service(name='github',
       base_url='https://api.github.com/',
       authorize_url='https://github.com/login/oauth/authorize',
       access_token_url='https://github.com/login/oauth/access_token',
       client_id=state.app.config['GITHUB_CLIENT_ID'],
       client_secret=state.app.config['GITHUB_CLIENT_SECRET'],
    )


@gh.route('/login')
def login():
    auth_uri = gh.api.get_authorize_url(scope='user,public_repo')
    return redirect(auth_uri)


@gh.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('pages.hello'))


@gh.route('/authorized')
def authorized():
    if 'code' not in request.args:
        return redirect(url_for('pages.hello', auth='sadface'))

    session = gh.api.get_auth_session(data={'code': request.args['code']})
    blogger = Blogger.gh_get_or_create(session)

    login_user(blogger)
    return redirect(url_for('blog.list', blogger=blogger.username))


def configure(app, config):
    config = config or {}
    get = lambda key, default=None: config.get(key, environ.get(key, default))
    app.config.update(
        SECRET_KEY              = get('SECRET_KEY'),
        DEBUG                   = get('DEBUG') == 'True',
        HOST                    = get('HOST', '127.0.0.1'),
        PORT                    = int(get('PORT', 5000)),
        SQLALCHEMY_DATABASE_URI = get('DATABASE_URL', 'sqlite:///db'),
        GITHUB_CLIENT_ID        = get('GITHUB_CLIENT_ID'),
        GITHUB_CLIENT_SECRET    = get('GITHUB_CLIENT_SECRET'),
        CSRF_ENABLED            = get('CSRF_ENABLED', True),  # testing ONLY
    )
    server_name = get('SERVER_NAME')
    if server_name is not None:
        app.config['SERVER_NAME'] = server_name


def create_app(config=None):
    app = Flask('commitblog')
    configure(app, config)
    login_manager.init_app(app)
    db.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(blog)
    app.register_blueprint(gh, url_prefix='/gh')
    return app
