import dateutil.parser
from flask import (
    Blueprint, redirect, request, session as client_session, url_for
)
from flask_login import login_required, login_user, logout_user
from rauth.service import OAuth2Session, OAuth2Service
from requests.sessions import Session
from requests.utils import default_user_agent
from urllib.parse import urlparse, urljoin

from models import Blogger, CommitPost


gh = Blueprint('gh', __name__)


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


def get_commit_from_api(repo, sha, blogger):
    with gh.AppSession() as session:
        commit_url = f'/repos/{repo.full_name}/git/commits/{sha}'
        print(f'finding commit at {commit_url}')
        resp = session.get(commit_url)

    if resp.status_code == 404:
        return None

    assert resp.ok, 'got error from github'
    gh_commit = resp.json()

    return CommitPost(
        hex=sha,
        message=gh_commit['message'],
        datetime=dateutil.parser.parse(gh_commit['author']['date']),
        repo=repo,
        blogger=blogger,
    )


@gh.record
def init_github(state):
    state.blueprint.oauth = OAuth2Service(
        name='github',
        base_url='https://api.github.com/',
        authorize_url='https://github.com/login/oauth/authorize',
        access_token_url='https://github.com/login/oauth/access_token',
        client_id=state.app.config['GITHUB_CLIENT_ID'],
        client_secret=state.app.config['GITHUB_CLIENT_SECRET'],
        session_obj=GHOAuthSession,
    )
    state.blueprint.AppSession = lambda: GHAppSession(
        'https://api.github.com/',
        client_id=state.app.config['GITHUB_CLIENT_ID'],
        client_secret=state.app.config['GITHUB_CLIENT_SECRET'],
    )
    state.blueprint.get_commit_from_api = get_commit_from_api


@gh.route('/login')
def login():
    next = client_session.get('after_login_redirect', None)

    print(f'NEXT1??? {next=}')

    # referrer = request.referrer
    # if referrer is None or \
    #     referrer.startswith(url_for('pages.hello', _external=True)):
    #     client_session['after_login_redirect'] = None
    # else:
    #     client_session['after_login_redirect'] = referrer
    auth_uri = gh.oauth.get_authorize_url()

    next = client_session.get('after_login_redirect', None)

    print(f'NEXT2??? {next=}')

    return redirect(auth_uri)


@gh.route('/authorized')
def authorized():
    # final stage of oauth login
    next = client_session.get('after_login_redirect', None)

    print(f'NEXT?3?? {next=}')

    if 'code' not in request.args:
        return redirect(next or url_for('pages.hello', auth='sadface'))

    session = gh.oauth.get_auth_session(data={'code': request.args['code']})
    blogger, email_to_ask = Blogger.gh_get_or_create(session)
    client_session['gh_email'] = email_to_ask

    login_user(blogger)

    return redirect(next or url_for('account.dashboard'))


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
