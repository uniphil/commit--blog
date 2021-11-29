from flask import (
    Blueprint, abort, current_app, redirect, render_template, request,
    session, url_for
)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import fields
from models import Blogger, CommitPost, Task
from authlib.integrations.flask_oauth2 import (
    AuthorizationServer,
    ResourceProtector,
)
from authlib.integrations.sqla_oauth2 import create_bearer_token_validator
from authlib.oauth2 import OAuth2Error
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc7636 import CodeChallenge
from models import db, Blogger
from models.auth import OAuth2Client, OAuth2AuthorizationCode, OAuth2Token
from wtf import csrf

oauth = Blueprint('oauth', __name__)

SCOPES = {
    'blog': 'Create, view, and update posts',
    'profile': 'Read and write public profile info',
    'account': 'Manage private account data',
}


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic',
        'client_secret_post',
        'none',
    ]

    def save_authorization_code(self, code, request):
        code_challenge = request.data.get('code_challenge')
        code_challenge_method = request.data.get('code_challenge_method')
        auth_code = OAuth2AuthorizationCode(
            code=code,
            client_id=request.client.client_id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            blogger_id=request.user.id,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
        db.session.add(auth_code)
        db.session.commit()
        return auth_code

    def query_authorization_code(self, code, client):
        auth_code = OAuth2AuthorizationCode.query.filter_by(
            code=code, client_id=client.client_id).first()
        if auth_code and not auth_code.is_expired():
            return auth_code

    def delete_authorization_code(self, authorization_code):
        db.session.delete(authorization_code)
        db.session.commit()

    def authenticate_user(self, authorization_code):
        return Blogger.query.get(authorization_code.blogger_id)


class RefreshTokenGrant(grants.RefreshTokenGrant):
    def authenticate_refresh_token(self, refresh_token):
        token = OAuth2Token.query.filter_by(refresh_token=refresh_token).first()
        if token and token.is_refresh_token_active():
            return token

    def authenticate_user(self, credential):
        return Blogger.query.get(credential.blogger_id)

    def revoke_old_credential(self, credential):
        credential.revoked = True
        db.session.add(credential)
        db.session.commit()


def query_client(client_id):
    return OAuth2Client.query.filter_by(client_id=client_id).first()


def save_token(token, request):
    if current_user.is_authenticated:
        user_id = current_user.get_user_id()
    else:
        user_id = None
    client = request.client
    tok = OAuth2Token(
        client_id=client.client_id,
        blogger_id=user_id,
        **token
    )
    db.session.add(tok)
    db.session.commit()


authorization = AuthorizationServer(
    query_client=query_client,
    save_token=save_token,
)
require_oauth = ResourceProtector()


@oauth.record
def init_oauth2(state):
    app = state.app
    authorization.init_app(app)

    authorization.register_grant(grants.ClientCredentialsGrant)
    authorization.register_grant(AuthorizationCodeGrant, [CodeChallenge(required=True)])
    authorization.register_grant(RefreshTokenGrant)

    # # support revocation
    # revocation_cls = create_revocation_endpoint(db.session, OAuth2Token)
    # authorization.register_endpoint(revocation_cls)

    bearer_cls = create_bearer_token_validator(db.session, OAuth2Token)
    require_oauth.register_token_validator(bearer_cls())


@oauth.route('/auth', methods=('GET', 'POST'))
def auth():
    if request.method == 'POST':
        if current_user.is_anonymous:
            abort(401, 'must be logged in to authorize client application.')
        if 'authorize' not in request.form:
            abort(401, 'authorization denied. TODO: better UX :)')

        return authorization.create_authorization_response(grant_user=current_user)

    try:
        grant = authorization.validate_consent_request(end_user=current_user)
    except OAuth2Error as error:
        return error.error

    template = 'client-authorize.html'
    if current_user.is_anonymous:
        template = 'client-authorize-anonymous.html'
        session['after_login_redirect'] = request.url
        session.permanent = True

    return render_template(template,
        grant=grant,
        scope_descriptions=SCOPES,
        redirect_uri=request.args['redirect_uri'])


@oauth.route('/token', methods=('POST',))
@csrf.exempt
def issue_token():
    return authorization.create_token_response()


@oauth.route('/revoke', methods=('POST',))
def revoke_token():
    return authorization.create_endpoint_response('revocation')
