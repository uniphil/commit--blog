# -*- coding: utf-8 -*-
"""
    commitblog
    ~~~~~~~~~~

    Turn your commit messages into a blog.

    :license: MPL
    :copyright: uniphil 2014
"""

from os import environ
from datetime import datetime, timedelta
import dateutil.parser
from flask import (
    Flask, Blueprint, request, flash, session,
    render_template, redirect, url_for, json, abort)
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user)
from sqlalchemy.exc import IntegrityError
from wtforms import fields, validators
from flask_wtf import Form
from flask_wtf.csrf import CSRFProtect
from secrets import compare_digest

from admin import admin
from blog import blog
from emails import mail
import limits
from models import (
    db, message_parts, AnonymousUser,
    Blogger, Email, Repo, CommitPost, Task)
from known_git_hosts.github import gh


login_manager = LoginManager()
account = Blueprint('account', __name__)
pages = Blueprint('pages', __name__)

class CommitpostAddForm(Form):
    repo_name = fields.TextField(
        'Repository Name', validators=[validators.DataRequired()])
    sha = fields.TextField(
        'Sha-1 Hash', validators=[validators.Length(min=40, max=40)])


class UnpostForm(Form):
    """unposts a commit (form for csrf only)"""


class NameUpdateForm(Form):
    display_name = fields.TextField(
        'Update your display name', validators=[validators.DataRequired()])


class EmailAddForm(Form):
    address = fields.TextField(
        'Email address', validators=[
            validators.DataRequired(),
            validators.Email(check_deliverability=True)])


@pages.route('/')
def hello():
    return render_template('hello.html')


@account.route('/account')
@login_required
def dashboard():
    if 'gh_email_later' in request.args:
        if session.pop('gh_email', None) is None:
            return redirect(url_for('account.dashboard'))

    # Warning: 0.username used here *must* be trusted from github else a path
    # traversal may get open for GETs as the app.
    # TODO: move gh username to be known_git_provider-specific and out of here.
    events_url = '/users/{0.username}/events/public'.format(current_user)

    with gh.AppSession() as gh_session:
        events_resp = gh_session.get(events_url)
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

    email = current_user.get_email(True)
    return render_template('account.html', events=commit_events, email=email)


def add_with_github_api(form, repo):
    commit_url = '/repos/{repo}/git/commits/{hex}'.format(
        repo=form.repo_name.data, hex=form.sha.data)

    with gh.AppSession() as session:
        gh_commit = session.get(commit_url).json()

    commit = CommitPost(
        hex=form.sha.data,
        message=gh_commit['message'],
        datetime=dateutil.parser.parse(gh_commit['author']['date']),
        repo=repo,
        blogger=current_user,
    )
    return commit


@account.route('/add', methods=('GET', 'POST'))
@login_required
def add_post():
    form = CommitpostAddForm(request.args)
    if any((form.repo_name.data, form.sha.data)) and form.validate():
        repo, repo_created = Repo.get_or_create(form.repo_name.data)
        commit = add_with_github_api(form, repo)
        db.session.add(commit)
        if repo_created:
            db.session.add(repo)
            db.session.add(Task(task='clone', details={'full_name': repo.full_name}))
        try:
            db.session.commit()
        except IntegrityError:
            flash('Already blogged!', 'info')
        return redirect(url_for('account.dashboard'))

    return render_template('blog-add.html', form=form)


def get_confirmation_email_task(email):
    previous_confirmation_sends = Task.query \
        .filter(Task.task == 'email') \
        .filter(Task.creator == current_user) \
        .filter(Task.details['recipient'].as_string() == email.address) \
        .filter(Task.details['message'].as_string() == 'confirm_email')
    if previous_confirmation_sends.count() >= limits.EMAIL_CONFIRMATION_SENDS:
        abort(429, f'Max {limits.EMAIL_CONFIRMATION_SENDS} confirmation email sends. Get in touch if you haven\'t received any!')
    return Task(task='email', details={
        'recipient': email.address,
        'message': 'confirm_email',
        'variables': {
            'username': current_user.username,
            'confirm_url': url_for('account.confirm_email', _external=True,
                address=email.address, token=email.token),
        },
    })


@account.route('/account/add-gh-email', methods=('POST',))
@login_required
def add_gh_email():
    try:
        address = session.pop('gh_email').lower()
    except KeyError:
        abort(400, 'missing gh_email address')

    if 'decline' in request.form:
        current_user.gh_email_choice = False
        db.session.add(current_user)
        db.session.commit()
    elif 'add_email' in request.form:
        current_user.gh_email_choice = True
        email = Email(address=address)
        db.session.add(current_user)
        db.session.add(email)
        try:
            db.session.commit()
        except IntegrityError:
            abort(401, 'This email address may already be in use')
        db.session.add(get_confirmation_email_task(email))
        db.session.commit()
        flash(f'Email added! Confirmation email will be sent to {address}', 'info')
    else:
        abort(400)
    return redirect(url_for('account.dashboard'))


@account.route('/account/email/new', methods=('GET', 'POST'))
@login_required
def add_email():
    session.pop('gh_email', None)
    form = EmailAddForm(request.form)
    if form.validate_on_submit():
        address = form.address.data.lower()
        email = Email(address=address)
        db.session.add(email)
        try:
            db.session.commit()
        except IntegrityError:
            abort(401, 'This email address may already be in use')
        db.session.add(get_confirmation_email_task(email))
        db.session.commit()
        flash(f'Email added! Confirmation email will be sent to {address}', 'info')
        return redirect(url_for('account.dashboard'))
    return render_template('email-add.html', form=form)


@account.route('/accounts/confirm-email/<address>/resend', methods=('POST',))
@login_required
def resend_confirmation_email(address):
    address = address.lower()
    email = Email.query \
        .filter(Email.address == address) \
        .filter(Email.blogger == current_user) \
        .first_or_404()
    db.session.add(get_confirmation_email_task(email))
    db.session.commit()
    flash(f'Confirmation email resent to {address}', 'info')
    return redirect(url_for('account.dashboard'))


@account.route('/account/confirm-email/<address>', methods=('GET', 'POST'))
def confirm_email(address):
    address = address.lower()

    if request.method == 'POST':
        try:
            token = request.args['token']
        except KeyError:
            abort(400, 'missing token')

        email = Email.query.filter(Email.address == address).first_or_404()
        if not compare_digest(token, email.token):
            abort(401)

        if email.confirmed is None:
            email.confirmed = datetime.now()
            db.session.add(email)
            db.session.commit()
            flash('Email confirmed!', 'info')
        else:
            flash('Email already confirmed!', 'info')

        if current_user.is_anonymous:
            login_user(email.blogger)
        elif current_user.id != email.blogger.id:
            logout_user()
        return redirect(url_for('account.dashboard'))

    return render_template('account-email-confirm.html', address=address)


@account.route('/account/name', methods=('GET', 'POST'))
@login_required
def name_edit():
    form = NameUpdateForm(request.form)
    if request.method == 'POST' and form.validate():
        new_name, old_name = form.display_name.data, current_user.name
        current_user.name = new_name
        db.session.add(current_user)
        db.session.commit()
        flash('Display name updated: {} ➔ {}'.format(
            old_name, new_name), 'info')
        return redirect(url_for('account.dashboard'))

    return render_template('name-edit.html', form=form)


@account.route('/<path:repo_name>/<hex>/unpost', methods=('GET', 'POST'))
@login_required
def remove_post(repo_name, hex):
    form = UnpostForm(request.form)
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    commit = CommitPost.query \
                .filter_by(blogger=current_user, hex=hex, repo=repo) \
                .first() or abort(404)
    if request.method == 'POST' and form.validate():
        db.session.delete(commit)
        db.session.commit()
        flash(f'Unposted commit: {commit.repo.full_name}/{commit.hex[:8]} ➔ 💨', 'info')
        return redirect(url_for('blog.list', blogger=current_user.username))
    return render_template('blog-unpost.html', post=commit, form=form)


@account.route('/<path:repo_name>/<hex>/rerender', methods=('GET', 'POST'))
@login_required
def rerender_preview(repo_name, hex):
    repo = Repo.query.filter_by(full_name=repo_name).first() or abort(404)
    commit = CommitPost.query \
                .filter_by(blogger=current_user, hex=hex, repo=repo) \
                .first() or abort(404)

    if request.method == 'POST':
        commit.apply_rerender()
        db.session.add(commit)
        db.session.commit()
        flash('✓ Applied new renderer', 'info')
        next = request.args.get('next') \
            or url_for('blog.commit_post', _external=True,
                        blogger=current_user.username,
                        repo_name=commit.repo.full_name,
                        hex=commit.hex)
        return redirect(next)

    noop_message = None

    if commit.can_rerender():
        preview = commit.get_rerender_preview()
        if preview is None:
            noop_message = f'Commit rerender appears to be empty :/'
        elif preview == commit.markdown_body:
            noop_message = f'No change detected for this commit with the new render config'
            commit.apply_rerender()
            db.session.add(commit)
            db.session.commit()
    else:
        noop_message = f'Commit seems to already be rendered with the latest renderer'

    if noop_message is not None:
        flash(noop_message, 'info')
        next = request.args.get('next') \
            or request.referrer \
            or url_for('blog.list', blogger=current_user.username)
        return redirect(next)

    return render_template('rerender-preview.html', post=commit, preview=preview)


@account.route('/logout')
def logout():
    logout_user()
    referrer = request.referrer
    if referrer is None or \
        referrer.startswith(url_for('account.dashboard', _external=True)):
        return redirect(url_for('pages.hello'))
    else:
        return redirect(referrer)


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
        TESTING                 = bool(get('TESTING', False)),
        GITHUB_CLIENT_ID        = get('GITHUB_CLIENT_ID'),
        GITHUB_CLIENT_SECRET    = get('GITHUB_CLIENT_SECRET'),
        CSRF_ENABLED            = get('CSRF_ENABLED', True),  # testing ONLY
        GIT_REPO_DIR            = get('GIT_REPO_DIR', './repos'),
        MAIL_SERVER             = get('MAIL_SERVER'),
        MAIL_PORT               = int(get('MAIL_PORT', '2525')),
        MAIL_USE_TLS            = get('MAIL_USE_TLS') != 'False',
        MAIL_USERNAME           = get('MAIL_USERNAME'),
        MAIL_PASSWORD           = get('MAIL_PASSWORD'),
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
    mail.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(account)
    app.register_blueprint(admin, url_prefix='/admin')
    if app.config['ENV'] == 'development':
        app.register_blueprint(blog, url_prefix='/_subdomain:<blogger>')
    else:
        app.register_blueprint(blog, subdomain='<blogger>')
    app.register_blueprint(gh, url_prefix='/gh')
    CSRFProtect(app)
    return app
