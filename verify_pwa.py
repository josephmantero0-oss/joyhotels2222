import unittest
from app import app
import json

class PWAVerificationTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_manifest_endpoint(self):
        print("\n[Testing] GET /manifest.json")
        response = self.client.get('/manifest.json')
        self.assertEqual(response.status_code, 200)
        
        # Verify it loads valid JSON
        data = json.loads(response.data.decode('utf-8'))
        print("Manifest loaded successfully:")
        print(f"  Name: {data.get('name')}")
        print(f"  Short Name: {data.get('short_name')}")
        print(f"  Display Mode: {data.get('display')}")
        print(f"  Theme Color: {data.get('theme_color')}")
        
        self.assertEqual(data.get('short_name'), 'JoyHotels')
        self.assertEqual(data.get('display'), 'standalone')
        self.assertEqual(data.get('theme_color'), '#10b981')
        self.assertTrue(len(data.get('icons', [])) >= 2)

    def test_service_worker_endpoint(self):
        print("\n[Testing] GET /sw.js")
        response = self.client.get('/sw.js')
        self.assertEqual(response.status_code, 200)
        
        # Verify Headers
        content_type = response.headers.get('Content-Type', '')
        sw_allowed = response.headers.get('Service-Worker-Allowed', '')
        
        print("Service Worker headers verified:")
        print(f"  Content-Type: {content_type}")
        print(f"  Service-Worker-Allowed: {sw_allowed}")
        
        self.assertTrue('javascript' in content_type.lower())
        self.assertEqual(sw_allowed, '/')
        
        # Verify content contains basic lifecycle hooks
        content = response.data.decode('utf-8')
        self.assertTrue('install' in content)
        self.assertTrue('activate' in content)
        self.assertTrue('fetch' in content)

    def test_login_page_pwa_tags(self):
        print("\n[Testing] GET /login PWA head tags")
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        
        # Verify presence of the manifest link and sw registration script
        self.assertTrue('link rel="manifest" href="/manifest.json"' in html)
        self.assertTrue('navigator.serviceWorker.register' in html)
        print("PWA Head tags and service worker register script verified in /login.")

if __name__ == '__main__':
    print("Starting PWA Verification Tests...")
    unittest.main()
