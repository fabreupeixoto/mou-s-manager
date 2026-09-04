import os
import re
import json
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_from_directory, abort, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
PROXY_PREFIX = os.getenv('PROXY_PREFIX', '').rstrip('/')

database_url = os.getenv('DATABASE_URL')
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mou.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'gif', 'txt', 'csv'}

db = SQLAlchemy(app)
scheduler = BackgroundScheduler()

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


@app.context_processor
def inject_prefix():
    mode = (get_setting('INSTITUTION_MODE') or '').strip().lower()
    single = mode == 'single'
    return dict(
        prefix=PROXY_PREFIX,
        own_institution=get_own_institution(),
        SINGLE_MODE=single,
    )


class ProxyPrefixMiddleware:
    def __init__(self, wsgi_app, prefix):
        self.app = wsgi_app
        self.prefix = prefix.rstrip('/')

    def __call__(self, environ, start_response):
        prefix = environ.get('HTTP_X_FORWARDED_PREFIX', self.prefix)
        if prefix:
            environ['SCRIPT_NAME'] = prefix
            path = environ.get('PATH_INFO', '')
            if path.startswith(prefix):
                environ['PATH_INFO'] = path[len(prefix):]
        return self.app(environ, start_response)


# ==================== ROLE HELPERS ====================
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def editor_or_admin(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role not in ('admin', 'editor'):
            flash('Permission denied.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== DATABASE MODELS ====================
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    full_name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class MOU(db.Model):
    __tablename__ = 'mous'

    id = db.Column(db.Integer, primary_key=True)
    portuguese_speaking = db.Column(db.Boolean, default=False)
    asean = db.Column(db.Boolean, default=False)
    signed_date = db.Column(db.Date)
    duration = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)
    renewal_terms = db.Column(db.Text)
    notice_period = db.Column(db.String(100))
    additional_info = db.Column(db.Text)
    mobility_available = db.Column(db.Boolean, default=False)
    mobility_info = db.Column(db.Text)
    other_projects = db.Column(db.Text)
    website_status = db.Column(db.String(50))
    status = db.Column(db.String(50))
    signed_file = db.Column(db.String(200))
    scope = db.Column(db.String(20), default='university')
    last_sync = db.Column(db.DateTime, default=datetime.utcnow)

    partners = db.relationship('MOUPartner', backref='mou', lazy='select',
                               cascade='all, delete-orphan', order_by='MOUPartner.sort_order')

    def primary_partner(self):
        if self.partners:
            return self.partners[0]
        return None

    def display_name(self):
        names = [p.institution for p in self.partners if p.institution]
        if names:
            return ' + '.join(names)
        return f'MOU #{self.id}'

    def to_dict(self):
        primary = self.primary_partner()
        fac_ids = []
        for p in self.partners:
            for f in p.faculties:
                if f.id not in fac_ids:
                    fac_ids.append(f.id)
        return {
            'id': self.id,
            'portuguese_speaking': self.portuguese_speaking,
            'asean': self.asean,
            'scope': self.scope,
            'signed_date': self.signed_date.isoformat() if self.signed_date else None,
            'duration': self.duration,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'renewal_terms': self.renewal_terms,
            'notice_period': self.notice_period,
            'additional_info': self.additional_info,
            'mobility_available': self.mobility_available,
            'mobility_info': self.mobility_info,
            'other_projects': self.other_projects,
            'website_status': self.website_status,
            'status': self.status,
            'signed_file': self.signed_file,
            'institution': primary.institution if primary else None,
            'country': primary.country if primary else None,
            'country_code': primary.country_code if primary else None,
            'institution_number': primary.institution_number if primary else None,
            'contact_person': (primary.signees[0].name if primary and primary.signees else None),
            'contact_email': (primary.signees[0].email if primary and primary.signees else None),
            'partners': [p.to_dict() for p in self.partners],
            'faculties': fac_ids,
        }


class MOUPartner(db.Model):
    __tablename__ = 'mou_partners'

    id = db.Column(db.Integer, primary_key=True)
    mou_id = db.Column(db.Integer, db.ForeignKey('mous.id'), nullable=False)
    institution = db.Column(db.String(500))
    country = db.Column(db.String(100))
    country_code = db.Column(db.String(10))
    institution_number = db.Column(db.Integer)
    sort_order = db.Column(db.Integer, default=0)
    faculty_names = db.Column(db.Text)
    last_sync = db.Column(db.DateTime, default=datetime.utcnow)

    signees = db.relationship('MOUSignee', backref='partner', lazy='select',
                              cascade='all, delete-orphan', order_by='MOUSignee.id')
    faculties = db.relationship('Faculty', secondary='mou_partner_faculties',
                                backref='linked_partners', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'institution': self.institution,
            'country': self.country,
            'country_code': self.country_code,
            'institution_number': self.institution_number,
            'sort_order': self.sort_order,
            'faculty_names': self.faculty_names,
            'faculties': [{'id': f.id, 'name': f.name} for f in self.faculties],
            'signees': [s.to_dict() for s in self.signees],
        }


class MOUSignee(db.Model):
    __tablename__ = 'mou_signees'

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('mou_partners.id'), nullable=False)
    name = db.Column(db.String(300))
    role = db.Column(db.String(300))
    email = db.Column(db.String(300))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'email': self.email,
        }


mou_partner_faculties = db.Table(
    'mou_partner_faculties',
    db.Column('partner_id', db.Integer, db.ForeignKey('mou_partners.id'), primary_key=True),
    db.Column('faculty_id', db.Integer, db.ForeignKey('faculties.id'), primary_key=True)
)


class Setting(db.Model):
    __tablename__ = 'settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_setting(key, default=None):
    try:
        s = db.session.get(Setting, key)
        if s is not None and s.value is not None and s.value != '':
            return s.value
    except Exception:
        pass
    env_val = os.getenv(key, '')
    if env_val != '':
        return env_val
    return default


def set_setting(key, value):
    s = db.session.get(Setting, key)
    if not s:
        s = Setting(key=key)
        db.session.add(s)
    s.value = value or ''


def get_own_institution():
    mode = (get_setting('INSTITUTION_MODE') or '').strip().lower()
    name = (get_setting('OWN_INSTITUTION') or '').strip()
    if mode == 'consortium':
        return ''
    return name


class Faculty(db.Model):
    __tablename__ = 'faculties'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    activities = db.relationship('Activity', backref='faculty', lazy='dynamic')
    accesses = db.relationship('FacultyAccess', backref='faculty', lazy='dynamic')

    @property
    def mous(self):
        return MOU.query.join(MOUPartner, MOUPartner.mou_id == MOU.id)\
            .join(mou_partner_faculties, mou_partner_faculties.c.partner_id == MOUPartner.id)\
            .filter(mou_partner_faculties.c.faculty_id == self.id).distinct().all()


class FacultyAccess(db.Model):
    __tablename__ = 'faculty_accesses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculties.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='faculty_accesses')


activity_mous = db.Table(
    'activity_mous',
    db.Column('activity_id', db.Integer, db.ForeignKey('activities.id'), primary_key=True),
    db.Column('mou_id', db.Integer, db.ForeignKey('mous.id'), primary_key=True)
)


class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculties.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    activity_date = db.Column(db.Date)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documents = db.relationship('Document', backref='activity', lazy='dynamic')
    author = db.relationship('User', foreign_keys=[created_by])
    mous = db.relationship('MOU', secondary=activity_mous, backref='activities', lazy='select')


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    filepath = db.Column(db.String(1000), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', foreign_keys=[uploaded_by])


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ==================== DATE PARSING ====================
def parse_date(date_str):
    if not date_str or date_str.strip() == '':
        return None
    date_str = str(date_str).strip()
    formats = [
        '%d.%m.%Y',
        '%d %b %Y',
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%d-%m-%Y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    if ';' in date_str:
        first_date = date_str.split(';')[0].strip()
        for fmt in formats:
            try:
                return datetime.strptime(first_date, fmt).date()
            except ValueError:
                continue
    return None


# ==================== EMAIL NOTIFICATIONS ====================
def send_expiry_notifications():
    smtp_server = get_setting('SMTP_SERVER')
    smtp_port = get_setting('SMTP_PORT', '587')
    smtp_username = get_setting('SMTP_USERNAME')
    smtp_password = get_setting('SMTP_PASSWORD')
    smtp_from = get_setting('SMTP_FROM')
    smtp_to = get_setting('SMTP_TO')
    if not all([smtp_server, smtp_username, smtp_password, smtp_from, smtp_to]):
        print("Email configuration incomplete. Skipping notifications.")
        return
    today = datetime.now().date()
    periods = {
        '30': ('Within 30 days', today + timedelta(days=30)),
        '60': ('30-60 days', today + timedelta(days=30), today + timedelta(days=60)),
        '90': ('60-90 days', today + timedelta(days=60), today + timedelta(days=90)),
        '180': ('90-180 days', today + timedelta(days=90), today + timedelta(days=180))
    }
    results = {}
    total_count = 0
    for key, config in periods.items():
        if len(config) == 2:
            label, end_date = config
            mous = MOU.query.filter(
                MOU.status == 'ACTIVE',
                MOU.expiry_date != None,
                MOU.expiry_date >= today,
                MOU.expiry_date <= end_date
            ).order_by(MOU.expiry_date).all()
        else:
            label, start_date, end_date = config
            mous = MOU.query.filter(
                MOU.status == 'ACTIVE',
                MOU.expiry_date != None,
                MOU.expiry_date >= start_date,
                MOU.expiry_date <= end_date
            ).order_by(MOU.expiry_date).all()
        if mous:
            results[key] = {'label': label, 'mous': mous}
            total_count += len(mous)
    if total_count == 0:
        print("No MOUs expiring within 180 days. No notification sent.")
        return
    subject = f"MOU Expiry Alert: {total_count} agreement(s) expiring within 6 months"
    body = f"""
    <html>
    <body>
    <h2>MOU Expiry Notification</h2>
    <p>The following MOUs are approaching expiry:</p>
    """
    for key, data in results.items():
        body += f"""
        <h3 style="color: {'#dc3545' if key == '30' else '#fd7e14' if key == '60' else '#ffc107' if key == '90' else '#17a2b8'};">
            {data['label']} ({len(data['mous'])})
        </h3>
        <table border="1" cellpadding="8" style="border-collapse: collapse; margin-bottom: 20px;">
        <tr>
            <th>Institution</th>
            <th>Country</th>
            <th>Expiry Date</th>
            <th>Days Remaining</th>
            <th>Notice Period</th>
        </tr>
        """
        for mou in data['mous']:
            days_remaining = (mou.expiry_date - today).days
            _pp = mou.primary_partner()
            _inst = (_pp.institution if _pp else None) or 'N/A'
            _country = (_pp.country if _pp else None) or 'N/A'
            body += f"""
            <tr>
                <td>{_inst}</td>
                <td>{_country}</td>
                <td>{mou.expiry_date.strftime('%d %b %Y')}</td>
                <td style="{'font-weight: bold; color: #dc3545;' if days_remaining <= 30 else ''}">{days_remaining}</td>
                <td>{mou.notice_period or 'N/A'}</td>
            </tr>
            """
        body += "</table>"
    body += """
    <br>
    <p><strong>Action Required:</strong> Please review and take necessary action for renewal or termination.</p>
    <p><small>This is an automated message from the USJ MOU Dashboard.</small></p>
    </body>
    </html>
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = smtp_to
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        print(f"Notification sent: {total_count} MOUs expiring")
    except Exception as e:
        print(f"Error sending email: {e}")


# ==================== AUTH ROUTES ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('dashboard'))


# ==================== ADMIN USER MANAGEMENT ====================
@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_add_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'viewer')
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()

    if not username or not password:
        flash('Username and password are required.', 'danger')
        return redirect(url_for('admin_users'))

    if len(password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin_users'))

    if role not in ('admin', 'editor', 'viewer'):
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin_users'))

    if User.query.filter_by(username=username).first():
        flash(f'Username "{username}" already exists.', 'danger')
        return redirect(url_for('admin_users'))

    user = User(
        username=username,
        role=role,
        full_name=full_name or username,
        email=email or None
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'User "{username}" created with role "{role}".', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def admin_edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', user.role)
    password = request.form.get('password', '')

    if role not in ('admin', 'editor', 'viewer'):
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin_users'))

    user.full_name = full_name or user.full_name
    user.email = email or None
    user.role = role

    if password:
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('admin_users'))
        user.set_password(password)

    db.session.commit()
    flash(f'User "{user.username}" updated.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_users'))

    db.session.delete(user)
    db.session.commit()
    flash(f'User "{user.username}" deleted.', 'success')
    return redirect(url_for('admin_users'))


# ==================== FACULTY HELPERS ====================
def can_access_faculty(faculty_id):
    if current_user.role == 'admin':
        return True
    return FacultyAccess.query.filter_by(
        user_id=current_user.id, faculty_id=faculty_id
    ).first() is not None


def get_accessible_faculty_ids():
    if current_user.role == 'admin':
        return [f.id for f in Faculty.query.all()]
    return [a.faculty_id for a in FacultyAccess.query.filter_by(user_id=current_user.id).all()]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== ADMIN FACULTY MANAGEMENT ====================
@app.route('/admin/faculties')
@admin_required
def admin_faculties():
    faculties = Faculty.query.order_by(Faculty.name).all()
    users = User.query.order_by(User.username).all()
    return render_template('admin_faculties.html', faculties=faculties, users=users)


@app.route('/admin/faculties/add', methods=['POST'])
@admin_required
def admin_add_faculty():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        flash('Faculty name is required.', 'danger')
        return redirect(url_for('admin_faculties'))
    if Faculty.query.filter_by(name=name).first():
        flash(f'Faculty "{name}" already exists.', 'danger')
        return redirect(url_for('admin_faculties'))
    faculty = Faculty(name=name, description=description or None)
    db.session.add(faculty)
    db.session.commit()
    flash(f'Faculty "{name}" created.', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/faculties/<int:faculty_id>/edit', methods=['POST'])
@admin_required
def admin_edit_faculty(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        flash('Faculty not found.', 'danger')
        return redirect(url_for('admin_faculties'))
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        flash('Faculty name is required.', 'danger')
        return redirect(url_for('admin_faculties'))
    faculty.name = name
    faculty.description = description or None
    db.session.commit()
    flash(f'Faculty "{name}" updated.', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/faculties/<int:faculty_id>/delete', methods=['POST'])
@admin_required
def admin_delete_faculty(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        flash('Faculty not found.', 'danger')
        return redirect(url_for('admin_faculties'))
    db.session.execute(mou_partner_faculties.delete().where(mou_partner_faculties.c.faculty_id == faculty_id))
    FacultyAccess.query.filter_by(faculty_id=faculty_id).delete()
    Activity.query.filter_by(faculty_id=faculty_id).delete()
    db.session.delete(faculty)
    db.session.commit()
    flash(f'Faculty "{faculty.name}" deleted.', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/faculties/<int:faculty_id>/assign', methods=['POST'])
@admin_required
def admin_assign_faculty(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        flash('Faculty not found.', 'danger')
        return redirect(url_for('admin_faculties'))
    user_id = request.form.get('user_id', type=int)
    if not user_id:
        flash('Please select a user.', 'danger')
        return redirect(url_for('admin_faculties'))
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_faculties'))
    existing = FacultyAccess.query.filter_by(user_id=user_id, faculty_id=faculty_id).first()
    if existing:
        flash(f'{user.full_name or user.username} already has access to {faculty.name}.', 'warning')
        return redirect(url_for('admin_faculties'))
    access = FacultyAccess(user_id=user_id, faculty_id=faculty_id)
    db.session.add(access)
    db.session.commit()
    flash(f'{user.full_name or user.username} assigned to {faculty.name}.', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/faculties/<int:faculty_id>/revoke/<int:access_id>', methods=['POST'])
@admin_required
def admin_revoke_faculty(faculty_id, access_id):
    access = db.session.get(FacultyAccess, access_id)
    if not access or access.faculty_id != faculty_id:
        flash('Access record not found.', 'danger')
        return redirect(url_for('admin_faculties'))
    db.session.delete(access)
    db.session.commit()
    flash('Access revoked.', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/mou/<int:mou_id>/assign-faculty', methods=['POST'])
@admin_required
def admin_assign_mou_faculty(mou_id):
    mou = db.session.get(MOU, mou_id)
    if not mou:
        flash('MOU not found.', 'danger')
        return redirect(url_for('dashboard'))
    faculty_id = request.form.get('faculty_id', type=int)
    partner_id = request.form.get('partner_id', type=int)
    partner = db.session.get(MOUPartner, partner_id) if partner_id else None
    if not partner or partner.mou_id != mou_id:
        partner = mou.partners[0] if mou.partners else None
    if not partner:
        flash('MOU has no partners.', 'danger')
        return redirect(url_for('dashboard'))
    if faculty_id:
        faculty = db.session.get(Faculty, faculty_id)
        if faculty and faculty not in partner.faculties:
            partner.faculties.append(faculty)
        mou.scope = 'faculty'
    else:
        partner.faculties = []
        partner.faculty_names = None
        mou.scope = 'university'
    db.session.commit()
    flash('MOU faculty assignment updated.', 'success')
    return redirect(request.referrer or url_for('dashboard'))


SETTING_TEXT_KEYS = ['OWN_INSTITUTION', 'SMTP_SERVER', 'SMTP_PORT', 'SMTP_USERNAME',
                     'SMTP_FROM', 'SMTP_TO', 'SMTP_HOST', 'SMTP_USER', 'SMTP_SENDER']
SETTING_PW_KEYS = ['SMTP_PASSWORD', 'SMTP_PASS']


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        mode = request.form.get('INSTITUTION_MODE')
        set_setting('INSTITUTION_MODE', mode if mode in ('single', 'consortium') else 'consortium')
        for k in SETTING_TEXT_KEYS:
            set_setting(k, (request.form.get(k) or '').strip())
        for k in SETTING_PW_KEYS:
            v = (request.form.get(k) or '').strip()
            if v:
                set_setting(k, v)
        db.session.commit()
        flash('Settings saved.', 'success')
        return redirect(url_for('admin_settings'))
    values = {k: (get_setting(k, '') or '') for k in SETTING_TEXT_KEYS}
    values['INSTITUTION_MODE'] = (get_setting('INSTITUTION_MODE') or
                                  ('single' if values['OWN_INSTITUTION'] else 'consortium'))
    pw_set = {k: bool(get_setting(k)) for k in SETTING_PW_KEYS}
    return render_template('admin_settings.html', values=values, pw_set=pw_set)


@app.route('/admin/settings/test-smtp', methods=['POST'])
@admin_required
def admin_settings_test_smtp():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    which = data.get('which') or 'notifications'
    if not email:
        return jsonify({'success': False, 'message': 'Enter a recipient email address'}), 400
    if which == 'file':
        host = get_setting('SMTP_HOST')
        user = get_setting('SMTP_USER')
        pw = get_setting('SMTP_PASS')
        sender = get_setting('SMTP_SENDER', user)
    else:
        host = get_setting('SMTP_SERVER')
        user = get_setting('SMTP_USERNAME')
        pw = get_setting('SMTP_PASSWORD')
        sender = get_setting('SMTP_FROM', user)
    try:
        port = int(get_setting('SMTP_PORT', '587') or 587)
    except (TypeError, ValueError):
        port = 587
    if not host or not user or not pw:
        return jsonify({'success': False, 'message': 'SMTP settings incomplete (host, username and password are required). Save the settings first.'}), 400
    try:
        msg = MIMEText('This is a test email from the MOU Dashboard settings page.\nIf you received it, SMTP is working correctly.', 'plain')
        msg['From'] = sender
        msg['To'] = email
        msg['Subject'] = 'MOU Dashboard - SMTP test'
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, pw)
            server.sendmail(sender, [email], msg.as_string())
        return jsonify({'success': True, 'message': f'Test email sent to {email}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'SMTP test failed: {e}'}), 500


# ==================== MOU MANAGEMENT ====================
@app.route('/manage')
def manage():
    faculties = [{'id': f.id, 'name': f.name} for f in Faculty.query.order_by(Faculty.name).all()]
    can_manage = current_user.is_authenticated and current_user.role in ('admin', 'editor')
    return render_template('manage.html', base_url=PROXY_PREFIX,
                           can_manage=can_manage,
                           faculties=faculties)


@app.route('/api/mous')
def api_mous_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    if per_page > 200:
        per_page = 200
    search = (request.args.get('search') or '').strip()
    country_search = (request.args.get('country_search') or '').strip()
    status = (request.args.get('status') or '').strip()
    file_filter = (request.args.get('file') or '').strip()
    expiry_filter = (request.args.get('expiry_status') or '').strip()
    sort_by = request.args.get('sort_by', 'institution')
    sort_order = request.args.get('sort_order', 'asc')

    query = MOU.query

    if search:
        like = f'%{search}%'
        query = query.filter(MOU.partners.any(MOUPartner.institution.ilike(like)))
    if country_search:
        query = query.filter(MOU.partners.any(MOUPartner.country.ilike(f'%{country_search}%')))
    if status:
        query = query.filter(MOU.status == status)
    if file_filter == 'has':
        query = query.filter(MOU.signed_file != None, MOU.signed_file != '')
    elif file_filter == 'missing':
        query = query.filter((MOU.signed_file == None) | (MOU.signed_file == ''))

    today = datetime.now().date()

    def expiry_window(days):
        return (MOU.status == 'ACTIVE', MOU.expiry_date != None,
                MOU.expiry_date >= today, MOU.expiry_date <= today + timedelta(days=days))

    if expiry_filter == 'expired':
        active = MOU.status == 'ACTIVE'
        query = query.filter(active, MOU.expiry_date != None, MOU.expiry_date < today)
    elif expiry_filter in ('30', '60', '90', '180'):
        cond = expiry_window(int(expiry_filter))
        query = query.filter(*cond)

    for flag in ('portuguese', 'asean', 'mobility'):
        if request.args.get(flag) == 'true':
            col = {'portuguese': MOU.portuguese_speaking,
                   'asean': MOU.asean,
                   'mobility': MOU.mobility_available}[flag]
            query = query.filter(col == True)
    if request.args.get('recently_signed') == 'true':
        query = query.filter(MOU.signed_date != None).order_by(MOU.signed_date.desc()).limit(5)
    if request.args.get('expired_active') == 'true':
        query = query.filter(MOU.status == 'ACTIVE', MOU.expiry_date != None, MOU.expiry_date < today)
    if request.args.get('expiring_60') == 'true':
        query = query.filter(*expiry_window(60))

    if sort_by in ('institution', 'country'):
        col = {'institution': MOUPartner.institution, 'country': MOUPartner.country}[sort_by]
        query = query.join(MOUPartner, db.and_(MOU.id == MOUPartner.mou_id, MOUPartner.sort_order == 0))
        query = query.order_by(col.is_(None), col.asc() if sort_order == 'asc' else col.desc())
    elif sort_by == 'institution_number':
        query = query.join(MOUPartner, db.and_(MOU.id == MOUPartner.mou_id, MOUPartner.sort_order == 0))
        col = MOUPartner.institution_number
        if sort_order == 'desc':
            query = query.order_by(col.is_(None), col.desc())
        else:
            query = query.order_by(col.is_(None), col.asc())
    elif sort_by in ('status', 'signed_date', 'expiry_date'):
        col = getattr(MOU, sort_by)
        if sort_order == 'desc':
            if col in (MOU.signed_date, MOU.expiry_date):
                query = query.order_by(col.is_(None), col.desc())
            else:
                query = query.order_by(col.desc())
        else:
            if col in (MOU.signed_date, MOU.expiry_date):
                query = query.order_by(col.is_(None), col.asc())
            else:
                query = query.order_by(col.asc())
    else:
        query = query.join(MOUPartner, db.and_(MOU.id == MOUPartner.mou_id, MOUPartner.sort_order == 0))
        query = query.order_by(MOUPartner.institution.desc() if sort_order == 'desc' else MOUPartner.institution.asc())

    total = query.count()

    if request.args.get('recently_signed') == 'true':
        rows = query.all()
    else:
        from math import ceil
        rows = query.offset((page - 1) * per_page).limit(per_page).all()
        pages = max(1, ceil(total / per_page)) if per_page else 1
    dicts = [mou.to_dict() for mou in rows]
    if request.args.get('recently_signed') == 'true':
        return jsonify({'mous': dicts, 'total': total, 'pages': max(1, total)})
    return jsonify({'mous': dicts, 'total': total, 'pages': pages})


def parse_partners(data):
    """Return a list of MOUPartner objects from request JSON data.
    Accepts a 'partners' array; falls back to legacy single-institution fields."""
    raw = data.get('partners')
    if not isinstance(raw, list):
        raw = [{
            'institution': data.get('institution'),
            'country': data.get('country'),
            'country_code': data.get('country_code'),
            'institution_number': data.get('institution_number'),
            'contact_person': data.get('contact_person'),
            'contact_email': data.get('contact_email'),
        }]
    partners = []
    max_num = db.session.query(db.func.max(MOUPartner.institution_number)).scalar() or 0
    auto_seq = max_num + 1
    for idx, p in enumerate(raw):
        if not isinstance(p, dict):
            continue
        inst = (p.get('institution') or '').strip()
        if not inst:
            continue
        partner = MOUPartner()
        partner.institution = inst
        partner.country = (p.get('country') or '').strip() or None
        partner.country_code = (p.get('country_code') or '').strip() or None
        partner.sort_order = idx
        try:
            num = int(p.get('institution_number')) if p.get('institution_number') not in (None, '') else None
        except (TypeError, ValueError):
            num = None
        partner.institution_number = num if num else auto_seq
        auto_seq += 1
        scope = (data.get('scope') or 'university').strip() or 'university'
        if scope == 'faculty':
            fids = p.get('faculty_ids')
            if isinstance(fids, list):
                fac_ids = [int(x) for x in fids if x not in (None, '')]
            else:
                fids = p.get('faculties')
                fac_ids = [int(x.get('id')) for x in fids if isinstance(x, dict) and x.get('id')] if isinstance(fids, list) else []
            if fac_ids:
                partner.faculties = Faculty.query.filter(Faculty.id.in_(fac_ids)).all()
            fnames = p.get('faculty_names')
            if isinstance(fnames, list):
                names = sorted({str(n).strip() for n in fnames if n and str(n).strip()})
                partner.faculty_names = ', '.join(names) if names else None
            elif isinstance(fnames, str) and fnames.strip():
                partner.faculty_names = fnames.strip()
            else:
                partner.faculty_names = None
        else:
            partner.faculties = []
            partner.faculty_names = None
        signees = p.get('signees')
        if isinstance(signees, list):
            for s in signees:
                if not isinstance(s, dict):
                    continue
                name = (s.get('name') or '').strip()
                if not name:
                    continue
                signee = MOUSignee()
                signee.name = name
                signee.role = (s.get('role') or '').strip() or None
                signee.email = (s.get('email') or '').strip() or None
                partner.signees.append(signee)
        partners.append(partner)
    return partners


def apply_mou_fields(mou, data):
    mou.portuguese_speaking = bool(data.get('portuguese_speaking'))
    mou.asean = bool(data.get('asean'))
    mou.duration = (data.get('duration') or '').strip() or None
    mou.renewal_terms = (data.get('renewal_terms') or '').strip() or None
    mou.notice_period = (data.get('notice_period') or '').strip() or None
    mou.additional_info = (data.get('additional_info') or '').strip() or None
    mou.mobility_available = bool(data.get('mobility_available'))
    mou.mobility_info = (data.get('mobility_info') or '').strip() or None
    mou.other_projects = (data.get('other_projects') or '').strip() or None
    mou.website_status = (data.get('website_status') or '').strip() or None
    mou.status = (data.get('status') or 'ACTIVE').strip() or 'ACTIVE'
    mou.scope = (data.get('scope') or 'university').strip() or 'university'
    mou.signed_date = parse_date(data.get('signed_date'))
    mou.expiry_date = parse_date(data.get('expiry_date'))


@app.route('/api/institutions')
@login_required
def api_institutions_list():
    search = (request.args.get('search') or '').strip()
    limit = request.args.get('limit', 8, type=int)
    if limit > 20:
        limit = 20
    query = db.session.query(
        MOUPartner.institution,
        MOUPartner.country,
        MOUPartner.country_code,
        db.func.count(db.func.distinct(MOUPartner.mou_id)).label('mou_count')
    ).filter(
        MOUPartner.institution != None, MOUPartner.institution != ''
    )
    if search:
        query = query.filter(MOUPartner.institution.ilike(f'%{search}%'))
    results = query.group_by(
        MOUPartner.institution, MOUPartner.country, MOUPartner.country_code
    ).order_by(db.func.count(db.func.distinct(MOUPartner.mou_id)).desc()).limit(limit).all()
    return jsonify([
        {'institution': r[0], 'country': r[1], 'country_code': r[2], 'mou_count': r[3]}
        for r in results
    ])


@app.route('/api/mous', methods=['POST'])
@editor_or_admin
def api_mou_create():
    data = request.get_json(silent=True) or {}
    partners = parse_partners(data)
    if not partners:
        return jsonify({'success': False, 'message': 'At least one institution is required'}), 400
    scope = (data.get('scope') or 'university').strip() or 'university'
    if scope == 'faculty' and not any(
        (p.faculties or p.faculty_names) for p in partners
    ):
        return jsonify({'success': False, 'message': 'Faculty-level MOUs require at least one faculty per partner'}), 400
    mou = MOU()
    apply_mou_fields(mou, data)
    mou.partners = partners
    mou.last_sync = datetime.utcnow()
    db.session.add(mou)
    db.session.commit()
    return jsonify({'success': True, 'message': f'MOU "{mou.primary_partner().institution}" created', 'id': mou.id})


@app.route('/api/mous/<int:mou_id>')
def api_mou_get(mou_id):
    mou = db.session.get(MOU, mou_id)
    if not mou:
        return jsonify({'success': False, 'message': 'MOU not found'}), 404
    return jsonify(mou.to_dict())


@app.route('/api/mous/<int:mou_id>', methods=['PUT'])
@editor_or_admin
def api_mou_update(mou_id):
    mou = db.session.get(MOU, mou_id)
    if not mou:
        return jsonify({'success': False, 'message': 'MOU not found'}), 404
    data = request.get_json(silent=True) or {}
    if 'partners' in data or 'institution' in data:
        new_partners = parse_partners(data)
        if not new_partners:
            return jsonify({'success': False, 'message': 'At least one institution is required'}), 400
        scope = (data.get('scope') or 'university').strip() or 'university'
        if scope == 'faculty' and not any(
            (p.faculties or p.faculty_names) for p in new_partners
        ):
            return jsonify({'success': False, 'message': 'Faculty-level MOUs require at least one faculty per partner'}), 400
        mou.partners = new_partners
    apply_mou_fields(mou, data)
    db.session.commit()
    return jsonify({'success': True, 'message': f'MOU updated'})


@app.route('/api/mous/<int:mou_id>', methods=['DELETE'])
@editor_or_admin
def api_mou_delete(mou_id):
    mou = db.session.get(MOU, mou_id)
    if not mou:
        return jsonify({'success': False, 'message': 'MOU not found'}), 404
    data = request.get_json(silent=True) or {}
    password = data.get('password') or ''
    if password != os.getenv('MANAGE_PASSWORD', 'admin123'):
        return jsonify({'success': False, 'message': 'Incorrect password'}), 403
    if mou.signed_file:
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], mou.signed_file)
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
        except OSError:
            pass
    pp = mou.primary_partner()
    title = (pp.institution if pp else None) or f'MOU #{mou.id}'
    db.session.delete(mou)
    db.session.commit()
    return jsonify({'success': True, 'message': f'MOU "{title}" deleted'})


@app.route('/api/upload-file/<int:mou_id>', methods=['POST'])
@editor_or_admin
def api_upload_file(mou_id):
    mou = db.session.get(MOU, mou_id)
    if not mou:
        return jsonify({'success': False, 'message': 'MOU not found'}), 404
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'success': False, 'message': 'File type not allowed'}), 400
    pp = mou.primary_partner()
    num = (pp.institution_number if pp else None) or mou.id
    safe_inst = re.sub(r'[^A-Za-z0-9_]+', '_', (pp.institution if pp else 'MOU')).strip('_')[:60]
    fname = f'{num}_{safe_inst}.{ext}'
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    counter = 1
    while os.path.exists(fpath):
        fname = f'{num}_{safe_inst}_{counter}.{ext}'
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        counter += 1
    file.save(fpath)
    try:
        os.chmod(fpath, 0o644)
    except OSError:
        pass
    if mou.signed_file and mou.signed_file != fname:
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], mou.signed_file)
        try:
            if os.path.isfile(old_path):
                os.remove(old_path)
        except OSError:
            pass
    mou.signed_file = fname
    db.session.commit()
    return jsonify({'success': True, 'message': 'File uploaded', 'filename': fname})


@app.route('/api/send-file-email', methods=['POST'])
@editor_or_admin
def api_send_file_email():
    data = request.get_json(silent=True) or {}
    mou_id = data.get('mou_id')
    email = (data.get('email') or '').strip()
    if not mou_id or not email:
        return jsonify({'success': False, 'message': 'Missing MOU or email'}), 400
    mou = db.session.get(MOU, mou_id)
    if not mou or not mou.signed_file:
        return jsonify({'success': False, 'message': 'MOU or file not found'}), 404
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], mou.signed_file)
    if not os.path.isfile(fpath):
        return jsonify({'success': False, 'message': 'File not on disk'}), 404
    smtp_host = get_setting('SMTP_HOST')
    smtp_port = int(get_setting('SMTP_PORT', '587'))
    smtp_user = get_setting('SMTP_USER')
    smtp_pass = get_setting('SMTP_PASS')
    sender = get_setting('SMTP_SENDER', smtp_user)
    if not smtp_host or not smtp_user:
        return jsonify({'success': False, 'message': 'SMTP not configured'}), 500
    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = email
        pp = mou.primary_partner()
        inst_label = (pp.institution if pp else None) or f'MOU #{mou.id}'
        msg['Subject'] = f'USJ MOU document - {inst_label}'
        body = f'Please find attached the signed MOU document for {inst_label}.'
        msg.attach(MIMEText(body, 'plain'))
        from email.mime.application import MIMEApplication
        with open(fpath, 'rb') as fh:
            part = MIMEApplication(fh.read(), _subtype='octet-stream')
        part.add_header('Content-Disposition', 'attachment', filename=mou.signed_file)
        msg.attach(part)
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, [email], msg.as_string())
        return jsonify({'success': True, 'message': 'Email sent'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Email failed: {str(e)}'}), 500


@app.route('/api/export-pdf')
@login_required
def api_export_pdf():
    try:
        from reports import generate_pdf
        query = MOU.query
        search = (request.args.get('search') or '').strip()
        country_search = (request.args.get('country_search') or '').strip()
        status = (request.args.get('status') or '').strip()
        if search:
            query = query.filter(MOU.partners.any(MOUPartner.institution.ilike(f'%{search}%')))
        if country_search:
            query = query.filter(MOU.partners.any(MOUPartner.country.ilike(f'%{country_search}%')))
        if status:
            query = query.filter(MOU.status == status)
        mous = query.all()
        search_info = ' '.join([x for x in [search, country_search, status] if x]) or 'All MOUs'
        return generate_pdf(mous, search_info=search_info)
    except Exception as e:
        return jsonify({'success': False, 'message': f'PDF export failed: {str(e)}'}), 500


@app.route('/api/export-csv')
@login_required
def api_export_csv():
    import csv
    from io import StringIO
    mous = MOU.query.all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Institution Number', 'Institution', 'Country', 'Status', 'Scope', 'Signed Date', 'Expiry Date',
                     'Duration', 'Notice Period', 'Renewal Terms', 'Additional Info', 'Mobility Info',
                     'Other Projects', 'Website Status', 'Contact Person', 'Contact Email',
                     'Portuguese-Speaking', 'ASEAN', 'Mobility Available', 'Faculties', 'Signed File'])
    for m in mous:
        partners = m.partners or [None]
        for p in partners:
            fac = None
            if p:
                if p.faculties:
                    fac = ', '.join(f.name for f in p.faculties)
                elif p.faculty_names:
                    fac = p.faculty_names
            writer.writerow([
                p.institution_number if p else None,
                p.institution if p else None,
                p.country if p else None,
                m.status,
                m.scope,
                m.signed_date.strftime('%d.%m.%Y') if m.signed_date else '',
                m.expiry_date.strftime('%d.%m.%Y') if m.expiry_date else '',
                m.duration, m.notice_period, m.renewal_terms, m.additional_info, m.mobility_info,
                m.other_projects, m.website_status,
                (p.signees[0].name if p and p.signees else None),
                (p.signees[0].email if p and p.signees else None),
                'Yes' if m.portuguese_speaking else 'No',
                'Yes' if m.asean else 'No',
                'Yes' if m.mobility_available else 'No',
                fac,
                m.signed_file
            ])
    return Response(si.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=mous_export.csv'})


@app.route('/api/export-analytics')
@login_required
def api_export_analytics():
    try:
        from reports import generate_analytics_jpg
        options = (request.args.get('options') or '').split(',')
        info = (request.args.get('info') or '').strip() or 'All MOUs'
        result = generate_analytics_jpg(options, search_info=info)
        if result is None:
            return jsonify({'success': False, 'message': 'No chart options selected'}), 400
        return result
    except Exception as e:
        return jsonify({'success': False, 'message': f'Analytics export failed: {str(e)}'}), 500


# ==================== FACULTY DETAIL PAGE ====================
@app.route('/faculty/<int:faculty_id>')
@login_required
def faculty_detail(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        abort(404)
    if not can_access_faculty(faculty_id):
        flash('You do not have access to this faculty.', 'danger')
        return redirect(url_for('dashboard'))
    def _mou_sort_key(m):
        pp = m.primary_partner()
        return ((pp.country or '') if pp else '', (pp.institution or '') if pp else '')
    mous = sorted(faculty.mous, key=_mou_sort_key)
    university_mous = sorted(
        MOU.query.filter(MOU.scope != 'faculty')
            .join(activity_mous, activity_mous.c.mou_id == MOU.id)
            .join(Activity, Activity.id == activity_mous.c.activity_id)
            .filter(Activity.faculty_id == faculty_id)
            .distinct().all(),
        key=_mou_sort_key)
    activities = faculty.activities.order_by(Activity.activity_date.desc().nullslast(), Activity.created_at.desc()).all()
    doc_count = Document.query.join(Activity).filter(Activity.faculty_id == faculty_id).count()
    return render_template('faculty_detail.html', faculty=faculty, mous=mous,
                           university_mous=university_mous, activities=activities, doc_count=doc_count)


# ==================== FACULTY LIST (for navigation) ====================
@app.route('/faculties')
@login_required
def faculties_list():
    accessible_ids = get_accessible_faculty_ids()
    faculties = Faculty.query.filter(Faculty.id.in_(accessible_ids)).order_by(Faculty.name).all()
    return render_template('faculties_list.html', faculties=faculties)


# ==================== ACTIVITY ROUTES ====================
@app.route('/faculty/<int:faculty_id>/activity/add', methods=['POST'])
@editor_or_admin
def add_activity(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        abort(404)
    if not can_access_faculty(faculty_id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    activity_date = request.form.get('activity_date', '')
    if not title:
        flash('Activity title is required.', 'danger')
        return redirect(url_for('faculty_detail', faculty_id=faculty_id))
    activity = Activity(
        faculty_id=faculty_id,
        title=title,
        description=description or None,
        activity_date=datetime.strptime(activity_date, '%Y-%m-%d').date() if activity_date else None,
        created_by=current_user.id
    )
    for mid in request.form.getlist('mou_ids'):
        try:
            mou = db.session.get(MOU, int(mid))
        except (TypeError, ValueError):
            mou = None
        if mou:
            activity.mous.append(mou)
    db.session.add(activity)
    db.session.commit()
    flash('Activity added.', 'success')
    return redirect(url_for('faculty_detail', faculty_id=faculty_id))


@app.route('/activity/<int:activity_id>/edit', methods=['POST'])
@editor_or_admin
def edit_activity(activity_id):
    activity = db.session.get(Activity, activity_id)
    if not activity:
        abort(404)
    if not can_access_faculty(activity.faculty_id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    activity_date = request.form.get('activity_date', '')
    if not title:
        flash('Activity title is required.', 'danger')
    else:
        activity.title = title
        activity.description = description or None
        activity.activity_date = datetime.strptime(activity_date, '%Y-%m-%d').date() if activity_date else None
        selected_mous = []
        for mid in request.form.getlist('mou_ids'):
            try:
                mou = db.session.get(MOU, int(mid))
            except (TypeError, ValueError):
                mou = None
            if mou:
                selected_mous.append(mou)
        activity.mous = selected_mous
        db.session.commit()
        flash('Activity updated.', 'success')
    return redirect(url_for('faculty_detail', faculty_id=activity.faculty_id))


@app.route('/activity/<int:activity_id>/delete', methods=['POST'])
@editor_or_admin
def delete_activity(activity_id):
    activity = db.session.get(Activity, activity_id)
    if not activity:
        abort(404)
    if not can_access_faculty(activity.faculty_id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))
    faculty_id = activity.faculty_id
    Document.query.filter_by(activity_id=activity_id).delete()
    db.session.delete(activity)
    db.session.commit()
    flash('Activity deleted.', 'success')
    return redirect(url_for('faculty_detail', faculty_id=faculty_id))


# ==================== DOCUMENT ROUTES ====================
@app.route('/activity/<int:activity_id>/upload', methods=['POST'])
@editor_or_admin
def upload_document(activity_id):
    activity = db.session.get(Activity, activity_id)
    if not activity:
        abort(404)
    if not can_access_faculty(activity.faculty_id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('faculty_detail', faculty_id=activity.faculty_id))
    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('faculty_detail', faculty_id=activity.faculty_id))
    if not allowed_file(file.filename):
        flash('File type not allowed.', 'danger')
        return redirect(url_for('faculty_detail', faculty_id=activity.faculty_id))
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(activity.faculty_id), str(activity_id))
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, unique_name)
    file.save(filepath)
    doc = Document(
        activity_id=activity_id,
        filename=filename,
        filepath=f"{activity.faculty_id}/{activity_id}/{unique_name}",
        file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else '',
        file_size=os.path.getsize(filepath),
        uploaded_by=current_user.id
    )
    db.session.add(doc)
    db.session.commit()
    flash(f'File "{filename}" uploaded.', 'success')
    return redirect(url_for('faculty_detail', faculty_id=activity.faculty_id))


@app.route('/document/<int:doc_id>/delete', methods=['POST'])
@editor_or_admin
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    activity = doc.activity
    if not can_access_faculty(activity.faculty_id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], doc.filepath)
    if os.path.exists(full_path):
        os.remove(full_path)
    faculty_id = activity.faculty_id
    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted.', 'success')
    return redirect(url_for('faculty_detail', faculty_id=faculty_id))


@app.route('/uploads/<path:filepath>')
@login_required
def serve_upload(filepath):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filepath)


# ==================== DASHBOARD ROUTES ====================
@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/stats')
def get_stats():
    total = MOU.query.count()
    active = MOU.query.filter_by(status='ACTIVE').count()
    not_active = MOU.query.filter_by(status='NOT ACTIVE').count()
    portuguese_speaking = MOU.query.filter_by(portuguese_speaking=True).count()
    asean = MOU.query.filter_by(asean=True).count()
    mobility = MOU.query.filter_by(mobility_available=True).count()
    today = datetime.now().date()
    expiring_30 = MOU.query.filter(
        MOU.status == 'ACTIVE', MOU.expiry_date != None,
        MOU.expiry_date >= today, MOU.expiry_date <= today + timedelta(days=30)
    ).count()
    expiring_60 = MOU.query.filter(
        MOU.status == 'ACTIVE', MOU.expiry_date != None,
        MOU.expiry_date >= today, MOU.expiry_date <= today + timedelta(days=60)
    ).count()
    expiring_90 = MOU.query.filter(
        MOU.status == 'ACTIVE', MOU.expiry_date != None,
        MOU.expiry_date >= today, MOU.expiry_date <= today + timedelta(days=90)
    ).count()
    expiring_180 = MOU.query.filter(
        MOU.status == 'ACTIVE', MOU.expiry_date != None,
        MOU.expiry_date >= today, MOU.expiry_date <= today + timedelta(days=180)
    ).count()
    return jsonify({
        'total': total, 'active': active, 'not_active': not_active,
        'portuguese_speaking': portuguese_speaking, 'asean': asean, 'mobility': mobility,
        'expiring_30': expiring_30, 'expiring_60': expiring_60,
        'expiring_90': expiring_90, 'expiring_180': expiring_180,
        'last_sync': MOU.query.order_by(MOU.last_sync.desc()).first().last_sync.isoformat() if total > 0 else None
    })


@app.route('/api/mous-by-country')
def get_mous_by_country():
    results = db.session.query(
        MOUPartner.country, db.func.count(db.func.distinct(MOUPartner.mou_id)).label('count')
    ).filter(
        MOUPartner.country != None, MOUPartner.country != ''
    ).group_by(MOUPartner.country).order_by(db.func.count(db.func.distinct(MOUPartner.mou_id)).desc()).all()
    return jsonify([{'country': r[0], 'count': r[1]} for r in results])


@app.route('/api/mous-by-status')
@login_required
def get_mous_by_status():
    results = db.session.query(
        MOU.status, db.func.count(MOU.id).label('count')
    ).group_by(MOU.status).all()
    return jsonify([{'status': r[0], 'count': r[1]} for r in results])


@app.route('/api/expiry-timeline')
@login_required
def get_expiry_timeline():
    today = datetime.now().date()
    one_year_later = today + timedelta(days=365)
    results = db.session.query(
        db.func.to_char(MOU.expiry_date, 'YYYY-MM').label('month'),
        db.func.count(MOU.id).label('count')
    ).filter(
        MOU.status == 'ACTIVE', MOU.expiry_date != None,
        MOU.expiry_date >= today, MOU.expiry_date <= one_year_later
    ).group_by('month').order_by('month').all()
    return jsonify([{'month': r[0], 'count': r[1]} for r in results])


@app.route('/api/map-data')
def get_map_data():
    results = db.session.query(
        MOUPartner.country,
        db.func.count(db.func.distinct(MOUPartner.mou_id)).label('count')
    ).filter(
        MOUPartner.country != None, MOUPartner.country != ''
    ).group_by(MOUPartner.country).all()
    country_institutions = {}
    all_countries = db.session.query(MOUPartner.country).distinct().filter(
        MOUPartner.country != None, MOUPartner.country != ''
    ).all()
    for country_result in all_countries:
        country_name = country_result[0]
        partners = MOUPartner.query.join(MOU).filter(
            MOUPartner.country == country_name
        ).order_by(MOUPartner.institution).all()
        country_institutions[country_name] = [
            {
                'name': p.institution.replace('https://', '').replace('http://', '').strip() if p.institution else 'Unknown',
                'status': p.mou.status,
                'expiry_date': p.mou.expiry_date.isoformat() if p.mou.expiry_date else None
            }
            for p in partners
        ]
    return jsonify([
        {
            'country': r[0], 'total': r[1], 'active': 0,
            'institutions': country_institutions.get(r[0], [])
        }
        for r in results
    ])


@app.route('/api/expiring-soon')
@login_required
def get_expiring_soon():
    days = request.args.get('days', 90, type=int)
    today = datetime.now().date()
    future_date = today + timedelta(days=days)
    mous = MOU.query.filter(
        MOU.status == 'ACTIVE', MOU.expiry_date != None,
        MOU.expiry_date >= today, MOU.expiry_date <= future_date
    ).order_by(MOU.expiry_date).all()
    return jsonify([mou.to_dict() for mou in mous])


@app.route('/api/expiring-by-period')
@login_required
def get_expiring_by_period():
    today = datetime.now().date()
    periods = {
        '30': today + timedelta(days=30),
        '60': today + timedelta(days=60),
        '90': today + timedelta(days=90),
        '180': today + timedelta(days=180)
    }
    result = {}
    for key, end_date in periods.items():
        mous = MOU.query.filter(
            MOU.status == 'ACTIVE', MOU.expiry_date != None,
            MOU.expiry_date >= today, MOU.expiry_date <= end_date
        ).order_by(MOU.expiry_date).all()
        result[key] = [mou.to_dict() for mou in mous]
    return jsonify(result)


@app.route('/upload-csv', methods=['GET', 'POST'])
@admin_required
def upload_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        if not file.filename.endswith('.csv'):
            return jsonify({'success': False, 'message': 'Please upload a CSV file'})
        try:
            import csv
            from io import StringIO
            csv_content = file.read().decode('utf-8')
            reader = csv.reader(StringIO(csv_content))
            rows = list(reader)
            header_idx = 0
            for i, row in enumerate(rows):
                if len(row) > 2 and 'COUNTRY CODE' in row[0]:
                    header_idx = i
                    break
            data_rows = rows[header_idx + 1:]
            imported = 0
            with app.app_context():
                db.session.execute(MOUSignee.__table__.delete())
                db.session.execute(MOUPartner.__table__.delete())
                db.session.execute(mou_partner_faculties.delete())
                db.session.execute(activity_mous.delete())
                MOU.query.delete()
                db.session.commit()
                for row in data_rows:
                    if len(row) < 6 or not row[2].strip():
                        continue
                    try:
                        inst_num = int(row[2]) if row[2].strip() else None
                    except ValueError:
                        inst_num = None
                    if not inst_num:
                        continue
                    mou = MOU()
                    mou.portuguese_speaking = row[3].strip() == '1' if len(row) > 3 else False
                    mou.asean = row[4].strip() == '1' if len(row) > 4 else False
                    mou.signed_date = parse_date(row[6]) if len(row) > 6 else None
                    mou.duration = row[7].strip() if len(row) > 7 else None
                    duration_str = row[7].upper() if len(row) > 7 else ''
                    if 'NOT ACTIVE' in duration_str:
                        mou.status = 'NOT ACTIVE'
                    elif 'ACTIVE' in duration_str:
                        mou.status = 'ACTIVE'
                    else:
                        mou.status = 'UNKNOWN'
                    mou.expiry_date = parse_date(row[8]) if len(row) > 8 else None
                    mou.renewal_terms = row[9].strip() if len(row) > 9 else None
                    mou.notice_period = row[10].strip() if len(row) > 10 else None
                    mou.additional_info = row[11].strip() if len(row) > 11 else None
                    mou.mobility_available = row[12].strip().upper() == 'Y' if len(row) > 12 and row[12].strip() else False
                    mou.mobility_info = row[13].strip() if len(row) > 13 else None
                    mou.other_projects = row[14].strip() if len(row) > 14 else None
                    mou.website_status = row[15].strip() if len(row) > 15 else None
                    mou.last_sync = datetime.utcnow()
                    partner = MOUPartner()
                    partner.country_code = row[0].strip() if row[0].strip() else None
                    partner.country = row[1].strip() if row[1].strip() else None
                    partner.institution_number = inst_num
                    partner.institution = row[5].strip() if len(row) > 5 else None
                    partner.sort_order = 0
                    mou.partners.append(partner)
                    db.session.add(mou)
                    imported += 1
                db.session.commit()
            return jsonify({'success': True, 'message': f'Database rebuilt with {imported} MOUs'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    return render_template('upload_csv.html')


# ==================== SCHEDULER ====================
def init_scheduler():
    scheduler.add_job(
        send_expiry_notifications,
        'cron',
        hour=9,
        id='expiry_notification'
    )
    scheduler.start()


# ==================== SEED ADMIN USER ====================
def seed_admin_user():
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    admin_name = os.getenv('ADMIN_FULL_NAME', 'Administrator')
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@usj.edu.mo')

    if not User.query.filter_by(username=admin_username).first():
        admin = User(
            username=admin_username,
            role='admin',
            full_name=admin_name,
            email=admin_email
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Default admin user created: {admin_username}")
    else:
        print(f"Admin user '{admin_username}' already exists.")


# ==================== INITIALIZATION ====================
def init_db():
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


if PROXY_PREFIX:
    app.wsgi_app = ProxyPrefixMiddleware(app.wsgi_app, PROXY_PREFIX)


if __name__ == '__main__':
    with app.app_context():
        init_db()
        seed_admin_user()
    init_scheduler()
    print("Starting USJ MOU Dashboard...")
    print("Access at: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
