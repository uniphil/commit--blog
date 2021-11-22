def test_hello(client):
    response = client.get('/')
    assert b'--get-started' in response.data
