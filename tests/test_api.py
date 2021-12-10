import pytest
from models import db, CommitPost

@pytest.mark.parametrize(('method', 'api_path', 'no_token_status'), (
    ('put', '/api/blog/shaaaaaaaa', 401),
    ('delete', '/api/blog/shaaaa', 401),
))
def test_token_required(client, method, api_path, no_token_status):
    resp = getattr(client, method)(api_path)
    assert resp.status_code == no_token_status


def test_delete_non_existent(token_for, gh_blogger, token_login):
    with token_login(token_for(gh_blogger)) as client:
        resp = client.delete('/api/blog/sha.asdfasdf', json={
            'github': {'repo': 'not/real' },
        })
        assert resp.status_code == 404


def test_add_commit(app_ctx, fake_github, token_for, gh_blogger, token_login):
    sha = '050c55865e2bb1c96bf0910488d3d6d521eb8f4d'
    repo = 'uniphil/commit--blog'
    token = token_for(gh_blogger)
    with fake_github(), token_login(token) as client:
        resp = client.put(f'/api/blog/{sha}', json={
            'github': {'repo': repo},
        })
        assert resp.status_code == 200, resp.data
        assert sha.encode() in resp.data, 'links to the post in response'

        posts = CommitPost.query.filter(CommitPost.hex == sha)
        assert posts.count() == 1
        assert posts.first().blogger is token.blogger

        # posting again should not make a new post
        resp = client.put(f'/api/blog/{sha}', json={
            'github': {'repo': repo},
        })
        assert resp.status_code == 400, resp.data
        assert b'already blogged' in resp.data
        db.session.rollback()  # the PUT ^^ triggers a db integrity error

        posts = CommitPost.query.filter(CommitPost.hex == sha)
        assert posts.count() == 1

        # also try unposting
        resp = client.delete(f'/api/blog/{sha}', json={
            'github': {'repo': repo},
        })
        assert resp.status_code == 204

        post = CommitPost.query.filter(CommitPost.hex == sha).first()
        assert post is None

        # subsequent unposts just 404
        resp = client.delete(f'/api/blog/{sha}', json={
            'github': {'repo': repo},
        })
        assert resp.status_code == 404


def test_cannot_delete_others_commits(
    app_ctx, fake_github, token_for, blogger, gh_blogger, token_login
):
    sha = '050c55865e2bb1c96bf0910488d3d6d521eb8f4d'
    repo = 'uniphil/commit--blog'

    author_token = token_for(gh_blogger)

    # post as gh blogger
    with fake_github(), token_login(author_token) as client:
        resp = client.put(f'/api/blog/{sha}', json={
            'github': {'repo': repo},
        })
        assert resp.status_code == 200, resp.data

    # attempt to unpost as a different user
    elses_token = token_for(blogger('someone', 'else'))
    with token_login(elses_token) as else_client:
        resp = else_client.delete(f'/api/blog/{sha}', json={
            'github': {'repo': repo},
        })
        assert resp.status_code == 403, resp.data
        assert b'only unpost your own' in resp.data