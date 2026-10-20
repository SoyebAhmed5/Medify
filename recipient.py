from flask import Blueprint, render_template
from flask_login import current_user
from security import role_required

recipient = Blueprint('recipient', __name__, url_prefix='/recipient')

@recipient.route('/dashboard')
@role_required('ngo', 'hospital')
def dashboard():
    return render_template('recipient/dashboard.html', user=current_user)