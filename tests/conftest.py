import datetime
import json
import os
import pytest
import time
from contextlib import contextmanager
from commitblog import create_app
from flask import g, session
from flask_login import FlaskLoginClient, login_user
from flask_wtf.csrf import generate_csrf as wtf_generate_csrf
from models import Blogger, db
from models.auth import OAuth2Client, OAuth2Token
from oauth import token_db_parts
from known_git_hosts.github import gh


class BloggerTestClient(FlaskLoginClient):
    def __init__(self, *args, **kwargs):
        self.bearer_token = kwargs.pop("bearer_token", None)
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
        if token := self.bearer_token:
            kwargs.setdefault('headers', {})
            kwargs['headers']['Authorization'] = f'Bearer {token}'

        res = super().open(*args, **kwargs)

        if 'csrf_token' in g:
            self.csrf_token = g.csrf_token

        return res


@contextmanager
def get_fake_github():
    tests_dir = os.path.dirname(__file__)
    def fixture(name):
        with open(os.path.join(tests_dir, f'fixtures/github/{name}.json')) as f:
            return json.load(f)
    _json_responses = {
        '/users/uniphil/events/public': 'get.uniphil.events',
        '/repos/uniphil/commit--blog/git/commits/050c55865e2bb1c96bf0910488d3d6d521eb8f4d': 'get.uniphil.commit',
    }
    class GithubFaker:
        class FakeResponse:
            def __init__(self, url):
                self.url = url
                self.ok = url in _json_responses
                self.status_code = 200 if self.ok else 404
            def json(self):
                assert self.url in _json_responses
                return fixture(_json_responses[self.url])
        def get(self, url):
            return self.FakeResponse(url)
    yield GithubFaker()


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'DATABASE_URL': 'sqlite://',  # in-memory db
        'SECRET_KEY': 'key for tests',
    })
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['WTF_CSRF_SSL_STRICT'] = False

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
def blogger(app_ctx):

    def make_blogger(username, name, **kwargs):
        u = Blogger(username=username, name=name, **kwargs)
        db.session.add(u)
        db.session.commit()
        return u

    return make_blogger


@pytest.fixture
def gh_blogger(blogger):
    return blogger('uniphil', 'Jem')


@pytest.fixture
def admin(blogger):
    return blogger('mod', 'Maud', admin=True)


@pytest.fixture
def login(app):

    @contextmanager
    def login_client(blogger, fresh_login=True):
        with app.test_client(user=blogger, fresh_login=fresh_login) as c:
            yield c

    return login_client


@pytest.fixture
def fake_github():

    @contextmanager
    def github():
        original_app_session = gh.AppSession
        try:
            gh.AppSession = get_fake_github
            yield
        finally:
            gh.AppSession = original_app_session

    return github


@pytest.fixture
def oauth_app(app_ctx):
    client = OAuth2Client(
        client_id='commit--cli',
        client_id_issued_at=int(time.time()),
        client_secret = '')
    client.set_client_metadata({
        'client_name': 'commit--blog cli',
        'client_uri': 'https://commit--blog.com/cli',
        'grant_types': ['authorization_code'],
        'redirect_uris': ['http://localhost:33205/oauth/authorized'],
        'response_types': ['code'],
        'scope': 'blog',
        'token_endpoint_auth_method': 'none',
    })
    db.session.add(client)
    db.session.commit()
    return client


@pytest.fixture
def token_for(oauth_app):

    def seq(_n=[0]):
        _n[0] += 1
        return _n[0]

    def get_new_token(blogger):
        token_string = f'asdfasdf-asdf-{seq()}' * 5
        selector, validator = token_db_parts(token_string)
        token = OAuth2Token(
            client=oauth_app,
            token_type='Bearer',
            access_token_selector=selector,
            access_token_validator=validator,
            scope='blog',
            expires_in=3600,
            blogger=blogger)
        db.session.add(token)
        db.session.commit()
        return token, token_string

    return get_new_token


@pytest.fixture
def token_login(app):

    @contextmanager
    def login_client(token_stuff):
        _token, token_string = token_stuff
        with app.test_client(bearer_token=token_string) as c:
            yield c

    return login_client
