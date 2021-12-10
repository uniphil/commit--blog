from base64 import urlsafe_b64encode as b64
from hashlib import sha256
from os import urandom
import urllib.parse


def test_oauth_flow_anonymous(oauth_app, client):
    state = '31zy-J0AN1s2fQ73uTHLtQ'
    code_challenge = 'ElnII37xeSswIXzCQ8eINgEe55WxY1dvp0KU9xlBV8I'
    token_resp = client.get('/oauth/auth', query_string={
        'response_type': 'code',
        'client_id': oauth_app.client_id,
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'redirect_uri': 'http://localhost:33205/oauth/authorized',
        'scope': 'blog',
    })
    assert token_resp.status_code == 200, token_resp.data
    assert b'Log in to continue' in token_resp.data


def test_oauth_flow_authorize(oauth_app, login, gh_blogger):
    app_name = oauth_app.client_metadata["client_name"]
    authorized_url = 'http://localhost:33205/oauth/authorized'

    with login(gh_blogger) as client:
        code_verifier = urandom(48).hex()
        code_challenge = b64(sha256(code_verifier.encode()).digest()).decode().replace('=', '')
        state = urandom(16).hex()

        auth_qs = {
            'response_type': 'code',
            'client_id': oauth_app.client_id,
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'redirect_uri': authorized_url,
            'scope': 'blog',
        }
        auth_resp = client.get('/oauth/auth', query_string=auth_qs)
        assert auth_resp.status_code == 200, auth_resp.data
        assert f'Allow "{app_name}" access?'.encode() in auth_resp.data
        assert b'Authorize' in auth_resp.data

        allow_resp = client.post('/oauth/auth', query_string=auth_qs, data={
            'authorize': '',
            'csrf_token': client.csrf_token,
        })
        assert allow_resp.status_code == 302, allow_resp.data
        redir_url, qs = allow_resp.headers['location'].split('?', 1)
        assert redir_url == authorized_url
        query = dict(urllib.parse.parse_qsl(qs))
        assert query['state'] == state
        assert 'code' in query

        token_resp = client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'client_id': oauth_app.client_id,
            'code': query['code'],
            'code_verifier': code_verifier,
            'redirect_uri': authorized_url,
        })
        assert token_resp.status_code == 200, token_resp.data
        assert b'access_token' in token_resp.data
        assert token_resp.json['expires_in'] > 60  # arbitrary -- some seconds in the future
        assert token_resp.json['scope'] == 'blog'
        assert token_resp.json['token_type'] == 'Bearer'
        access_token = token_resp.json['access_token']

        # check that the token actually works
        resp = client.delete('/api/blog/fake-just-checking-auth', headers={
            'Authorization': f'Bearer {access_token}'
        }, json={ 'github': {'repo': 'not/real' } })
        assert resp.status_code == 404, 'token request allowed (not found)'

        # revoke the token
        revoke_resp = client.post('/oauth/revoke', data={
            'token': access_token,
            'client_id': oauth_app.client_id,
        })
        assert revoke_resp.status_code == 200, revoke_resp.data  # always 200s :(

        # ensure the revoked token no longer works
        resp = client.delete('/api/blog/fake-just-checking-auth', headers={
            'Authorization': f'Bearer {access_token}'
        }, json={ 'github': {'repo': 'not/real' } })
        assert resp.status_code == 401, 'auth fails with revoked token'



def test_oauth_flow_deny(oauth_app, login, gh_blogger):
    app_name = oauth_app.client_metadata["client_name"]
    authorized_url = 'http://localhost:33205/oauth/authorized'

    with login(gh_blogger) as client:
        code_verifier = urandom(48).hex()
        code_challenge = b64(sha256(code_verifier.encode()).digest()).decode().replace('=', '')
        state = urandom(16).hex()

        auth_qs = {
            'response_type': 'code',
            'client_id': oauth_app.client_id,
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'redirect_uri': authorized_url,
            'scope': 'blog',
        }
        auth_resp = client.get('/oauth/auth', query_string=auth_qs)
        assert auth_resp.status_code == 200, auth_resp.data
        assert f'Allow "{app_name}" access?'.encode() in auth_resp.data
        assert b'Authorize' in auth_resp.data

        allow_resp = client.post('/oauth/auth', query_string=auth_qs, data={
            # 'authorize' not present
            'csrf_token': client.csrf_token,
        })
        assert allow_resp.status_code == 401, allow_resp.data
        assert b'authorization denied' in allow_resp.data
