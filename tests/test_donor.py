"""Regression tests for donor-side validation and ownership controls.

Run with: python -m unittest discover -s tests
"""
import os
import tempfile
import unittest
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'unit-test-secret-not-for-production')

from app import create_app
from models import ClaimRequest, DonationItem, User, db
from werkzeug.security import generate_password_hash


class DonorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'test.db'
        self.upload_dir = Path(self.temp_dir.name) / 'uploads'
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'unit-test-secret-not-for-production',
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.db_path.as_posix()}',
            'UPLOAD_FOLDER': str(self.upload_dir),
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.donor = User(name='Donor Test', email='donor@example.test', password_hash=generate_password_hash('long-test-password'), role='donor')
        self.other_donor = User(name='Other Donor', email='other@example.test', password_hash=generate_password_hash('long-test-password'), role='donor')
        db.session.add_all([self.donor, self.other_donor])
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.donor.user_id)
            sess['_fresh'] = True

    def tearDown(self):
        # Release the current SQLAlchemy session.
        db.session.remove()

        # Leave the Flask application context.
        self.ctx.pop()

        # Dispose of pooled database connections.
        with self.app.app_context():
            db.engine.dispose()

        # Delete the temporary database directory.
        self.temp_dir.cleanup()

    def test_medicine_requires_future_expiry(self):
        response = self.client.post('/donor/add-item', data={
            'item_name': 'Paracetamol', 'category': 'medicine', 'expiry_date': ''
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(DonationItem.query.count(), 0)

    def test_rejects_invalid_category(self):
        response = self.client.post('/donor/add-item', data={
            'item_name': 'Blankets', 'category': 'admin', 'expiry_date': ''
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(DonationItem.query.count(), 0)

    def test_valid_goods_donation_is_pending(self):
        response = self.client.post('/donor/add-item', data={
            'item_name': 'Warm blankets', 'category': 'goods', 'expiry_date': ''
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        item = DonationItem.query.one()
        self.assertEqual(item.status, 'pending')
        self.assertEqual(item.donor_id, self.donor.user_id)

    def test_donor_cannot_edit_another_donors_item(self):
        item = DonationItem(donor_id=self.other_donor.user_id, item_name='Blankets', category='goods', status='pending')
        db.session.add(item)
        db.session.commit()
        response = self.client.post(f'/donor/edit-item/{item.item_id}', data={
            'item_name': 'Changed', 'category': 'goods', 'expiry_date': ''
        })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(item)
        self.assertEqual(item.item_name, 'Blankets')

    def test_non_pending_item_cannot_be_deleted(self):
        item = DonationItem(donor_id=self.donor.user_id, item_name='Blankets', category='goods', status='verified')
        db.session.add(item)
        db.session.commit()
        response = self.client.post(f'/donor/delete-item/{item.item_id}')
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(DonationItem, item.item_id))

    def test_rejects_image_with_fake_extension(self):
        fake_image = BytesIO(b'this is not an image')
        response = self.client.post('/donor/add-item', data={
            'item_name': 'Warm blankets', 'category': 'goods', 'expiry_date': '',
            'image': (fake_image, 'photo.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(DonationItem.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
