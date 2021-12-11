
def test_add_client_app(app_ctx, login, admin):
    with login(admin) as client:
        client.generate_csrf()
        resp = client.post('/admin/clients', data={
            'csrf_token': client.csrf_token,
            'client_name': 'Some amazing app',
            'client_uri': 'https://example.com',
            'redirect_uri': 'https://example.com/oauth/authorized',
            'allowed_scopes': 'blog',
            'allowed_grant_types': ['authorization_code'],
            'token_auth_method': 'none',
        })
        assert resp.status_code == 200

def test_create_client_app_non_admin(app_ctx, login, gh_blogger):
    with login(gh_blogger) as client:
        client.generate_csrf()
        resp = client.post('/admin/clients', data={
            'csrf_token': client.csrf_token,
            'client_name': 'Some amazing app',
            'client_uri': 'https://example.com',
            'redirect_uri': 'https://example.com/oauth/authorized',
            'allowed_scopes': 'blog',
            'allowed_grant_types': ['authorization_code'],
            'token_auth_method': 'none',
        })
        assert resp.status_code == 401
