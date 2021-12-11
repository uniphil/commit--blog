from base64 import urlsafe_b64encode
from datetime import datetime
from flask import (
    Blueprint, abort, current_app, redirect, render_template, request,
    session, url_for
)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from wtforms import fields
from models import Blogger, CommitPost, Task
from authlib.integrations.flask_oauth2 import (
    AuthorizationServer as AuthlibFlaskAuthorizationServer,
    ResourceProtector,
)
from authlib.oauth2 import OAuth2Error
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc6750 import BearerTokenValidator as _BearerTokenValidator
from authlib.oauth2.rfc7636 import CodeChallenge
from authlib.oauth2.rfc7009 import RevocationEndpoint
from models import db, Blogger
from models.auth import OAuth2Client, OAuth2AuthorizationCode, OAuth2Token
from wtf import csrf

oauth = Blueprint('oauth', __name__)

SCOPES = {
    'blog': 'Create, view, and update posts',
}


# see commitblog.configure / config['OAUTH2_ACCESS_TOKEN_GENERATOR']
def access_token_generator(_client, grant_type, _user, _scope):
    if grant_type == 'authorization_code':
        return token_urlsafe(64)
    assert False, f'unsupported grant type: {grant_type}'


def token_db_parts(token_string):
    selector, validator = token_string[:42], token_string[42:]
    hashed_validator = urlsafe_b64encode(sha256(validator.encode()).digest())
    return selector, hashed_validator


class AuthorizationServer(AuthlibFlaskAuthorizationServer):
    def __init__(self):
        save_qc = self.query_client
        save_st = self.save_token
        super().__init__()
        self.query_client = save_qc  #als fl ajslkfja slkdfjla ksdjfl
        self.save_token = save_st

    def query_client(self, client_id):
        return OAuth2Client.query.filter_by(client_id=client_id).first()

    def save_token(self, token, request):
        if not request.user:
            abort(401, 'a blogger is required to associate a token')

        db_token = dict(token)

        access_token = db_token.pop('access_token')
        selector, hashed_validator = token_db_parts(access_token)

        tok = OAuth2Token(
            client_id=request.client.client_id,
            blogger=request.user,
            access_token_selector=selector,
            access_token_validator=hashed_validator,
            **db_token)
        db.session.add(tok)
        db.session.commit()


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = ['none']

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
        return authorization_code.blogger


class BearerTokenValidator(_BearerTokenValidator):
    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

    def authenticate_token(self, token_string):
        selector, hashed_validator = token_db_parts(token_string)
        if token := OAuth2Token.query.filter_by(
            access_token_selector=selector
        ).first():
            if compare_digest(hashed_validator, token.access_token_validator):
                return token

        return OAuth2Token.query.filter_by(access_token=token_string).first()

    def request_invalid(self, request):
        return False

    def token_revoked(self, token):
        return token.is_revoked()


def create_revocation_endpoint(session):
    class _RevocationEndpoint(RevocationEndpoint):
        def query_token(self, token_string, _token_type_hint, client):
            selector, validator = token_db_parts(token_string)
            if token := OAuth2Token.query.filter_by(
                client=client,
                access_token_selector=selector,
                access_token_revoked_at=None,
            ).first():
                if compare_digest(validator, token.access_token_validator):
                    return token

        def revoke_token(self, token):
            token.access_token_revoked_at = datetime.now()
            session.add(token)
            session.commit()

    return _RevocationEndpoint


authorization = AuthorizationServer()
require_oauth = ResourceProtector()


@oauth.record
def init_oauth2(state):
    app = state.app
    authorization.init_app(app)

    revocation_cls = create_revocation_endpoint(db.session)
    revocation_cls.CLIENT_AUTH_METHODS = ['none']

    authorization.register_grant(AuthorizationCodeGrant, [CodeChallenge(required=True)])
    authorization.register_endpoint(revocation_cls)

    require_oauth.register_token_validator(BearerTokenValidator(db.session))


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
@csrf.exempt
def revoke_token():
    return authorization.create_endpoint_response('revocation')
