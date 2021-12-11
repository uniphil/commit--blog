from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from authlib.oauth2.rfc6749 import TokenMixin
from authlib.integrations.sqla_oauth2 import (
    OAuth2ClientMixin,
    OAuth2AuthorizationCodeMixin,
    OAuth2TokenMixin,
)
from sqlalchemy import func
from . import db


class OAuth2Client(db.Model, OAuth2ClientMixin):
    __tablename__ = 'oauth2_client'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(48), index=True, unique=True)  # override to force unique
    dev_id = db.Column(db.Integer, db.ForeignKey('blogger.id', ondelete='CASCADE'))
    dev = db.relationship('Blogger')


class OAuth2AuthorizationCode(db.Model, OAuth2AuthorizationCodeMixin):
    __tablename__ = 'oauth2_code'

    id = db.Column(db.Integer, primary_key=True)
    blogger_id = db.Column(db.Integer, db.ForeignKey('blogger.id', ondelete='CASCADE'), nullable=False)
    blogger = db.relationship('Blogger')


class OAuth2Token(db.Model, TokenMixin):
    __tablename__ = 'oauth2_token'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(48), db.ForeignKey('oauth2_client.client_id', ondelete='CASCADE'))
    blogger_id = db.Column(db.Integer, db.ForeignKey('blogger.id', ondelete='CASCADE'))
    token_type = db.Column(db.String(40))
    scope = db.Column(db.Text, default='')
    issued_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    expires_in = db.Column(db.Integer, nullable=False)  # seconds

    # split token model
    # https://paragonie.com/blog/2017/02/split-tokens-token-based-authentication-protocols-without-side-channels
    access_token_selector = db.Column(db.String(48), unique=True, nullable=False)
    access_token_validator = db.Column(db.String(48), nullable=False)

    access_token_revoked_at = db.Column(db.DateTime, nullable=True)

    blogger = db.relationship('Blogger')
    client = db.relationship('OAuth2Client')

    def check_client(self, client):
        return self.client_id == client.get_client_id()

    def get_scope(self):
        return self.scope

    def get_expires_in(self):
        return self.expires_in

    def get_expires_at(self):
        dt = self.issued_at + timedelta(seconds=self.expires_in)
        expat = int(dt.timestamp())
        return expat

    def is_revoked(self):
        return self.access_token_revoked_at is not None

    def is_expired(self):
        if self.access_token_revoked_at is None:
            return False
        return self.get_expires_at() >= datetime.now()

    def revoke(self):
        self.access_token_revoked_at = datetime.now()
