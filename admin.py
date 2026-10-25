"""Administrative dashboard and donation verification workflow."""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user

from models import ClaimRequest, DonationItem, User, VerificationLog, db
from security import role_required

admin = Blueprint('admin', __name__, url_prefix='/admin')
ALLOWED_DECISIONS = {'verify', 'reject'}
MAX_REMARKS_LENGTH = 2000
PAGE_SIZE = 10


@admin.route('/dashboard')
@role_required('admin')
def dashboard():
    stats = {
        'users': User.query.count(),
        'donations': DonationItem.query.count(),
        'pending': DonationItem.query.filter_by(status='pending').count(),
        'verified': DonationItem.query.filter_by(status='verified').count(),
        'rejected': DonationItem.query.filter_by(status='rejected').count(),
        'claims': ClaimRequest.query.count(),
    }
    pending_items = (DonationItem.query.filter_by(status='pending')
                     .order_by(DonationItem.created_at.asc())
                     .limit(5).all())
    recent_logs = (VerificationLog.query.order_by(VerificationLog.timestamp.desc())
                   .limit(5).all())
    return render_template('admin/dashboard.html', user=current_user, stats=stats,
                           pending_items=pending_items, recent_logs=recent_logs)


@admin.route('/donations')
@role_required('admin')
def donations():
    status = (request.args.get('status') or 'pending').strip().lower()
    if status not in {'pending', 'verified', 'rejected', 'claimed', 'all'}:
        status = 'pending'
    search = (request.args.get('q') or '').strip()[:100]
    page = max(request.args.get('page', 1, type=int) or 1, 1)

    query = DonationItem.query
    if status != 'all':
        query = query.filter_by(status=status)
    if search:
        query = query.filter(DonationItem.item_name.ilike(f'%{search}%'))
    pagination = query.order_by(DonationItem.created_at.desc()).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )
    return render_template('admin/donations.html', user=current_user,
                           items=pagination.items, pagination=pagination,
                           selected_status=status, search_query=search)


@admin.route('/donations/<int:item_id>/review', methods=['POST'])
@role_required('admin')
def review_donation(item_id):
    item = db.session.get(DonationItem, item_id)
    if item is None:
        abort(404)

    decision = (request.form.get('decision') or '').strip().lower()
    remarks = (request.form.get('remarks') or '').strip()
    if decision not in ALLOWED_DECISIONS:
        flash('Choose a valid verification decision.', 'danger')
        return redirect(url_for('admin.donations'))
    if len(remarks) > MAX_REMARKS_LENGTH:
        flash('Remarks must be 2,000 characters or fewer.', 'danger')
        return redirect(url_for('admin.donations'))
    if item.status != 'pending':
        flash('Only pending donations can be reviewed. This item has already been processed.', 'warning')
        return redirect(url_for('admin.donations'))
    if item.category == 'medicine' and (not item.expiry_date or item.expiry_date <= date.today()):
        # Never approve medicine with no valid future expiry date.
        if decision == 'verify':
            flash('This medicine needs a valid future expiry date before it can be verified.', 'danger')
            return redirect(url_for('admin.donations'))

    item.status = 'verified' if decision == 'verify' else 'rejected'
    log = VerificationLog(item_id=item.item_id, verified_by=current_user.user_id,
                          remarks=remarks or None)
    try:
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Admin review failed for donation %s', item_id)
        flash('We could not save this review. Please try again.', 'danger')
        return redirect(url_for('admin.donations'))

    if decision == 'verify':
        flash(f'Donation “{item.item_name}” verified successfully.', 'success')
    else:
        flash(f'Donation “{item.item_name}” rejected.', 'info')
    return redirect(url_for('admin.donations', status='pending'))
