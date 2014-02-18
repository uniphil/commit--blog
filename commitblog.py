# -*- coding: utf-8 -*-
"""
    commitblog
    ~~~~~~~~~~

    Turn your commit messages into a blog.

    :license: MPL
    :copyright: uniphil 2014
"""

from os import environ
import json
import dateutil.parser
from rauth.service import OAuth2Service
from flask import (Flask, Blueprint, request, session as client_session, flash,
                   render_template, redirect, url_for, json, abort)
from flask.ext.login import (LoginManager, login_user, logout_user, UserMixin,
                             AnonymousUserMixin, current_user, login_required)
from flask.ext.sqlalchemy import SQLAlchemy
from wtforms import fields, validators
from flask.ext.wtf import Form
from flask.ext.wtf.csrf import CsrfProtect


login_manager = LoginManager()
db = SQLAlchemy()
pages = Blueprint('pages', __name__)
blog = Blueprint('blog', __name__)
gh = Blueprint('gh', __name__)


def message_parts(commit_message):
    parts = commit_message.split('\n', 1)
    try:
        return parts[0], parts[1]
    except IndexError:
        return parts[0], ''


class AnonymousUser(AnonymousUserMixin):
    """Implement convenient methods that are nice to use on current_user"""
    def is_blogger(self, blogger):
        return False


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

    def is_blogger(self, blogger):
        return (self == blogger)

    def get_session(self):
        return gh.api.get_session(token=self.access_token)

    def get_new_events(self):
        events_url = '/users/{0.username}/events/public'.format(self)
        events = self.get_session().get(events_url).json()
        commit_events = []
        for event in events:
            if event['type'] == 'PushEvent':
                for commit in event['payload']['commits']:
                    commit.update(repo=event['repo']['name'])
                    title, body = message_parts(commit['message'])
                    if not body:
                        continue
                    commit.update(title=title, body=body)
                    commit_events.append(commit)
        return commit_events

    def __repr__(self):
        return '<Blogger: {}>'.format(self.username)


class Repo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    full_name = db.Column(db.String(180), unique=True)
    description = db.Column(db.String(384))

    @classmethod
    def get_or_create(cls, repo_name):
        created = False
        repo = cls.query.filter_by(full_name=repo_name).first()
        if repo is None:
            repo = cls(full_name=repo_name)
            created = True
        return repo, created

    def __repr__(self):
        return '<Repo: {}>'.format(self.full_name)


class CommitPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hex = db.Column(db.String(40))
    message = db.Column(db.String)
    markdown_body = db.Column(db.String)
    datetime = db.Column(db.DateTime)
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'))
    blogger_id = db.Column(db.Integer, db.ForeignKey('blogger.id'))

    repo = db.relationship('Repo')
    blogger = db.relationship('Blogger', backref=db.backref('commit_posts'))

    def get_parts(self):
        return message_parts(self.message)

    def get_title(self):
        return self.get_parts()[0]

    def get_body(self, markdown=False):
        if markdown:
            return self.markdown_body
        else:
            return self.get_parts()[1]

    def __repr__(self):
        return '<CommitPost: {}...>'.format(self.message[:16])


class AddCommitForm(Form):
    repo_name = fields.TextField('Repository Name',
                                 validators=[validators.DataRequired()])
    sha = fields.TextField('Sha-1 Hash',
                           validators=[validators.Length(min=40, max=40)])


@pages.route('/')
def hello():
    return render_template('hello.html')


@blog.route('/account')
@login_required
def account():
    posts = CommitPost.query \
                .filter_by(blogger=current_user) \
                .order_by(CommitPost.datetime.desc())
    return render_template('account.html', posts=posts)


@blog.route('/', subdomain='<blogger>')
def list(blogger):
    blog_author = Blogger.query.filter_by(username=blogger).first() or abort(404)
    posts = CommitPost.query \
                .filter_by(blogger=blog_author) \
                .order_by(CommitPost.datetime.desc())
    return render_template('blog-list.html', posts=posts, blogger=blog_author)


@blog.route('/<path:repo_name>/<hex>', subdomain='<blogger>')
def commit_post(blogger, repo_name, hex):
    blog_author = Blogger.query.filter_by(username=blogger).first() or abort(404)
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    post = CommitPost.query \
                .filter_by(blogger=blog_author, repo=repo, hex=hex) \
                .first() or abort(404)
    return render_template('blog-commit.html', post=post, blogger=blog_author)


@blog.route('/add')
@login_required
def add():
    form = AddCommitForm(request.args)
    if any((form.repo_name.data, form.sha.data)) and form.validate():
        session = current_user.get_session()
        commit_url = '/repos/{repo}/git/commits/{hex}'.format(
                        repo=form.repo_name.data, hex=form.sha.data)
        gh_commit = session.get(commit_url).json()
        repo, repo_created = Repo.get_or_create(form.repo_name.data)
        commit = CommitPost(
            hex=form.sha.data,
            message=gh_commit['message'],
            datetime=dateutil.parser.parse(gh_commit['author']['date']),
            repo=repo,
            blogger=current_user,
        )
        if commit.get_body():
            markdown_data = json.dumps(dict(text=commit.get_body(),
                                    mode='gfm', context=form.repo_name.data))
            commit.markdown_body = session.post('/markdown',
                                    data=markdown_data).text
        else:
            commit.markdown_body = ''
        db.session.add(commit)
        if repo_created:
            db.session.add(repo)
        db.session.commit()
        return redirect(url_for('blog.list', blogger=current_user.username))

    return render_template('blog-add.html', form=form)


@blog.route('/<path:repo_name>/<hex>/unpost')
@login_required
def remove(repo_name, hex):
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    commit = CommitPost.query \
                .filter_by(blogger=current_user, hex=hex, repo=repo) \
                .first() or abort(404)
    db.session.delete(commit)
    db.session.commit()
    return redirect(url_for('.list', blogger=current_user.username))


@gh.record
def setup_github(state):
    gh.api = OAuth2Service(name='github',
       base_url='https://api.github.com/',
       authorize_url='https://github.com/login/oauth/authorize',
       access_token_url='https://github.com/login/oauth/access_token',
       client_id=state.app.config['GITHUB_CLIENT_ID'],
       client_secret=state.app.config['GITHUB_CLIENT_SECRET'],
    )


@gh.route('/login')
def login():
    client_session['post_login_target'] = request.referrer if not \
        request.referrer.startswith(url_for('pages.hello', _external=True)) \
        else None
    auth_uri = gh.api.get_authorize_url(scope='user,public_repo', next=next)
    return redirect(auth_uri)


@gh.route('/logout')
def logout():
    print('logging out...')
    next = request.referrer
    if next.startswith(url_for('blog.account', _external=True)):
        next = None  # don't go back to the account page
    print('next: {}'.format(next))
    logout_user()
    return redirect(next or url_for('pages.hello'))


@gh.route('/authorized')
def authorized():
    next = client_session.pop('post_login_target', None)
    if 'code' not in request.args:
        return redirect(next or url_for('pages.hello', auth='sadface'))

    session = gh.api.get_auth_session(data={'code': request.args['code']})
    blogger = Blogger.gh_get_or_create(session)

    login_user(blogger)
    return redirect(next or url_for('blog.account'))


@login_manager.user_loader
def load_user(blogger_id):
    return Blogger.query.get(blogger_id)


login_manager.anonymous_user = AnonymousUser


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

    @app.template_filter('nice_date')
    def nice_date(date, format='%b %d, %Y'):
        return date.strftime(format) if date else None


def create_app(config=None):
    app = Flask('commitblog')
    configure(app, config)
    login_manager.init_app(app)
    db.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(blog)
    app.register_blueprint(gh, url_prefix='/gh')
    CsrfProtect(app)
    return app
