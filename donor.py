import os
import secrets
from datetime import date, datetime
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

from models import DonationItem, db
from security import role_required

donor = Blueprint('donor', __name__, url_prefix='/donor')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
ALLOWED_CATEGORIES = {'medicine', 'goods'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
PAGE_SIZE = 9


def allowed_file(filename):
    return bool(filename and '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)


def _image_signature_is_valid(stream, extension):
    """Check the file signature rather than trusting the client-provided MIME type."""
    header = stream.read(12)
    stream.seek(0)
    if extension == 'png':
        return header.startswith(b'\x89PNG\r\n\x1a\n')
    if extension in {'jpg', 'jpeg'}:
        return header.startswith(b'\xff\xd8\xff')
    return False


def _save_image(upload):
    if not upload or not upload.filename:
        return None, None
    if not allowed_file(upload.filename):
        return None, 'Please upload a PNG or JPEG image.'

    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    if size > MAX_IMAGE_BYTES:
        return None, 'Image must be 5 MB or smaller.'
    extension = upload.filename.rsplit('.', 1)[1].lower()
    if not _image_signature_is_valid(upload.stream, extension):
        return None, 'The uploaded file does not appear to be a valid PNG or JPEG image.'

    safe_name = secure_filename(Path(upload.filename).name)
    if not safe_name:
        safe_name = f'image.{extension}'
    filename = f'{current_user.user_id}_{secrets.token_hex(12)}_{safe_name}'
    upload_folder = Path(current_app.config['UPLOAD_FOLDER']).resolve()
    upload_folder.mkdir(parents=True, exist_ok=True)
    upload.stream.seek(0)
    upload.save(str(upload_folder / filename))
    return filename, None


def _remove_image(filename):
    """Delete only files contained in the configured upload directory."""
    if not filename:
        return
    upload_folder = Path(current_app.config['UPLOAD_FOLDER']).resolve()
    candidate = (upload_folder / Path(filename).name).resolve()
    if candidate.parent == upload_folder and candidate.is_file():
        try:
            candidate.unlink()
        except OSError:
            current_app.logger.warning('Could not remove old upload %s', candidate.name)


def _validate_item_form(form):
    item_name = (form.get('item_name') or '').strip()
    category = (form.get('category') or '').strip().lower()
    expiry_raw = (form.get('expiry_date') or '').strip()

    errors = []
    if not 2 <= len(item_name) <= 150:
        errors.append('Item name must be between 2 and 150 characters.')
    if category not in ALLOWED_CATEGORIES:
        errors.append('Choose a valid category: medicine or essential goods.')

    expiry_date = None
    if expiry_raw:
        try:
            expiry_date = datetime.strptime(expiry_raw, '%Y-%m-%d').date()
        except ValueError:
            errors.append('Enter a valid expiry date.')
    if category == 'medicine':
        if expiry_date is None and not expiry_raw:
            errors.append('An expiry date is required for medicine donations.')
        elif expiry_date and expiry_date <= date.today():
            errors.append('Expired medicines cannot be listed. Choose a future expiry date.')
    elif expiry_date and expiry_date < date.today():
        errors.append('Expiry date cannot be in the past.')

    return item_name, category, expiry_date, errors


@donor.route('/dashboard')
@role_required('donor')
def dashboard():
    status = (request.args.get('status') or '').strip().lower()
    category = (request.args.get('category') or '').strip().lower()
    search = (request.args.get('q') or '').strip()[:100]
    page = request.args.get('page', 1, type=int)
    page = max(page or 1, 1)

    query = DonationItem.query.filter_by(donor_id=current_user.user_id)
    if status in {'pending', 'verified', 'rejected', 'claimed'}:
        query = query.filter_by(status=status)
    else:
        status = ''
    if category in ALLOWED_CATEGORIES:
        query = query.filter_by(category=category)
    else:
        category = ''
    if search:
        query = query.filter(DonationItem.item_name.ilike(f'%{search}%'))

    total_count = DonationItem.query.filter_by(donor_id=current_user.user_id).count()
    pending_count = DonationItem.query.filter_by(donor_id=current_user.user_id, status='pending').count()
    verified_count = DonationItem.query.filter_by(donor_id=current_user.user_id, status='verified').count()
    pagination = query.order_by(DonationItem.created_at.desc()).paginate(page=page, per_page=PAGE_SIZE, error_out=False)
    return render_template(
        'donor/dashboard.html', user=current_user, items=pagination.items,
        pagination=pagination, total_count=total_count, pending_count=pending_count,
        verified_count=verified_count, selected_status=status,
        selected_category=category, search_query=search,
    )


@donor.route('/add-item', methods=['GET', 'POST'])
@role_required('donor')
def add_item():
    if request.method == 'POST':
        item_name, category, expiry_date, errors = _validate_item_form(request.form)
        image = request.files.get('image')
        image_path = None
        if image and image.filename:
            image_path, image_error = _save_image(image)
            if image_error:
                errors.append(image_error)

        if errors:
            if image_path:
                _remove_image(image_path)
            for error in errors:
                flash(error, 'danger')
            return render_template('donor/add_item.html'), 400

        item = DonationItem(
            donor_id=current_user.user_id, item_name=item_name, category=category,
            expiry_date=expiry_date, image_path=image_path, status='pending'
        )
        try:
            db.session.add(item)
            db.session.commit()
        except Exception:
            db.session.rollback()
            _remove_image(image_path)
            current_app.logger.exception('Failed to create donation item')
            flash('We could not save your donation. Please try again.', 'danger')
            return render_template('donor/add_item.html'), 500

        flash('Donation submitted successfully and is awaiting admin review.', 'success')
        return redirect(url_for('donor.dashboard'))
    return render_template('donor/add_item.html')


@donor.route('/edit-item/<int:item_id>', methods=['GET', 'POST'])
@role_required('donor')
def edit_item(item_id):
    item = DonationItem.query.get_or_404(item_id)
    if item.donor_id != current_user.user_id:
        flash("You can't edit this item.", 'danger')
        return redirect(url_for('donor.dashboard'))
    if item.status != 'pending':
        flash('Only pending donations can be edited.', 'warning')
        return redirect(url_for('donor.dashboard'))

    if request.method == 'POST':
        item_name, category, expiry_date, errors = _validate_item_form(request.form)
        new_image_path = None
        image = request.files.get('image')
        if image and image.filename:
            new_image_path, image_error = _save_image(image)
            if image_error:
                errors.append(image_error)
        if errors:
            _remove_image(new_image_path)
            for error in errors:
                flash(error, 'danger')
            return render_template('donor/edit_item.html', item=item), 400

        old_image_path = item.image_path
        item.item_name = item_name
        item.category = category
        item.expiry_date = expiry_date
        if new_image_path:
            item.image_path = new_image_path
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            _remove_image(new_image_path)
            current_app.logger.exception('Failed to update donation item %s', item_id)
            flash('We could not update your donation. Please try again.', 'danger')
            return render_template('donor/edit_item.html', item=item), 500
        if new_image_path:
            _remove_image(old_image_path)
        flash('Donation updated successfully.', 'success')
        return redirect(url_for('donor.dashboard'))
    return render_template('donor/edit_item.html', item=item)


@donor.route('/delete-item/<int:item_id>', methods=['POST'])
@role_required('donor')
def delete_item(item_id):
    item = DonationItem.query.get_or_404(item_id)
    if item.donor_id != current_user.user_id:
        flash("You can't delete this item.", 'danger')
        return redirect(url_for('donor.dashboard'))
    if item.status != 'pending':
        flash('Only pending donations can be deleted.', 'warning')
        return redirect(url_for('donor.dashboard'))

    image_path = item.image_path
    try:
        db.session.delete(item)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to delete donation item %s', item_id)
        flash('We could not delete your donation. Please try again.', 'danger')
        return redirect(url_for('donor.dashboard'))
    _remove_image(image_path)
    flash('Donation deleted.', 'info')
    return redirect(url_for('donor.dashboard'))
