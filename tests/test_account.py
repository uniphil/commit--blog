import pytest
import flask
from models import Task


def test_csrf_is_checked(app, app_ctx, client):
    @app.route('/csrf', methods=('GET', 'POST'))
    def csrfed():
        return 'sup'

    no_csrf_resp = client.post('/csrf')
    assert no_csrf_resp.status_code == 400
    assert b'CSRF' in no_csrf_resp.data

    assert client.post('/csrf', data={'csrf_token': 'wrong'}).status_code == 400
    resp = client.post('/csrf', data={'csrf_token': client.generate_csrf()})
    assert resp.status_code == 200, resp.data


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


def test_add_gh_email(app_ctx, login, gh_blogger):
    with login(gh_blogger) as client:
        client.generate_csrf()
        no_email = client.post('/account/add-gh-email', data={
            'add_email': '',
            'csrf_token': client.csrf_token,
        })
        assert no_email.status_code == 400
        assert b'missing gh_email address' in no_email.data

        with client.session_transaction() as sess:
            sess['gh_email'] = 'jel@example.com'
        ok_email = client.post('/account/add-gh-email', data={
            'add_email': '',
            'csrf_token': client.csrf_token,
        })
        assert ok_email.status_code == 302
        assert '/account' in ok_email.headers['Location']

    email = gh_blogger.get_email()
    assert email is not None
    assert email.address == 'jel@example.com'
    assert email.confirmed is None

    email_confirms = Task.query \
        .filter(Task.task == 'email') \
        .filter(Task.creator == gh_blogger) \
        .filter(Task.details['recipient'].as_string() == 'jel@example.com') \
        .filter(Task.details['message'].as_string() == 'confirm_email')
    assert email_confirms.count() == 1, 'one email task should be created'


def test_add_email(app_ctx, login, gh_blogger):
    with login(gh_blogger) as client:
        client.get('/account/email/new')
        resp = client.post('/account/email/new', data={
            'address': 'jol@commit--blog.com',
            'csrf_token': client.csrf_token,
        })
        assert resp.status_code == 302
        assert '/account' in resp.headers['Location']

        email = gh_blogger.get_email()
        assert email is not None
        assert email.address == 'jol@commit--blog.com'
        assert email.confirmed is None

        email_confirms = Task.query \
            .filter(Task.task == 'email') \
            .filter(Task.creator == gh_blogger) \
            .filter(Task.details['recipient'].as_string() == 'jol@commit--blog.com') \
            .filter(Task.details['message'].as_string() == 'confirm_email')
        assert email_confirms.count() == 1, 'one email task should be created'

        # resend
        resp = client.post('/accounts/confirm-email/jol@commit--blog.com/resend', data={
            'csrf_token': client.csrf_token,
        })
        assert resp.status_code == 302, resp.data
        assert '/account' in resp.headers['Location']

        email_confirms = Task.query \
            .filter(Task.task == 'email') \
            .filter(Task.creator == gh_blogger) \
            .filter(Task.details['recipient'].as_string() == 'jol@commit--blog.com') \
            .filter(Task.details['message'].as_string() == 'confirm_email')
        assert email_confirms.count() == 2, 'another email task should be created'
