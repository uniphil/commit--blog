
def test_token_required(client):
    resp = client.put('/api/blog/sha.asdfasdf')
    assert resp.status_code == 401


def test_token(oauth_token, token_login):
    print('got a token', oauth_token)
    with token_login(oauth_token) as client:
        print('got client', client)
        resp = client.delete('/api/blog/sha.asdfasdf', json={
            'github': {'repo': 'not/real' },
        })
        assert resp.status_code == 404
