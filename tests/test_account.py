import pytest
import flask
from flask_wtf.csrf import generate_csrf


def test_csrf_is_checked(app, client, app_ctx):
    @app.after_request
    def add_csrf_header(response):
        response.headers.set('X-CSRF-Token', generate_csrf())
        return response

    @app.route('/csrf', methods=('GET', 'POST'))
    def csrfed():
        return 'sup'

    no_csrf_resp = client.post('/csrf')
    assert no_csrf_resp.status_code == 400
    assert b'CSRF' in no_csrf_resp.data

    token = client.get('/csrf').headers['X-CSRF-Token']
    print('tok', token)

    assert client.post('/csrf', data={'csrf_token': 'wrong'}).status_code == 400
    assert client.post('/csrf', data={'csrf_token': token}).status_code == 200


@pytest.mark.parametrize(('account_path', 'unauth_status'), (
    ('/account', 401),
    ('/add', 401),
    ('/account/email/new', 401),
    ('/account/name', 401),
    ('/repo/hex/unpost', 401),
    ('/repo/hex/rerender', 401),
))
def test_account_unauthed(client, account_path, unauth_status):
    assert client.get(account_path).status_code == unauth_status
