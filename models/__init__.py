from flask_login import AnonymousUserMixin, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import re
import render_message


GH_RAW_BASE = 'https://raw.githubusercontent.com'


db = SQLAlchemy()


def message_parts(commit_message):
    parts = commit_message.split('\n', 1)
    try:
        return parts[0], parts[1]
    except IndexError:
        return parts[0], ''


class AnonymousUser(AnonymousUserMixin):
    """Implement convenient methods that are nice to use on current_user"""

    admin = False
    username = 'anon'

    def is_blogger(self, blogger):
        return False


class Blogger(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    admin = db.Column(db.Boolean, nullable=False, default=lambda: False)
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
    markdown_body = db.Column(db.String, default=lambda: '')
    markdown_renderer = db.Column(
        db.String, nullable=True, default=lambda: render_message.__version__)
    datetime = db.Column(db.DateTime)
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'))
    blogger_id = db.Column(db.Integer, db.ForeignKey('blogger.id'))

    repo = db.relationship('Repo')
    blogger = db.relationship('Blogger', backref=db.backref('commit_posts'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if text := self.get_body():
            user, repo_name = self.repo.full_name.split('/', 1)
            html = render_message.render_github(text, user, repo_name, self.hex)
            self.markdown_body = html

    def get_title(self):
        return message_parts(self.message)[0]

    def get_body(self, markdown=False):
        if markdown:
            return self.markdown_body
        else:
            return message_parts(self.message)[1]

    def can_rerender(self):
        return self.markdown_renderer != render_message.__version__

    def get_rerender_preview(self):
        if text := self.get_body():
            user, repo_name = self.repo.full_name.split('/', 1)
            return render_message.render_github(text, user, repo_name, self.hex)

    def apply_rerender(self):
        html = self.get_rerender_preview()
        if html is None:
            raise ValueError('rerender failed-- no content')
        self.markdown_body = html
        self.markdown_renderer = render_message.__version__

    def __repr__(self):
        return '<CommitPost: {}...>'.format(self.message[:16])
