# -*- coding: utf-8 -*-
"""
    commitblog
    ~~~~~~~~~~

    Turn your commit messages into a blog.

    :license: MPL
    :copyright: uniphil 2014
"""

from os import environ
from urllib.parse import urlparse, urljoin, parse_qsl
from werkzeug.contrib.atom import AtomFeed
import dateutil.parser
import re
from requests.sessions import Session
from requests.utils import default_user_agent
from rauth.service import OAuth2Session, OAuth2Service
from flask import (
    Flask, Blueprint, request, session as client_session, flash,
    render_template, redirect, url_for, json, abort)
from flask_login import (
    LoginManager, login_user, logout_user, UserMixin, AnonymousUserMixin,
    current_user, login_required)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from wtforms import fields, validators
from flask_wtf import Form
from flask_wtf.csrf import CsrfProtect


GH_RAW_BASE = 'https://raw.githubusercontent.com'


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

    username = 'anon'

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
                name=user_obj.get('name'),
                avatar_url=user_obj.get('avatar_url'),
                access_token=session.access_token,
            )
            db.session.add(user)
            db.session.commit()
        return user

    @classmethod
    def from_subdomain(cls, username):
        """Handle casing issues with domains"""
        return cls.query.filter(username.lower() == func.lower(cls.username)).first()

    def is_blogger(self, blogger):
        return (self == blogger)

    def get_session(self):
        return gh.oauth.get_session(token=self.access_token)

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

    __table_args__ = (db.UniqueConstraint('hex', 'repo_id'),)

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
            return self.fix_gh_img(self.markdown_body)
        else:
            return self.get_parts()[1]

    def fix_gh_img(self, html):
        def repl(m):
            path = m.groupdict()['path']
            if '://' in path:
                return m.group(0)
            else:
                fixed_path = '{base}/{repo}/{sha}/{path}'.format(
                    base=GH_RAW_BASE, repo=self.repo.full_name, sha=self.hex,
                    path=path)
                return m.group(0).replace(path, fixed_path)

        return re.sub(r'<img src="(?P<path>.*?)"', repl, html)

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
    events_url = '/users/{0.username}/events/public'.format(current_user)
    with gh.AppSession() as session:
        events_resp = session.get(events_url)
    events = events_resp.json()
    commit_events = []
    for event in events:
        if event['type'] == 'PushEvent':
            for commit in event['payload']['commits']:
                commit.update(repo=event['repo']['name'])
                title, body = message_parts(commit['message'])
                if not body:
                    continue
                post = CommitPost.query.filter_by(hex=commit['sha']).first()
                commit.update(title=title, body=body, post=post)
                commit_events.append(commit)
    return render_template('account.html', events=commit_events)


@blog.route('/', subdomain='<blogger>')
def list(blogger):
    blog_author = Blogger.from_subdomain(blogger) or abort(404)
    posts = CommitPost.query \
                .filter_by(blogger=blog_author) \
                .order_by(CommitPost.datetime.desc())
    return render_template('blog-list.html', posts=posts, blogger=blog_author)


@blog.route('/feed', subdomain='<blogger>')
def feed(blogger):
    blog_author = Blogger.from_subdomain(blogger) or abort(404)
    posts = CommitPost.query \
                .filter_by(blogger=blog_author) \
                .order_by(CommitPost.datetime.desc())
    feed = AtomFeed('$ commits-by ' + (blog_author.name or blog_author.username),
                    feed_url=request.url, url=request.url_root)
    for post in posts:
        feed.add(
            post.get_title(),
            post.get_body(markdown=True),
            content_type='html',
            author=blog_author.name or blog_author.username,
            url=url_for('blog.commit_post', _external=True,
                        blogger=blog_author.username,
                        repo_name=post.repo.full_name,
                        hex=post.hex),
            updated=post.datetime,
            published=post.datetime,
        )
    return feed.get_response()


@blog.route('/<path:repo_name>/<hex>', subdomain='<blogger>')
def commit_post(blogger, repo_name, hex):
    blog_author = Blogger.from_subdomain(blogger) or abort(404)
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    post = CommitPost.query \
                .filter_by(blogger=blog_author, repo=repo, hex=hex) \
                .first() or abort(404)
    return render_template('blog-post.html', post=post, blogger=blog_author)


@blog.route('/add')
@login_required
def add():
    form = AddCommitForm(request.args)
    if any((form.repo_name.data, form.sha.data)) and form.validate():
        commit_url = '/repos/{repo}/git/commits/{hex}'.format(
                        repo=form.repo_name.data, hex=form.sha.data)
        with gh.AppSession() as session:
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
                markdown_data = json.dumps(dict(
                    text=commit.get_body(),
                    mode='gfm',
                    context=form.repo_name.data))
                commit.markdown_body = session.post(
                    '/markdown', data=markdown_data).text
            else:
                commit.markdown_body = ''
        db.session.add(commit)
        if repo_created:
            db.session.add(repo)
        try:
            db.session.commit()
        except IntegrityError:
            flash('Already blogged!', 'info')
        return redirect(url_for('blog.account'))

    return render_template('blog-add.html', form=form)


@blog.route('/<path:repo_name>/<hex>/unpost', methods=['POST'])
@login_required
def remove(repo_name, hex):
    next = request.referrer or url_for('.list', blogger=current_user.username)
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    commit = CommitPost.query \
                .filter_by(blogger=current_user, hex=hex, repo=repo) \
                .first() or abort(404)
    db.session.delete(commit)
    db.session.commit()
    return redirect(next)


def useragentify(session):
    """declare a specific user-agent for commit --blog"""
    user_agent = default_user_agent('commit --blog')
    session.headers.update({'User-Agent': user_agent})


class GHAppSession(Session):
    """A session object for app-authenticated GitHub API requests

    Allows relative URLs from a base_url.

    Injects the app id and secret instead of the user's (useless-for-no-scopes)
    bearer token to make requests to public endpoints with the usual 5000 req
    rate limit rules.
    """

    def __init__(self, base_url, client_id, client_secret):
        super(GHAppSession, self).__init__()
        useragentify(self)
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret

    def request(self, method, url, **req_kwargs):
        # absolutify URL
        if not bool(urlparse(url).netloc):
            url = urljoin(self.base_url, url)

        # inject app credentials
        auth=(self.client_id, self.client_secret)

        return super(GHAppSession, self).request(
            method, url, auth=auth, **req_kwargs)


class GHOAuthSession(OAuth2Session):
    """An OAuth2 session for user authentication, with a nice UA header"""

    def __init__(self, *args, **kwargs):
        super(GHOAuthSession, self).__init__(*args, **kwargs)
        useragentify(self)


@gh.record
def setup_github(state):
    gh.BASE_URL = 'https://api.github.com/'
    gh.oauth = OAuth2Service(
        name='github',
        base_url=gh.BASE_URL,
        authorize_url='https://github.com/login/oauth/authorize',
        access_token_url='https://github.com/login/oauth/access_token',
        client_id=state.app.config['GITHUB_CLIENT_ID'],
        client_secret=state.app.config['GITHUB_CLIENT_SECRET'],
        session_obj=GHOAuthSession,
    )
    gh.AppSession = lambda: GHAppSession(
        gh.BASE_URL,
        client_id=state.app.config['GITHUB_CLIENT_ID'],
        client_secret=state.app.config['GITHUB_CLIENT_SECRET'],
    )


@gh.route('/login')
def login():
    referrer = request.referrer
    if referrer is None or \
        referrer.startswith(url_for('pages.hello', _external=True)):
        client_session['after_login_redirect'] = None
    else:
        client_session['after_login_redirect'] = referrer
    auth_uri = gh.oauth.get_authorize_url()
    return redirect(auth_uri)


@gh.route('/authorized')
def authorized():
    # final stage of oauth login
    next = client_session.pop('after_login_redirect', None)

    if 'code' not in request.args:
        return redirect(next or url_for('pages.hello', auth='sadface'))

    session = gh.oauth.get_auth_session(data={'code': request.args['code']})
    blogger = Blogger.gh_get_or_create(session)

    login_user(blogger)
    return redirect(next or url_for('blog.account'))


@gh.route('/logout')
def logout():
    logout_user()
    referrer = request.referrer
    if referrer is None or \
        referrer.startswith(url_for('blog.account', _external=True)):
        return redirect(url_for('pages.hello'))
    else:
        return redirect(referrer)


@gh.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    for post in current_user.commit_posts:
        db.session.delete(post)
    db.session.delete(current_user)
    # don't delete repos because they may be used by other users
    # later maybe prune orphans
    db.session.commit()
    logout_user()
    return redirect(url_for('pages.hello'))


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

    @app.errorhandler(404)
    def not_found(error):
        return render_template('not-found.html'), 404


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
