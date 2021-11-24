import os
import pytest
from contextlib import contextmanager
from commitblog import create_app
from flask import g, session
from flask_login import FlaskLoginClient, login_user
from flask_wtf.csrf import generate_csrf as wtf_generate_csrf
from models import Blogger, db


class BloggerTestClient(FlaskLoginClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csrf_token = None

    def generate_csrf(self):
        """manually force a csrf tokent to be generated

        usually you can just .get() a page with a form and self.csrf_token
        should populate
        """
        with self.application.test_request_context():
            self.csrf_token = wtf_generate_csrf()
            raw_token = session['csrf_token']
        with self.session_transaction() as sess:
            sess['csrf_token'] = raw_token
        return self.csrf_token

    def open(self, *args, **kwargs):
        res = super().open(*args, **kwargs)
        if 'csrf_token' in g:
            self.csrf_token = g.csrf_token
        return res


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'DATABASE_URL': 'sqlite://',  # in-memory db
        'SECRET_KEY': 'key for tests',
    })

    with app.app_context():
        db.create_all()

    app.test_client_class = BloggerTestClient
    yield app

    with app.app_context():
        db.drop_all()


@pytest.fixture
def app_ctx(app):
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def req_ctx(app):
    with app.test_request_context() as ctx:
        yield ctx


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def no_csrf(app):
    app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture
def gh_blogger(app_ctx):
    u = Blogger(username='jim', name='Jem')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def login(app):

    @contextmanager
    def login_client(blogger, fresh_login=True):
        with app.test_client(user=blogger, fresh_login=fresh_login) as c:
            yield c

    return login_client
