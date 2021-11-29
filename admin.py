from flask import Blueprint, abort, render_template, request
from flask_login import current_user
from flask_wtf import FlaskForm
from time import time
from wtforms import fields, validators
from werkzeug.security import gen_salt
from models import db, Blogger, CommitPost, Task
from models.auth import OAuth2Client
from oauth import SCOPES


class ClientAddForm(FlaskForm):
    client_id = fields.TextField(
        'Client ID (leave blank to auto-generate)')
    client_name = fields.TextField(
        'Application name', validators=[validators.DataRequired()])
    client_uri = fields.TextField(
        'Aplication URI', validators=[validators.DataRequired()])
    redirect_uri = fields.TextField(
        'Redirect URI',
        validators=[
            validators.DataRequired(),
            validators.URL(require_tld=False),  # make localhost dev easier
        ])
    allowed_scopes = fields.SelectMultipleField(
        'Allowed scopes',
        choices=[(k, f'{v} ({k})') for k, v in SCOPES.items()],
        validators=[validators.DataRequired()])
    allowed_grant_types = fields.SelectMultipleField(
        'Allowed grant types',
        choices=(
            ('authorization_code', 'Act on behalf of users (authorization_code)'),
            ('client_credentials', 'Act as the client app itself (client_credentials)'),
        ),
        validators=[validators.DataRequired()])
    token_auth_method = fields.SelectField(
        'Token endpoint authentication method',
        choices=(
            ('none', 'None (for client-side apps)'),
            ('client_secret_basic', 'Client secret basic (for server-side apps)'),
            ('client_secret_post', 'Client secret post (for server-side apps)'),
        ))


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
    return render_template('admin/index.html',
        authors=authors, posts=posts, waiting_tasks=waiting_tasks,
        active_tasks=active_tasks, completed_tasks=completed_tasks)


@admin.route('/clients', methods=('GET', 'POST'))
def clients():
    form = ClientAddForm(request.form)
    if form.validate_on_submit():
        token_auth = form.token_auth_method.data
        client = OAuth2Client(
            client_id=form.client_id.data or gen_salt(24),
            client_id_issued_at=int(time()),
            client_secret = '' if token_auth == 'none' else gen_salt(24),
            dev=current_user)
        client.set_client_metadata({
            'client_name': form.client_name.data,
            'client_uri': form.client_uri.data,
            'grant_types': form.allowed_grant_types.data,
            'redirect_uris': [form.redirect_uri.data],
            'response_types': ['code'],
            'scope': ' '.join(form.allowed_scopes.data),
            'token_endpoint_auth_method': token_auth,
        })
        db.session.add(client)
        db.session.commit()
    clients = OAuth2Client.query.all()
    return render_template('admin/clients.html', form=form, clients=clients)
