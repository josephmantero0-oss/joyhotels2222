from app import app, init_db
import unittest
import os
import zipfile
import io
import sqlite3

class BackupTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = 'static/uploads_test_backup'
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        self.app = app.test_client()
        with app.app_context():
            init_db()
            
        # Create a dummy file in uploads
        with open(os.path.join(app.config['UPLOAD_FOLDER'], 'test_img.txt'), 'w') as f:
            f.write('dummy image data')

    def login(self):
        return self.app.post('/login', json={'username': 'najuka', 'password': 'najuka123'})

    def test_backup_restore(self):
        self.login()
        
        # 1. Download Backup
        resp = self.app.get('/api/backup')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'application/zip')
        
        zip_content = resp.data
        
        # Verify Zip Content
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            files = zf.namelist()
            self.assertIn('hotel.db', files)
            # Check relative path for uploads
            # We expect static/uploads_test_backup/test_img.txt to be in there
            # stored as static\uploads_test_backup\test_img.txt or similar depending on os.relpath
            # Let's just check if ANY upload file is there
            upload_files = [f for f in files if 'test_img.txt' in f]
            self.assertTrue(len(upload_files) > 0)

        # 2. Modify System (Delete a room status or something)
        conn = sqlite3.connect('hotel.db')
        c = conn.cursor()
        c.execute("UPDATE rooms SET status='Occupied_Modified' WHERE room_id='101'")
        conn.commit()
        conn.close()
        
        # 3. Restore System
        data = {
            'backup_zip': (io.BytesIO(zip_content), 'backup.zip')
        }
        resp = self.app.post('/api/restore', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.json['success'], True)
        
        # 4. Verify Restoration (Room 101 should be 'available' again, as per init_db default or pre-modification)
        # Note: init_db defaults 101 to 'available'. 
        # The backup was taken when 101 was 'available' (fresh init).
        # We changed it to 'Occupied_Modified'.
        # Restore should bring it back to 'available'.
        
        conn = sqlite3.connect('hotel.db')
        c = conn.cursor()
        c.execute("SELECT status FROM rooms WHERE room_id='101'")
        status = c.fetchone()[0]
        self.assertEqual(status, 'available')
        conn.close()

if __name__ == '__main__':
    unittest.main()
