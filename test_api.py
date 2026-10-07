import sys
sys.path.insert(0, '.')
from app import app

with app.app_context():
    with app.test_client() as client:
        response = client.get('/api/guest/edit-details/33')
        print(f'Status: {response.status_code}')
        if response.status_code == 200:
            print(f'JSON: {response.json}')
        else:
            print(f'Error: {response.data[:200]}')
