# -*- coding: utf-8 -*-
"""
    commitblog
    ~~~~~~~~~~

    Turn your commit messages into a blog.

    :license: MPL
    :copyright: uniphil 2014
"""

from os import environ
from datetime import datetime
import dateutil.parser
from flask import (
    Flask, Blueprint, request, flash,
    render_template, redirect, url_for, json, abort)
from flask_login import LoginManager, current_user, login_required
from sqlalchemy.exc import IntegrityError
from wtforms import fields, validators
from flask_wtf import Form
from flask_wtf.csrf import CSRFProtect

from blog import blog
from models import db, message_parts, AnonymousUser, Blogger, Repo, CommitPost
from known_git_hosts.github import gh
import git


GH_RAW_BASE = 'https://raw.githubusercontent.com'


login_manager = LoginManager()
pages = Blueprint('pages', __name__)


class AddCommitForm(Form):
    repo_name = fields.TextField(
        'Repository Name', validators=[validators.DataRequired()])
    sha = fields.TextField(
        'Sha-1 Hash', validators=[validators.Length(min=40, max=40)])
    githubless = fields.BooleanField(
        'Fetch with git instead of GitHub API (beta, may fail for large repositories)')


class UpdateNameForm(Form):
    display_name = fields.TextField(
        'Update your display name', validators=[validators.DataRequired()])


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


def add_without_github_mostly(form):
    repo_url = f'https://github.com/{form.repo_name.data}.git'
    git_commit = git.fetch_commit(repo_url, form.sha.data)

    with gh.AppSession() as session:
        repo, repo_created = Repo.get_or_create(form.repo_name.data)
        commit = CommitPost(
            hex=form.sha.data,
            message=git_commit.message.decode('utf-8'),
            datetime=datetime.fromtimestamp(git_commit.author_time),
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


def add_with_github_api(form):
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


@blog.route('/add')
@login_required
def add():
    form = AddCommitForm(request.args)
    if any((form.repo_name.data, form.sha.data)) and form.validate():
        if form.githubless.data:
            return add_without_github_mostly(form)
        else:
            return add_with_github_api(form)
    return render_template('blog-add.html', form=form)


@blog.route('/account/name', methods=('GET', 'POST'))
@login_required
def name_edit():
    form = UpdateNameForm(request.form)
    if request.method == 'POST' and form.validate():
        new_name, old_name = form.display_name.data, current_user.name
        current_user.name = new_name
        db.session.add(current_user)
        db.session.commit()
        flash('Display name updated: {} ➔ {}'.format(
            old_name, new_name), 'info')
        return redirect(url_for('blog.account'))

    return render_template('name-edit.html', form=form)


@blog.route('/<path:repo_name>/<hex>/unpost', methods=['POST'])
@login_required
def remove(repo_name, hex, blogger=None):
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    commit = CommitPost.query \
                .filter_by(blogger=current_user, hex=hex, repo=repo) \
                .first() or abort(404)
    db.session.delete(commit)
    db.session.commit()
    flash(f'Unposted commit: {commit.repo.full_name}/{commit.hex[:8]} ➔ 💨', 'info')
    next = request.args.get('next') \
            or request.referrer \
            or url_for('.list', blogger=current_user.username)
    return redirect(next)


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
        SQLALCHEMY_TRACK_MODIFICATIONS = False,
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
    CSRFProtect(app)
    return app
