import json

def test_public_announcement(client, init_test_data):
    """Test public announcement endpoint returns successfully."""
    response = client.get('/api/public/announcement')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'has_announcement' in data

def test_protected_route_without_login(client):
    """Test accessing protected route without login redirects or returns 4xx."""
    response = client.get('/dashboard')
    # Since login_required redirects to login
    assert response.status_code == 302
    assert '/login' in response.headers.get('Location', '')

def test_super_admin_route_without_login(client):
    """Test super admin route protection."""
    response = client.get('/super_admin')
    assert response.status_code in [403, 302]
