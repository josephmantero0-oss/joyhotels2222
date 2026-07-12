import json

def test_login_success(client, init_test_data):
    """Test successful login returns a redirect to dashboard."""
    response = client.post('/api/login', 
                           json={"username": init_test_data["username"], "password": init_test_data["password"]})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] == True
    assert data["redirect"] == "/dashboard"

def test_login_failure(client, init_test_data):
    """Test login with wrong password."""
    response = client.post('/api/login', 
                           json={"username": init_test_data["username"], "password": "wrongpassword"})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] == False
    assert "Invalid credentials" in data["message"]

def test_registration(client):
    """Test user and hotel registration."""
    payload = {
        "hotel_name": "New Test Hotel",
        "email": "newtest@example.com",
        "phone": "9876543210",
        "username": "newuser",
        "password": "newpassword123",
        "plan": "monthly_hotel",
        "utr_ref": "TXN12345678"
    }
    response = client.post('/api/register', json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["success"] == True
