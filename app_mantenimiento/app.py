"""
Assisted Living Maintenance App - Backend Server
Flask application for managing maintenance and cleaning reports
With user authentication and automatic community detection
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory, send_file
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json
from services.question_manager import QuestionManager
from services.inspection_service import InspectionService
from services.input_sanitizer import InputSanitizer

# Initialize Flask app
app = Flask(__name__)

# Configuration
# SECRET_KEY resolution order (never falls back to a hardcoded insecure key):
#   1. SECRET_KEY env var (preferred for production).
#   2. A persisted random key in data/.secret_key (stable across restarts so
#      sessions survive a reboot). Generated with secrets.token_hex on first run.
def _resolve_secret_key():
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key
    import secrets
    key_path = os.path.join(os.path.dirname(__file__), 'data', '.secret_key')
    try:
        if os.path.exists(key_path):
            with open(key_path, 'r', encoding='utf-8') as f:
                k = f.read().strip()
            if k:
                return k
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        k = secrets.token_hex(32)
        with open(key_path, 'w', encoding='utf-8') as f:
            f.write(k)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        app.logger.warning('SECRET_KEY env var not set — generated and persisted a '
                           'random key in data/.secret_key. Set SECRET_KEY in the '
                           'environment for full control.')
        return k
    except OSError:
        # Last resort (read-only fs): a per-process random key. Sessions won't
        # survive a restart, but the key is never a known hardcoded value.
        return secrets.token_hex(32)


app.config['SECRET_KEY'] = _resolve_secret_key()
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# --- Session cookie hardening ---
# Secure: only send the cookie over HTTPS (disable for local http via COOKIE_SECURE=0).
# HttpOnly: JS can't read the cookie (mitigates XSS cookie theft).
# SameSite=Lax: the browser won't attach the session cookie to cross-site POST/
#   fetch requests, which blocks the bulk of CSRF, while still allowing top-level
#   navigations (so inspection-report email links still log the user in).
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE', '1') != '0'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== SECURITY MIDDLEWARE ====================
from urllib.parse import urlparse as _urlparse

# Endpoints that legitimately accept cross-origin / no-Origin POSTs. (None today;
# kept for clarity / future webhooks.)
_CSRF_EXEMPT_PATHS = set()


@app.before_request
def _csrf_origin_guard():
    """Lightweight CSRF protection: for state-changing requests, require the
    Origin (or Referer) to match our own host. Combined with the SameSite=Lax
    session cookie, this blocks cross-site forged requests. Same-origin fetch/
    form posts always send a matching Origin, so legitimate traffic is unaffected."""
    if request.method not in ('POST', 'PUT', 'DELETE', 'PATCH'):
        return
    if request.path in _CSRF_EXEMPT_PATHS:
        return
    source = request.headers.get('Origin') or request.headers.get('Referer')
    if not source:
        # No Origin/Referer at all (rare). The SameSite cookie still protects us,
        # so allow rather than break non-browser clients / health checks.
        return
    if _urlparse(source).netloc != request.host:
        app.logger.warning('Blocked cross-origin %s %s from %s',
                           request.method, request.path, source)
        return jsonify({'status': 'error', 'message': 'Cross-origin request blocked'}), 403


@app.after_request
def _security_headers(resp):
    """Standard hardening headers applied to every response."""
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('X-XSS-Protection', '0')
    # HSTS only matters over HTTPS; harmless to always send (browsers ignore on http).
    resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return resp


# --- Simple in-memory login throttle (per IP + username) ---
import time as _time
from collections import defaultdict as _defaultdict
_LOGIN_ATTEMPTS = _defaultdict(list)   # key -> [timestamps of recent failures]
_LOGIN_WINDOW = 300                    # 5 minutes
_LOGIN_MAX_FAILS = 8                   # allowed failures per window


def _login_throttle_key():
    ip = (request.headers.get('X-Forwarded-For', '') or request.remote_addr or '').split(',')[0].strip()
    return ip or 'unknown'


def login_is_throttled():
    key = _login_throttle_key()
    now = _time.time()
    fails = [t for t in _LOGIN_ATTEMPTS[key] if now - t < _LOGIN_WINDOW]
    _LOGIN_ATTEMPTS[key] = fails
    return len(fails) >= _LOGIN_MAX_FAILS


def record_login_failure():
    _LOGIN_ATTEMPTS[_login_throttle_key()].append(_time.time())


def reset_login_failures():
    _LOGIN_ATTEMPTS.pop(_login_throttle_key(), None)


# ---- Automatic cache-busting for static assets ----------------------------
# static_v('theme.css') -> '/static/theme.css?v=<file-mtime>'. The version
# changes by itself whenever the file is saved, so browsers always pick up
# edits without anyone hand-bumping a version string.
_STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')


@app.context_processor
def _inject_static_v():
    def static_v(filename):
        path = os.path.join(_STATIC_DIR, filename)
        try:
            stamp = int(os.path.getmtime(path))
        except OSError:
            stamp = 0
        return url_for('static', filename=filename) + ('?v=%d' % stamp)
    return {'static_v': static_v}


# ==================== SERVICE INITIALIZATION ====================

# Initialize data directory
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_FOLDER, exist_ok=True)

# Seed the live data files from data/seeds/ on first run (e.g. a fresh server).
# Live data files are git-ignored so deploys never overwrite them; the seeds
# ship in git and only populate a file that doesn't exist yet.
import shutil
SEED_FOLDER = os.path.join(DATA_FOLDER, 'seeds')
for _seed_name in ('regions.json', 'questions.json', 'survey_types.json', 'resources.json', 'movein_template.json'):
    _live = os.path.join(DATA_FOLDER, _seed_name)
    _seed = os.path.join(SEED_FOLDER, _seed_name)
    if not os.path.exists(_live) and os.path.exists(_seed):
        try:
            shutil.copyfile(_seed, _live)
        except OSError as _e:
            app.logger.error(f'Could not seed {_seed_name}: {_e}')

# Initialize QuestionManager service
QUESTIONS_FILE = os.path.join(DATA_FOLDER, 'questions.json')
question_manager = QuestionManager(QUESTIONS_FILE)

# Initialize InspectionService
INSPECTIONS_FILE = os.path.join(DATA_FOLDER, 'inspections.json')
from services.inspection_service import InspectionService
inspection_service = InspectionService(INSPECTIONS_FILE, UPLOAD_FOLDER)

# Initialize FileUploadHandler.
# If S3_BUCKET is set, photos are stored privately in S3 and served via signed
# URLs; otherwise they fall back to the local static/uploads folder. This keeps
# the app working in dev / before the bucket is configured.
from services.file_upload_handler import FileUploadHandler
S3_BUCKET = os.environ.get('S3_BUCKET', '').strip() or None
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_URL_EXPIRY = int(os.environ.get('S3_URL_EXPIRY', '3600'))
file_upload_handler = FileUploadHandler(
    UPLOAD_FOLDER,
    s3_bucket=S3_BUCKET,
    region=AWS_REGION,
    url_expiry=S3_URL_EXPIRY,
)
if S3_BUCKET:
    app.logger.info(f'Photo storage: S3 bucket "{S3_BUCKET}" ({AWS_REGION})')
else:
    app.logger.info('Photo storage: local static/uploads (set S3_BUCKET to use S3)')

# Initialize SurveyTypeService
SURVEY_TYPES_FILE = os.path.join(DATA_FOLDER, 'survey_types.json')
from services.survey_type_service import SurveyTypeService
survey_type_service = SurveyTypeService(SURVEY_TYPES_FILE)

# Initialize QuestionFilterService
from services.question_filter import QuestionFilterService
question_filter_service = QuestionFilterService(question_manager, survey_type_service)

# Initialize RegionService (regional structure: leadership + community assignments)
REGIONS_FILE = os.path.join(DATA_FOLDER, 'regions.json')
from services.region_service import RegionService
region_service = RegionService(REGIONS_FILE)

# Initialize ActivityService (audit log) and ProfileService (per-user photo)
ACTIVITY_FILE = os.path.join(DATA_FOLDER, 'activity.json')
from services.activity_service import ActivityService
activity_service = ActivityService(ACTIVITY_FILE)

PROFILES_FILE = os.path.join(DATA_FOLDER, 'profiles.json')
from services.profile_service import ProfileService
profile_service = ProfileService(PROFILES_FILE)

# Admin-created login accounts (persisted; survives restarts/deploys)
USERS_FILE = os.path.join(DATA_FOLDER, 'users.json')
from services.user_service import UserService
user_service = UserService(USERS_FILE)

# Admin-managed resource library (guides, training, FAQ; files or links)
RESOURCES_FILE = os.path.join(DATA_FOLDER, 'resources.json')
from services.resource_service import ResourceService
resource_service = ResourceService(RESOURCES_FILE)

# Admin-uploaded community cover images (shown on dashboard cards + detail panel)
COVERS_FILE = os.path.join(DATA_FOLDER, 'community_covers.json')
from services.community_cover_service import CommunityCoverService
community_cover_service = CommunityCoverService(COVERS_FILE)

# Move-In module: editable checklist template + per-resident move-in records
MOVEIN_TEMPLATE_FILE = os.path.join(DATA_FOLDER, 'movein_template.json')
MOVEINS_FILE = os.path.join(DATA_FOLDER, 'moveins.json')
from services.move_in_service import MoveInTemplateService, MoveInService
movein_template_service = MoveInTemplateService(MOVEIN_TEMPLATE_FILE)
movein_service = MoveInService(MOVEINS_FILE)


def community_slug(name: str) -> str:
    """Mirror of the client-side slug: lowercase, non-alphanumerics -> '_'."""
    import re as _re
    s = (name or '').lower()
    s = _re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')


def cover_url_for(record):
    """Build a usable image URL for a stored cover record (S3 signed or local)."""
    if not record or not record.get('path'):
        return None
    path = record['path']
    if file_upload_handler.use_s3:
        return file_upload_handler.generate_presigned_url(path)
    return url_for('static', filename=f'uploads/{path}')

# Email (Amazon SES). Disabled until MAIL_FROM is set, so the app runs fine
# before email is configured. A failed send never blocks an inspection.
from services.email_service import EmailService
_extra = [a for a in os.environ.get('MAIL_EXTRA_RECIPIENTS', '').split(',') if a.strip()]
email_service = EmailService(
    mail_from=os.environ.get('MAIL_FROM'),
    region=os.environ.get('SES_REGION') or AWS_REGION,
    extra_recipients=_extra,
    app_base_url=os.environ.get('APP_BASE_URL'),
    configuration_set=os.environ.get('SES_CONFIGURATION_SET'),
)
app.logger.info('Email: SES enabled' if email_service.enabled
                else 'Email: disabled (set MAIL_FROM to enable)')

# Runtime-editable settings (email recipient lists, etc.)
SETTINGS_FILE = os.path.join(DATA_FOLDER, 'settings.json')
from services.settings_service import SettingsService
settings_service = SettingsService(SETTINGS_FILE)
# First run: seed subscribers (all-regions) from MAIL_EXTRA_RECIPIENTS if empty.
settings_service.seed_subscribers(_extra)

# Avatars folder for uploaded profile photos
AVATARS_FOLDER = os.path.join(UPLOAD_FOLDER, '..', 'avatars')
AVATARS_FOLDER = os.path.normpath(AVATARS_FOLDER)
os.makedirs(AVATARS_FOLDER, exist_ok=True)



# ==================== DATABASE & USER MANAGEMENT ====================

# Sample user database - In production, use a real database
# Format: {username: {'password_hash': hash, 'community': 'Community Name'}}
USERS_DB = {
    # Admin user
    'admin': {
        'password': 'admin123',
        'community': None  # Admin can see all communities
    },
    
    # Test users - one per community (38 total)
    # Georgia
    'user1': {'password': 'test123', 'community': 'Kelley Place, Enterprise'},
    'user2': {'password': 'test123', 'community': 'Madison Heights Enterprise, Enterprise'},
    'user3': {'password': 'test123', 'community': 'Monark Grove Madison'},
    'user4': {'password': 'test123', 'community': 'Monark Grove Greystone'},
    'user5': {'password': 'test123', 'community': 'Legacy Ridge Trussville, Trussville'},
    'user6': {'password': 'test123', 'community': 'Madison at The Range, Madison'},
    'user7': {'password': 'test123', 'community': 'The Goldton at Athens'},
    'user8': {'password': 'test123', 'community': 'The Goldton at Jones Farm'},
    
    # Florida
    'user9': {'password': 'test123', 'community': 'Madison at Clermont, Clermont'},
    'user10': {'password': 'test123', 'community': 'Madison at Ocoee, Ocoee'},
    'user11': {'password': 'test123', 'community': 'Madison at Oviedo, Oviedo'},
    'user12': {'password': 'test123', 'community': 'The Goldton at Venice, Venice'},
    'user13': {'password': 'test123', 'community': 'The Goldton at St. Petersburg, St. Petersburg'},
    'user14': {'password': 'test123', 'community': 'Lake Howard Heights, Winter Haven'},
    'user15': {'password': 'test123', 'community': 'The Canopy At Beacon Woods'},
    'user16': {'password': 'test123', 'community': 'The Goldton At Lake Nona'},
    
    # North Carolina
    'user17': {'password': 'test123', 'community': 'Madison Heights Evans, Evans'},
    'user18': {'password': 'test123', 'community': 'Legacy at Savannah Quarters, Pooler'},
    'user19': {'password': 'test123', 'community': 'Legacy Reserve at Old Town, Columbus'},
    'user20': {'password': 'test123', 'community': 'Legacy Ridge at Alpharetta, Alpharetta'},
    'user21': {'password': 'test123', 'community': 'Legacy Ridge at Buckhead, Atlanta'},
    'user22': {'password': 'test123', 'community': 'Legacy Ridge at Marietta, Marietta'},
    'user23': {'password': 'test123', 'community': 'The Canopy at Westridge, McDonough'},
    'user24': {'password': 'test123', 'community': 'The Overlook at Suwanee, Suwanee'},
    
    # Ohio
    'user25': {'password': 'test123', 'community': 'Legacy Reserve at Fritz Farm, Lexington'},
    
    # Mississippi
    'user26': {'password': 'test123', 'community': 'The Goldton at Southaven, Southaven'},
    'user27': {'password': 'test123', 'community': 'The Goldton at Adelaide, Starkville'},
    
    # South Carolina
    'user28': {'password': 'test123', 'community': 'Oakview Park, Greenville'},
    'user29': {'password': 'test123', 'community': 'Spring Park, Travelers Rest'},
    'user30': {'password': 'test123', 'community': 'Legacy Reserve Fairview Park, Simpsonville'},
    'user31': {'password': 'test123', 'community': 'Wildcat Senior Living, Summerville'},
    
    # Tennessee
    'user32': {'password': 'test123', 'community': 'The Goldton at Spring Hill, Spring Hill'},
    
    # Texas
    'user33': {'password': 'test123', 'community': 'The Oscar at Georgetown'},
    'user34': {'password': 'test123', 'community': 'The Oscar at Veramendi (June 2026)'},
    
    # Maryland
    'user35': {'password': 'test123', 'community': 'Tribute at Black Hill'},
    'user36': {'password': 'test123', 'community': 'Tribute at Melford'},
    
    # Virginia
    'user37': {'password': 'test123', 'community': 'Tribute at One Loudoun'},
    'user38': {'password': 'test123', 'community': 'Tribute at The Glen'},

    # Transitioning in (DMV)
    'user39': {'password': 'test123', 'community': 'The Goldton at Stuart'}
}

# List of all available communities
ALL_COMMUNITIES = [
    # Georgia
    "Kelley Place, Enterprise",
    "Madison Heights Enterprise, Enterprise",
    "Monark Grove Madison",
    "Monark Grove Greystone",
    "Legacy Ridge Trussville, Trussville",
    "Madison at The Range, Madison",
    "The Goldton at Athens",
    "The Goldton at Jones Farm",
    
    # Florida
    "Madison at Clermont, Clermont",
    "Madison at Ocoee, Ocoee",
    "Madison at Oviedo, Oviedo",
    "The Goldton at Venice, Venice",
    "The Goldton at St. Petersburg, St. Petersburg",
    "Lake Howard Heights, Winter Haven",
    "The Canopy At Beacon Woods",
    "The Goldton At Lake Nona",
    
    # North Carolina
    "Madison Heights Evans, Evans",
    "Legacy at Savannah Quarters, Pooler",
    "Legacy Reserve at Old Town, Columbus",
    "Legacy Ridge at Alpharetta, Alpharetta",
    "Legacy Ridge at Buckhead, Atlanta",
    "Legacy Ridge at Marietta, Marietta",
    "The Canopy at Westridge, McDonough",
    "The Overlook at Suwanee, Suwanee",
    
    # Ohio
    "Legacy Reserve at Fritz Farm, Lexington",
    
    # Mississippi
    "The Goldton at Southaven, Southaven",
    "The Goldton at Adelaide, Starkville",
    
    # South Carolina
    "Oakview Park, Greenville",
    "Spring Park, Travelers Rest",
    "Legacy Reserve Fairview Park, Simpsonville",
    "Wildcat Senior Living, Summerville",
    
    # Tennessee
    "The Goldton at Spring Hill, Spring Hill",
    
    # Texas
    "The Oscar at Georgetown",
    "The Oscar at Veramendi (June 2026)",
    
    # Maryland
    "Tribute at Black Hill",
    "Tribute at Melford",
    
    # Virginia
    "Tribute at One Loudoun",
    "Tribute at The Glen",

    # Transitioning in (DMV)
    "The Goldton at Stuart"
]


# Default password for the auto-generated regional (per-person) accounts.
REGIONAL_DEFAULT_PASSWORD = 'atlas123'


def slugify_name(name):
    """Turn 'Keith Martin' into a stable login slug 'keith.martin'."""
    import re
    s = (name or '').strip().lower()
    s = re.sub(r'[^a-z0-9]+', '.', s)
    return s.strip('.')


def get_regional_accounts():
    """
    Build per-person regional login accounts from the region leadership.
    Each leader becomes an account: username = name slug, covering all the
    communities in their region. Computed live from regions.json so edits to
    leadership are reflected immediately.
    Returns: { username: {'display_name','role','region_id','region_name','communities'} }
    """
    accounts = {}
    for region in region_service.get_all_regions():
        if region.get('id') == 'unassigned':
            continue
        for leader in region.get('leadership', []):
            name = (leader.get('name') or '').strip()
            if not name or name.lower() == 'open':
                continue
            username = slugify_name(name)
            if not username:
                continue
            accounts[username] = {
                'display_name': name,
                'role': 'regional',
                'region_id': region.get('id'),
                'region_name': region.get('name'),
                'communities': list(region.get('communities', []))
            }
    return accounts


def authenticate_user(username, password):
    """
    Authenticate a user and return their account info on success.
    Order: admin/staff (USERS_DB), then per-person regional accounts.
    A hashed override (from change-password) takes precedence over the seed.
    Returns: (True, account_dict) on success, (False, None) on failure.
    account_dict = {role, community, region_id, display_name}
    """
    # --- Admin / staff (community accounts) ---
    if username in USERS_DB:
        user = USERS_DB[username]
        override = profile_service.get_password_hash(username)
        ok = check_password_hash(override, password) if override else (user['password'] == password)
        if not ok:
            return (False, None)
        community = user['community']
        return (True, {
            'role': 'admin' if community is None else 'staff',
            'community': community,
            'region_id': None,
            'display_name': profile_service.get_display_name(username) or username
        })

    # --- Admin-created accounts (users.json) ---
    custom = user_service.get(username)
    if custom:
        override = profile_service.get_password_hash(username)
        stored = custom.get('password_hash')
        if override:
            ok = check_password_hash(override, password)
        elif stored:
            ok = check_password_hash(stored, password)
        else:
            ok = False
        if not ok:
            return (False, None)
        return (True, {
            'role': custom.get('role', 'staff'),
            'community': custom.get('community'),
            'region_id': custom.get('region_id'),
            'display_name': profile_service.get_display_name(username)
                            or custom.get('display_name') or username
        })

    # --- Regional (per-person) accounts ---
    regionals = get_regional_accounts()
    if username in regionals:
        acct = regionals[username]
        override = profile_service.get_password_hash(username)
        ok = check_password_hash(override, password) if override else (password == REGIONAL_DEFAULT_PASSWORD)
        if not ok:
            return (False, None)
        return (True, {
            'role': 'regional',
            'community': None,
            'region_id': acct['region_id'],
            'display_name': acct['display_name']
        })

    return (False, None)


def username_taken(candidate):
    """True if a username already exists in any of the three account sources."""
    if candidate in USERS_DB:
        return True
    if user_service.exists(candidate):
        return True
    if candidate in get_regional_accounts():
        return True
    return False


def generate_unique_username(base):
    """Slug from a name, with a numeric suffix if it collides."""
    base = slugify_name(base) or 'user'
    candidate = base
    n = 2
    while username_taken(candidate):
        candidate = f"{base}{n}"
        n += 1
    return candidate


def generate_password(length=10):
    """Readable strong password (avoids ambiguous characters)."""
    import secrets
    alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def current_role():
    """Resolve the current session role, with backward-compatible fallback."""
    role = session.get('role')
    if role:
        return role
    # Older sessions without an explicit role: infer from community
    return 'admin' if session.get('community') is None else 'staff'


def regional_communities():
    """Communities the current regional user may inspect (their region)."""
    region_id = session.get('region_id')
    if not region_id:
        return []
    region = next((r for r in region_service.get_all_regions() if r.get('id') == region_id), None)
    return list(region.get('communities', [])) if region else []


def region_for_community(community):
    """The region dict that owns this community, or None."""
    for r in region_service.get_all_regions():
        if community in (r.get('communities') or []):
            return r
    return None


def region_leader_emails(community):
    """Email addresses of the leadership for the region that owns this community."""
    r = region_for_community(community)
    if not r:
        return []
    return [(l.get('email') or '').strip()
            for l in (r.get('leadership') or [])
            if (l.get('email') or '').strip()]


def leadership_names():
    """All distinct regional leadership names (people who perform inspections)."""
    names = set()
    for r in region_service.get_all_regions():
        for l in (r.get('leadership') or []):
            n = (l.get('name') or '').strip()
            if n and n.lower() != 'open':
                names.add(n)
    return sorted(names)


def resolve_display_name(username):
    """Friendly name for a username (profile override, regional, or username)."""
    if not username:
        return ''
    name = profile_service.get_display_name(username)
    if name:
        return name
    regionals = get_regional_accounts()
    if username in regionals:
        return regionals[username]['display_name']
    return username


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """
    Decorator to require admin role for routes
    Admin users have community set to None
    Non-admin users are redirected to the inspection form
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Only admins may access admin routes
        if current_role() != 'admin':
            return redirect(url_for('report_form'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== ROUTES ====================

@app.route('/login')
def login():
    """
    Display the login page
    """
    # If already logged in, redirect to report form
    if 'user' in session:
        return redirect(url_for('report_form'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """
    API endpoint for user authentication
    Expects JSON with username and password
    Returns user info and their assigned community
    
    Error Handling:
    - 400: JSON parsing errors or missing fields
    - 401: Invalid credentials
    - 500: Internal server errors
    """
    try:
        # Throttle brute-force attempts (per client IP).
        if login_is_throttled():
            return jsonify({
                'status': 'error',
                'message': 'Too many failed attempts. Please wait a few minutes and try again.'
            }), 429

        # Handle JSON parsing errors
        data = request.get_json(silent=True)

        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format or Content-Type must be application/json'
            }), 400

        # Validate JSON structure
        if not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400

        # Sanitize and validate inputs
        username = InputSanitizer.sanitize_username(data.get('username', ''))
        password = data.get('password', '')
        
        if not username:
            return jsonify({
                'status': 'error',
                'message': 'Username is required'
            }), 400
        
        if not password:
            return jsonify({
                'status': 'error',
                'message': 'Password is required'
            }), 400

        # Authenticate user
        success, account = authenticate_user(username, password)

        if success:
            reset_login_failures()
            # Store user in session
            session['user'] = username
            session['community'] = account['community']
            session['role'] = account['role']
            session['region_id'] = account['region_id']
            session['display_name'] = account['display_name']
            session.permanent = True

            return jsonify({
                'status': 'success',
                'message': 'Login successful',
                'username': username,
                'community': account['community'],
                'role': account['role'],
                'display_name': account['display_name']
            }), 200
        else:
            record_login_failure()
            return jsonify({
                'status': 'error',
                'message': 'Invalid username or password'
            }), 401

    except Exception as e:
        # Log the error for debugging
        app.logger.error(f'Login error: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error during login'
        }), 500


@app.route('/logout')
def logout():
    """
    Logout user and clear session
    """
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    """
    Root route - redirect based on authentication and user type
    
    Behavior:
    - Not authenticated: Redirect to login
    - Admin user: Redirect to dashboard
    - Staff user: Redirect to survey type selection (start new visit)
    """
    if 'user' not in session:
        return redirect(url_for('login'))

    # Route by role
    if current_role() == 'admin':
        return redirect(url_for('dashboard'))
    else:
        # Staff and regional users start a visit via survey type selection
        return redirect(url_for('select_survey_type'))


@app.route('/reporte')
@login_required
def report_form():
    """
    Render the mobile report form (reporte.html)
    This page is designed for maintenance/cleaning staff using mobile devices
    User must be logged in and their community is automatically detected
    
    Survey Type Requirement:
    - User must have selected a survey type before accessing this page
    - If no survey type in session, redirect to survey type selection
    - Admin users are redirected to dashboard (cannot submit inspections)
    """
    # Admins cannot submit inspections
    if current_role() == 'admin':
        return redirect(url_for('dashboard'))

    # Check if survey type is selected
    survey_type_id = session.get('survey_type_id')
    if not survey_type_id:
        # No survey type selected, redirect to selection screen
        return redirect(url_for('select_survey_type'))
    
    # Validate survey type is still valid
    if not survey_type_service.validate_survey_type(survey_type_id):
        # Invalid survey type in session, clear and redirect
        session.pop('survey_type_id', None)
        session.pop('survey_type_name', None)
        return redirect(url_for('select_survey_type'))
    
    # Get survey type details for display
    survey_type = survey_type_service.get_survey_type_by_id(survey_type_id)
    
    # Communities the user may report on: regionals pick from their whole
    # region; staff are locked to their single community.
    if current_role() == 'regional':
        communities = regional_communities()
    else:
        communities = [session.get('community')] if session.get('community') else []

    return render_template('reporte.html',
                         community=session.get('community'),
                         communities=communities,
                         role=current_role(),
                         username=session.get('display_name') or session.get('user'),
                         survey_type=survey_type,
                         survey_type_id=survey_type_id)


@app.route('/select-survey-type')
@login_required
def select_survey_type():
    """
    Render the survey type selection screen
    User must select a survey type before starting an inspection
    Requires login - admin users are redirected to dashboard
    """
    # Admins cannot submit inspections
    if current_role() == 'admin':
        return redirect(url_for('dashboard'))
    
    return render_template('select_survey_type.html',
                         community=session.get('community'),
                         username=session.get('user'))


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Render the admin dashboard (dashboard.html)
    This page is designed for managers to view reports from a desktop
    Admin users can see all communities
    """
    is_admin = session.get('community') is None
    return render_template('dashboard.html',
                         username=session.get('user'),
                         is_admin=is_admin,
                         community=session.get('community'))


@app.route('/api/submit-report', methods=['POST'])
@login_required
def submit_report():
    """
    API endpoint to receive report submissions from the mobile form
    Handles file upload with proper image processing and storage
    
    Error Handling:
    - 400: Missing required fields, invalid file types/sizes
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Get and sanitize form data
        community = InputSanitizer.sanitize_community_name(request.form.get('community', ''))
        location = InputSanitizer.sanitize_string(request.form.get('location', ''), max_length=200)
        condition = InputSanitizer.sanitize_string(request.form.get('condition', ''), max_length=50)
        description = InputSanitizer.sanitize_description(request.form.get('description', ''))
        username = InputSanitizer.sanitize_username(session.get('user', ''))

        # Validate required fields
        if not all([community, location, condition, description]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400

        # Handle file upload
        file_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                # Validate file
                if not allowed_file(file.filename):
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid file type. Only images are allowed.'
                    }), 400

                try:
                    # Create secure filename with timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    file_ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
                    filename = f"{username}_{community}_{timestamp}.{file_ext}"
                    
                    # Create community folder if it doesn't exist
                    community_folder = os.path.join(app.config['UPLOAD_FOLDER'], 
                                                   secure_filename(community))
                    os.makedirs(community_folder, exist_ok=True)
                    
                    # Save file
                    file_path = os.path.join(community_folder, filename)
                    file.save(file_path)
                except IOError as e:
                    app.logger.error(f'File system error saving report photo: {str(e)}')
                    return jsonify({
                        'status': 'error',
                        'message': 'Internal server error: Failed to save photo'
                    }), 500

        # Create report record (in production, save to database)
        report = {
            'id': datetime.now().isoformat(),
            'username': username,
            'community': community,
            'location': location,
            'condition': condition,
            'description': description,
            'photo': file_path,
            'timestamp': datetime.now().isoformat()
        }

        # In production, save to database
        # For now, just return success
        return jsonify({
            'status': 'success',
            'message': 'Report submitted successfully',
            'report': report
        }), 200

    except Exception as e:
        app.logger.error(f'Unexpected error submitting report: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while submitting report'
        }), 500


@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """
    Profile data for the current user: identity, photo, activity stats, and
    recent activity feed.
    """
    try:
        username = session.get('user')
        community = session.get('community')
        role = current_role()
        is_admin = role == 'admin'
        role_label = {'admin': 'Administrator', 'regional': 'Regional', 'staff': 'Staff'}.get(role, 'Staff')

        # Inspection count from the source of truth (historical-safe)
        try:
            all_subs = inspection_service.get_all_submissions()
            inspections = sum(1 for s in all_subs if s.get('username') == username)
        except Exception:
            inspections = 0

        stats = {
            'inspections': inspections,
            'questions_created': activity_service.count_for_user(username, 'question_created'),
            'questions_edited': activity_service.count_for_user(username, 'question_updated'),
            'total_actions': activity_service.count_for_user(username)
        }

        # For regionals, surface their region in place of a single community
        display_community = community
        if role == 'regional':
            display_community = session.get('region_id') and \
                next((r.get('name') for r in region_service.get_all_regions()
                      if r.get('id') == session.get('region_id')), None)
            if display_community:
                display_community = f"{display_community} region"

        return jsonify({
            'status': 'success',
            'username': username,
            'display_name': profile_service.get_display_name(username) or session.get('display_name') or '',
            'community': display_community,
            'is_admin': is_admin,
            'role': role_label,
            'photo': profile_service.get_photo(username),
            'last_active': activity_service.last_active(username),
            'stats': stats,
            'recent_activity': activity_service.get_for_user(username, limit=15)
        }), 200
    except Exception as e:
        app.logger.error(f'Error retrieving profile: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while retrieving profile'}), 500


@app.route('/api/profile/name', methods=['POST'])
@login_required
def update_profile_name():
    """Update the current user's display name."""
    try:
        data = request.get_json(silent=True)
        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({'status': 'error', 'message': 'Request body must be a JSON object'}), 400

        username = session.get('user')
        display_name = InputSanitizer.sanitize_string(data.get('display_name', ''), max_length=80)
        profile_service.set_display_name(username, display_name)
        return jsonify({'status': 'success', 'display_name': display_name}), 200
    except Exception as e:
        app.logger.error(f'Error updating display name: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while updating name'}), 500


@app.route('/api/profile/password', methods=['POST'])
@login_required
def change_password():
    """
    Change the current user's password. Verifies the current password, then
    stores a securely hashed override.
    """
    try:
        data = request.get_json(silent=True)
        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({'status': 'error', 'message': 'Request body must be a JSON object'}), 400

        username = session.get('user')
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')

        if not current_password or not new_password:
            return jsonify({'status': 'error', 'message': 'Current and new password are required'}), 400

        if len(new_password) < 6:
            return jsonify({'status': 'error', 'message': 'New password must be at least 6 characters'}), 400

        # Verify current password
        success, _ = authenticate_user(username, current_password)
        if not success:
            return jsonify({'status': 'error', 'message': 'Current password is incorrect'}), 400

        profile_service.set_password_hash(username, generate_password_hash(new_password))
        activity_service.log(username, 'password_changed', 'Changed account password')
        return jsonify({'status': 'success', 'message': 'Password updated successfully'}), 200
    except Exception as e:
        app.logger.error(f'Error changing password: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while changing password'}), 500


@app.route('/api/profile/photo', methods=['POST'])
@login_required
def upload_profile_photo():
    """Upload/replace the current user's profile photo."""
    try:
        username = InputSanitizer.sanitize_username(session.get('user', ''))
        if 'photo' not in request.files:
            return jsonify({'status': 'error', 'message': 'No photo provided'}), 400

        file = request.files['photo']
        if not file or file.filename == '':
            return jsonify({'status': 'error', 'message': 'No photo provided'}), 400

        if not allowed_file(file.filename):
            return jsonify({'status': 'error', 'message': 'Invalid file type. Only images are allowed.'}), 400

        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{secure_filename(username)}_{timestamp}.{ext}"
        try:
            file.save(os.path.join(AVATARS_FOLDER, filename))
        except IOError as e:
            app.logger.error(f'Error saving avatar: {str(e)}')
            return jsonify({'status': 'error', 'message': 'Failed to save photo'}), 500

        relative_path = f"avatars/{filename}"
        profile_service.set_photo(username, relative_path)
        return jsonify({'status': 'success', 'photo': relative_path}), 200
    except Exception as e:
        app.logger.error(f'Error uploading profile photo: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while uploading photo'}), 500


@app.route('/api/communities')
@login_required
def get_communities():
    """
    Communities the current user is allowed to see on the dashboard:
      - admin: all communities
      - regional: only their region's communities
      - staff: only their assigned community
    """
    role = current_role()
    if role == 'admin':
        # Derive from the regional structure (union, de-duped) so renames and
        # additions made in the Regions view are reflected. Every community
        # lives in a region (including the Unassigned bucket), so this is the
        # complete list. Fall back to the seed list only if regions are empty.
        seen, communities = set(), []
        for r in region_service.get_all_regions():
            for c in r.get('communities', []):
                if c not in seen:
                    seen.add(c); communities.append(c)
        if not communities:
            communities = list(ALL_COMMUNITIES)
    elif role == 'regional':
        communities = regional_communities()
    else:
        communities = [session.get('community')] if session.get('community') else []
    return jsonify({'status': 'success', 'communities': communities}), 200


@app.route('/api/community-covers', methods=['GET'])
@login_required
def list_community_covers():
    """Return { slug: image_url } for every community that has a cover image.
    Any logged-in user can read these (covers are shown on the cards)."""
    out = {}
    for slug, rec in community_cover_service.get_all().items():
        url = cover_url_for(rec)
        if url:
            out[slug] = url
    return jsonify({'status': 'success', 'covers': out}), 200


@app.route('/api/communities/cover', methods=['POST'])
@require_admin
def upload_community_cover():
    """Admin-only: upload (or replace) a community's cover image.
    Multipart form: name (community name) + photo (image file)."""
    try:
        name = InputSanitizer.sanitize_community_name(request.form.get('name', ''))
        if not name:
            return jsonify({'status': 'error', 'message': 'Community name is required'}), 400
        if 'photo' not in request.files:
            return jsonify({'status': 'error', 'message': 'No image provided'}), 400

        file = request.files['photo']
        valid, msg = file_upload_handler.validate_file(file)
        if not valid:
            return jsonify({'status': 'error', 'message': msg}), 400

        slug = community_slug(name)
        # Remove any previous cover object (extension may differ) before saving.
        old = community_cover_service.get(slug)
        if old and old.get('path'):
            file_upload_handler.delete_file(old['path'])

        rel_path, stored = file_upload_handler.save_cover(file, slug)
        rec = community_cover_service.set(slug, name, rel_path, stored)
        activity_service.log(session.get('user'), 'community_cover_set',
                             f'Set cover image for "{name}"')
        return jsonify({'status': 'success', 'slug': slug,
                        'url': cover_url_for(rec)}), 200
    except Exception as e:
        app.logger.error(f'Error uploading community cover: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while uploading cover'}), 500


@app.route('/api/communities/cover', methods=['DELETE'])
@require_admin
def delete_community_cover():
    """Admin-only: remove a community's cover image (reverts to the gradient)."""
    try:
        data = request.get_json(silent=True) or {}
        name = InputSanitizer.sanitize_community_name(data.get('name', ''))
        if not name:
            return jsonify({'status': 'error', 'message': 'Community name is required'}), 400
        slug = community_slug(name)
        rec = community_cover_service.delete(slug)
        if rec and rec.get('path'):
            file_upload_handler.delete_file(rec['path'])
        activity_service.log(session.get('user'), 'community_cover_removed',
                             f'Removed cover image for "{name}"')
        return jsonify({'status': 'success', 'slug': slug}), 200
    except Exception as e:
        app.logger.error(f'Error removing community cover: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while removing cover'}), 500


# ==================== MOVE-IN MODULE ====================

def _movein_progress(rec, item_ids):
    """Count completed items for a move-in record against the template items."""
    comps = rec.get('completions') or {}
    done = sum(1 for iid in item_ids if (comps.get(iid) or {}).get('done'))
    total = len(item_ids)
    return done, total


def _movein_attachment_url(entry):
    path = (entry or {}).get('attachment_path')
    if not path:
        return None
    if file_upload_handler.use_s3:
        return file_upload_handler.generate_presigned_url(path, download_name=entry.get('attachment_name'))
    return url_for('static', filename=f'uploads/{path}')


@app.route('/api/moveins', methods=['GET'])
@login_required
def list_moveins():
    """List all move-ins with computed progress (any logged-in user)."""
    item_ids = movein_template_service.all_item_ids()
    out = []
    for rec in movein_service.get_all():
        done, total = _movein_progress(rec, item_ids)
        out.append({
            'id': rec.get('id'),
            'resident_name': rec.get('resident_name'),
            'community': rec.get('community'),
            'target_date': rec.get('target_date'),
            'status': rec.get('status', 'active'),
            'created_at': rec.get('created_at'),
            'done': done, 'total': total,
        })
    return jsonify({'status': 'success', 'moveins': out}), 200


@app.route('/api/moveins', methods=['POST'])
@login_required
def create_movein():
    """Create a new resident move-in record."""
    data = request.get_json(silent=True) or {}
    resident = InputSanitizer.sanitize_string(data.get('resident_name', ''), max_length=120)
    community = InputSanitizer.sanitize_community_name(data.get('community', ''))
    target_date = InputSanitizer.sanitize_string(data.get('target_date', ''), max_length=20)
    if not resident:
        return jsonify({'status': 'error', 'message': 'Resident name is required'}), 400
    if not community:
        return jsonify({'status': 'error', 'message': 'Community is required'}), 400
    rec = movein_service.create(resident, community, target_date, created_by=session.get('user'))
    activity_service.log(session.get('user'), 'movein_created', f'Started move-in for {resident} ({community})')
    return jsonify({'status': 'success', 'movein': rec}), 200


@app.route('/api/moveins/<mv_id>', methods=['GET'])
@login_required
def get_movein(mv_id):
    """Return a move-in record merged with the template (phases + items + completion)."""
    rec = movein_service.get(mv_id)
    if rec is None:
        return jsonify({'status': 'error', 'message': 'Move-in not found'}), 404
    template = movein_template_service.get_template()
    comps = rec.get('completions') or {}
    item_ids = []
    for ph in template['phases']:
        for it in ph.get('items', []):
            item_ids.append(it['id'])
            entry = comps.get(it['id']) or {}
            it['done'] = bool(entry.get('done'))
            it['date'] = entry.get('date', '')
            it['initials'] = entry.get('initials', '')
            it['attachment_name'] = entry.get('attachment_name')
            it['attachment_url'] = _movein_attachment_url(entry)
    done, total = _movein_progress(rec, item_ids)
    return jsonify({'status': 'success', 'movein': rec, 'template': template,
                    'done': done, 'total': total}), 200


@app.route('/api/moveins/<mv_id>/item', methods=['POST'])
@login_required
def update_movein_item(mv_id):
    """Update one checklist item's completion (done / date / initials)."""
    data = request.get_json(silent=True) or {}
    item_id = InputSanitizer.sanitize_string(data.get('item_id', ''), max_length=60)
    if not item_id:
        return jsonify({'status': 'error', 'message': 'item_id is required'}), 400
    rec = movein_service.update_item(
        mv_id, item_id,
        done=data.get('done'),
        date=data.get('date'),
        initials=data.get('initials'),
        updated_by=session.get('user'))
    if rec is None:
        return jsonify({'status': 'error', 'message': 'Move-in not found'}), 404
    return jsonify({'status': 'success'}), 200


@app.route('/api/moveins/<mv_id>/item/attachment', methods=['POST'])
@login_required
def upload_movein_attachment(mv_id):
    """Attach a file (signed form, etc.) to a checklist item."""
    item_id = InputSanitizer.sanitize_string(request.form.get('item_id', ''), max_length=60)
    if not item_id:
        return jsonify({'status': 'error', 'message': 'item_id is required'}), 400
    if movein_service.get(mv_id) is None:
        return jsonify({'status': 'error', 'message': 'Move-in not found'}), 404
    if 'file' not in request.files or not request.files['file'].filename:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400
    file = request.files['file']
    try:
        rel, name = file_upload_handler.save_movein_attachment(file, mv_id, item_id)
        movein_service.set_attachment(mv_id, item_id, rel, name)
        entry = (movein_service.get(mv_id).get('completions') or {}).get(item_id, {})
        return jsonify({'status': 'success', 'attachment_name': name,
                        'attachment_url': _movein_attachment_url(entry)}), 200
    except Exception as e:
        app.logger.error(f'Error uploading move-in attachment: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while uploading attachment'}), 500


@app.route('/api/moveins/<mv_id>', methods=['DELETE'])
@login_required
def delete_movein(mv_id):
    """Delete a move-in record (and best-effort remove its attachments)."""
    rec = movein_service.get(mv_id)
    if rec is None:
        return jsonify({'status': 'error', 'message': 'Move-in not found'}), 404
    for entry in (rec.get('completions') or {}).values():
        if entry.get('attachment_path'):
            file_upload_handler.delete_file(entry['attachment_path'])
    movein_service.delete(mv_id)
    activity_service.log(session.get('user'), 'movein_deleted', f"Deleted move-in for {rec.get('resident_name')}")
    return jsonify({'status': 'success'}), 200


@app.route('/api/moveins/<mv_id>/status', methods=['POST'])
@login_required
def set_movein_status(mv_id):
    """Mark a move-in active / completed / archived."""
    data = request.get_json(silent=True) or {}
    status = (data.get('status') or '').strip().lower()
    if status not in ('active', 'completed', 'archived'):
        return jsonify({'status': 'error', 'message': 'Invalid status'}), 400
    if movein_service.set_status(mv_id, status) is None:
        return jsonify({'status': 'error', 'message': 'Move-in not found'}), 404
    return jsonify({'status': 'success'}), 200


@app.route('/api/moveins/template', methods=['GET'])
@login_required
def get_movein_template():
    return jsonify({'status': 'success', 'template': movein_template_service.get_template()}), 200


@app.route('/api/moveins/template', methods=['POST'])
@require_admin
def save_movein_template():
    """Admin-only: replace the move-in checklist template (phases + items)."""
    data = request.get_json(silent=True) or {}
    phases = data.get('phases')
    if not isinstance(phases, list):
        return jsonify({'status': 'error', 'message': 'phases must be a list'}), 400
    tmpl = movein_template_service.save_template(phases)
    activity_service.log(session.get('user'), 'movein_template_saved', 'Updated move-in checklist template')
    return jsonify({'status': 'success', 'template': tmpl}), 200


@app.route('/api/users', methods=['GET'])
@login_required
def list_users():
    """Admin-only: list admin-created login accounts."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    return jsonify({'status': 'success', 'users': user_service.get_all()}), 200


@app.route('/api/users', methods=['POST'])
@login_required
def create_user():
    """
    Admin-only: create a new login account.
    Body: { display_name, role: admin|staff|regional, community?, region_id? }
    The username is generated from the name; a strong password is generated and
    returned ONCE (it is stored only as a hash).
    """
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403

    data = request.get_json(silent=True) or {}
    display_name = (data.get('display_name') or '').strip()
    role = (data.get('role') or '').strip().lower()
    community = (data.get('community') or '').strip() or None
    region_id = (data.get('region_id') or '').strip() or None
    email = (data.get('email') or '').strip() or None

    if not display_name:
        return jsonify({'status': 'error', 'message': 'Name is required'}), 400
    if role not in ('admin', 'staff', 'regional'):
        return jsonify({'status': 'error', 'message': 'Invalid role'}), 400

    if role == 'staff':
        valid = set()
        for r in region_service.get_all_regions():
            valid.update(r.get('communities', []))
        valid.update(ALL_COMMUNITIES)
        if not community or community not in valid:
            return jsonify({'status': 'error', 'message': 'A valid community is required for staff'}), 400
        region_id = None
    elif role == 'regional':
        valid_ids = {r.get('id') for r in region_service.get_all_regions() if r.get('id') != 'unassigned'}
        if not region_id or region_id not in valid_ids:
            return jsonify({'status': 'error', 'message': 'A valid region is required for a regional account'}), 400
        community = None
    else:  # admin
        community = None
        region_id = None

    username = generate_unique_username(display_name)
    password = generate_password()
    user_service.create(
        username=username,
        display_name=display_name,
        role=role,
        password_hash=generate_password_hash(password),
        community=community,
        region_id=region_id,
        created_by=session.get('user'),
        email=email,
    )
    try:
        activity_service.log(session.get('user'), 'user_created',
                             f'Created {role} account for {display_name}',
                             meta={'username': username})
    except Exception:
        pass

    # Emails (best-effort; never block account creation):
    #  - welcome the new user with their login (if an email was given)
    #  - alert the configured admin-notify list
    role_label = {'admin': 'Administrator', 'staff': 'Staff', 'regional': 'Regional'}.get(role, role)
    emailed = False
    if email_service.enabled:
        try:
            if email:
                ok, _ = email_service.send_welcome(email, display_name, username, password, role_label)
                emailed = bool(ok)
            admin_notify = settings_service.get_email_settings().get('admin_notify', [])
            if admin_notify:
                email_service.send_new_user_alert(admin_notify, display_name, username,
                                                  role_label, session.get('user'))
        except Exception as e:
            app.logger.error(f'User-creation email step failed: {e}')

    return jsonify({
        'status': 'success',
        'message': 'User created',
        'username': username,
        'password': password,
        'display_name': display_name,
        'role': role,
        'emailed': emailed,
    }), 201


@app.route('/api/users/<username>/reset-password', methods=['POST'])
@login_required
def reset_user_password(username):
    """Admin-only: generate a new password for a created user (returned once)."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    if not user_service.exists(username):
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    password = generate_password()
    user_service.set_password_hash(username, generate_password_hash(password))
    # Clear any per-user profile override so the new password takes effect.
    try:
        profile_service.set_password_hash(username, '')
    except Exception:
        pass
    return jsonify({'status': 'success', 'username': username, 'password': password}), 200


@app.route('/api/users/<username>', methods=['DELETE'])
@login_required
def delete_user(username):
    """Admin-only: remove a created user. Cannot remove yourself."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    if username == session.get('user'):
        return jsonify({'status': 'error', 'message': 'You cannot delete your own account'}), 400
    if not user_service.delete(username):
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    return jsonify({'status': 'success', 'message': 'User removed'}), 200


RESOURCE_ALLOWED_EXT = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                        'txt', 'csv', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'zip'}


@app.route('/standards/print')
@login_required
def standards_print():
    """Printable one-pager of all standards (text + pass criteria + guideline)."""
    questions = question_manager.get_all_active_questions()
    return render_template('standards_print.html', questions=questions)


@app.route('/standards/pdf')
@login_required
def standards_pdf():
    """Server-generated PDF of all standards — reliable download (no browser print)."""
    import os
    import html as _html
    from io import BytesIO
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    ListFlowable, ListItem, Image, HRFlowable)

    questions = question_manager.get_all_active_questions()
    navy = colors.HexColor('#00285c')
    styles = getSampleStyleSheet()
    s_title = ParagraphStyle('t', parent=styles['Title'], textColor=navy, fontSize=18, alignment=0, spaceAfter=2)
    s_sub = ParagraphStyle('s', parent=styles['Normal'], textColor=colors.HexColor('#6b7280'), fontSize=10, spaceAfter=14)
    s_h = ParagraphStyle('h', parent=styles['Heading2'], textColor=navy, fontSize=13, spaceBefore=14, spaceAfter=4)
    s_lbl = ParagraphStyle('l', parent=styles['Normal'], textColor=colors.HexColor('#94a3b8'), fontSize=8, spaceBefore=6, spaceAfter=2)
    s_body = ParagraphStyle('b', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#334155'))

    def esc(x):
        return _html.escape(str(x or '')).replace('\n', '<br/>')

    story = []
    logo = os.path.join(os.path.dirname(__file__), 'static', 'atlas-logo.png')
    if os.path.exists(logo):
        try:
            img = Image(logo)
            ratio = img.imageWidth / float(img.imageHeight)
            img.drawHeight = 0.45 * inch
            img.drawWidth = 0.45 * inch * ratio
            img.hAlign = 'LEFT'
            story += [img, Spacer(1, 8)]
        except Exception:
            pass
    story.append(Paragraph('Inspection Standards &amp; Pass Criteria', s_title))
    story.append(Paragraph('Atlas Senior Living &mdash; Communities Standards', s_sub))

    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"{i}. {esc(q.get('text'))}", s_h))
        crit = q.get('pass_criteria') or []
        if crit:
            story.append(Paragraph('TO PASS, MUST INCLUDE', s_lbl))
            story.append(ListFlowable(
                [ListItem(Paragraph(esc(c), s_body), leftIndent=12) for c in crit],
                bulletType='bullet', start='•', leftIndent=16))
        g = (q.get('interpretive_guideline') or '').strip()
        if g:
            story.append(Paragraph('INTERPRETIVE GUIDELINE', s_lbl))
            story.append(Paragraph(esc(g), s_body))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width='100%', color=colors.HexColor('#eef1f6')))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title='Atlas Standards',
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    from flask import Response
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment; filename="Atlas-Standards.pdf"'})


@app.route('/api/resources', methods=['GET'])
@login_required
def list_resources():
    """Everyone signed in can see the resource library."""
    items = []
    for r in resource_service.get_all():
        items.append({
            'id': r.get('id'),
            'title': r.get('title'),
            'description': r.get('description'),
            'kind': r.get('kind'),
            'url': r.get('url') if r.get('kind') == 'link' else None,
            'filename': r.get('filename') if r.get('kind') == 'file' else None,
            'created_at': r.get('created_at'),
        })
    return jsonify({'status': 'success', 'resources': items, 'is_admin': current_role() == 'admin'}), 200


@app.route('/api/resources', methods=['POST'])
@login_required
def add_resource():
    """Admin-only: add a resource (an uploaded file or an external link)."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403

    title = InputSanitizer.sanitize_string(request.form.get('title', ''), max_length=120).strip()
    description = InputSanitizer.sanitize_string(request.form.get('description', ''), max_length=400).strip()
    kind = (request.form.get('kind') or '').strip().lower()
    if not title:
        return jsonify({'status': 'error', 'message': 'Title is required'}), 400

    if kind == 'link':
        url = (request.form.get('url') or '').strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            return jsonify({'status': 'error', 'message': 'Enter a valid http(s) link'}), 400
        rec = resource_service.add(title, description, 'link', url=url, created_by=session.get('user'))
    elif kind == 'file':
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify({'status': 'error', 'message': 'Choose a file to upload'}), 400
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in RESOURCE_ALLOWED_EXT:
            return jsonify({'status': 'error', 'message': f'Unsupported file type .{ext}'}), 400
        try:
            rel, stored = file_upload_handler.save_resource(file)
        except Exception as e:
            app.logger.error(f'Resource upload failed: {e}')
            return jsonify({'status': 'error', 'message': 'Could not save the file'}), 500
        rec = resource_service.add(title, description, 'file', file_path=rel,
                                   filename=secure_filename(file.filename),
                                   content_type=file.mimetype, created_by=session.get('user'))
    else:
        return jsonify({'status': 'error', 'message': 'Invalid resource type'}), 400

    return jsonify({'status': 'success', 'id': rec['id']}), 201


@app.route('/api/resources/<resource_id>', methods=['DELETE'])
@login_required
def delete_resource(resource_id):
    """Admin-only: remove a resource (and its file)."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    rec = resource_service.delete(resource_id)
    if not rec:
        return jsonify({'status': 'error', 'message': 'Resource not found'}), 404
    if rec.get('kind') == 'file' and rec.get('file_path'):
        file_upload_handler.delete_file(rec['file_path'])
    return jsonify({'status': 'success'}), 200


@app.route('/api/resources/<resource_id>/attach', methods=['POST'])
@login_required
def attach_resource(resource_id):
    """Admin-only: attach a file or link to an existing (e.g. pending) resource."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    existing = resource_service.get(resource_id)
    if not existing:
        return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

    kind = (request.form.get('kind') or '').strip().lower()
    if kind == 'link':
        url = (request.form.get('url') or '').strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            return jsonify({'status': 'error', 'message': 'Enter a valid http(s) link'}), 400
        resource_service.attach(resource_id, 'link', url=url)
    elif kind == 'file':
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify({'status': 'error', 'message': 'Choose a file to upload'}), 400
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in RESOURCE_ALLOWED_EXT:
            return jsonify({'status': 'error', 'message': f'Unsupported file type .{ext}'}), 400
        try:
            rel, stored = file_upload_handler.save_resource(file)
        except Exception as e:
            app.logger.error(f'Resource attach upload failed: {e}')
            return jsonify({'status': 'error', 'message': 'Could not save the file'}), 500
        # remove the previous file if this resource already had one
        if existing.get('kind') == 'file' and existing.get('file_path'):
            file_upload_handler.delete_file(existing['file_path'])
        resource_service.attach(resource_id, 'file', file_path=rel,
                                filename=secure_filename(file.filename),
                                content_type=file.mimetype)
    else:
        return jsonify({'status': 'error', 'message': 'Invalid resource type'}), 400

    return jsonify({'status': 'success'}), 200


@app.route('/api/resources/<resource_id>/download')
@login_required
def download_resource(resource_id):
    """Stream/redirect to a resource for any signed-in user."""
    rec = resource_service.get(resource_id)
    if not rec:
        return jsonify({'status': 'error', 'message': 'Resource not found'}), 404
    if rec.get('kind') == 'link':
        return redirect(rec.get('url') or '/')
    rel = rec.get('file_path')
    if not rel:
        return jsonify({'status': 'error', 'message': 'No file'}), 404
    if file_upload_handler.use_s3:
        signed = file_upload_handler.generate_presigned_url(rel, download_name=rec.get('filename'))
        if not signed:
            return jsonify({'status': 'error', 'message': 'Could not generate download'}), 500
        return redirect(signed)
    # local: rel is like "resources/<stored>"
    directory = os.path.join(UPLOAD_FOLDER, os.path.dirname(rel))
    return send_from_directory(directory, os.path.basename(rel),
                               as_attachment=True, download_name=rec.get('filename'))


@app.route('/api/settings/email', methods=['GET'])
@login_required
def get_email_settings():
    """Admin-only: read subscribers + admin-notify list + the regions to pick from."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    s = settings_service.get_email_settings()
    regions = [{'id': r.get('id'), 'name': r.get('name')}
               for r in region_service.get_all_regions() if r.get('id') != 'unassigned']
    return jsonify({'status': 'success', 'subscribers': s['subscribers'],
                    'admin_notify': s['admin_notify'], 'regions': regions,
                    'inspectors': leadership_names(),
                    'clinical': s['clinical'], 'ops': s['ops'],
                    'email_enabled': email_service.enabled}), 200


@app.route('/api/settings/email', methods=['POST'])
@login_required
def save_email_settings():
    """Admin-only: update subscribers + admin-notify list."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    data = request.get_json(silent=True) or {}
    # keep only real region ids and known inspector names in each subscriber's scope
    valid_ids = {r.get('id') for r in region_service.get_all_regions() if r.get('id') != 'unassigned'}
    valid_names = set(leadership_names())
    subs = []
    for s in (data.get('subscribers') or []):
        if not isinstance(s, dict):
            continue
        regions = [rid for rid in (s.get('regions') or []) if rid in valid_ids]
        inspectors = [n for n in (s.get('inspectors') or []) if n in valid_names]
        subs.append({'email': s.get('email', ''), 'name': s.get('name', ''),
                     'regions': regions, 'inspectors': inspectors})
    saved = settings_service.set_email_settings(
        subscribers=subs, admin_notify=data.get('admin_notify', ''),
        clinical=data.get('clinical', ''), ops=data.get('ops', ''))
    regions = [{'id': r.get('id'), 'name': r.get('name')}
               for r in region_service.get_all_regions() if r.get('id') != 'unassigned']
    return jsonify({'status': 'success', 'regions': regions, 'inspectors': leadership_names(), **saved}), 200


@app.route('/api/user-info')
@login_required
def get_user_info():
    """
    Get current user's information
    """
    username = session.get('user')
    role = current_role()
    region_id = session.get('region_id')
    region_name = None
    if role == 'regional':
        communities = regional_communities()
        region_name = next((r.get('name') for r in region_service.get_all_regions()
                            if r.get('id') == region_id), None)
    elif session.get('community'):
        communities = [session.get('community')]
    else:
        communities = []
    return jsonify({
        'username': username,
        'display_name': profile_service.get_display_name(username) or session.get('display_name') or '',
        'photo': profile_service.get_photo(username),
        'community': session.get('community'),
        'role': role,
        'is_admin': role == 'admin',
        'region_id': region_id,
        'region_name': region_name,
        'communities': communities
    }), 200


# ==================== SURVEY TYPE API ====================

@app.route('/api/survey-types', methods=['GET'])
@login_required
def get_survey_types():
    """
    Get all active survey types
    
    Returns:
        200: JSON with status and survey_types array
        500: Internal server error
        
    Requirements: Task 4.1
    """
    try:
        survey_types = survey_type_service.get_all_survey_types()
        
        return jsonify({
            'status': 'success',
            'survey_types': survey_types
        }), 200
        
    except Exception as e:
        app.logger.error(f'Error retrieving survey types: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while retrieving survey types'
        }), 500


@app.route('/api/survey-types', methods=['POST'])
@login_required
def create_survey_type():
    """Admin-only: create a new survey type (a question group / checklist)."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    data = request.get_json(silent=True) or {}
    name = InputSanitizer.sanitize_string(data.get('name', ''), max_length=80).strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Name is required'}), 400
    description = InputSanitizer.sanitize_string(data.get('description', ''), max_length=300)
    icon = InputSanitizer.sanitize_string(data.get('icon', ''), max_length=40) or 'fa-clipboard-list'
    color = InputSanitizer.sanitize_string(data.get('color', ''), max_length=20) or '#1f6fe5'
    try:
        st = survey_type_service.create_survey_type(name, description, icon, color)
    except Exception as e:
        app.logger.error(f'Error creating survey type: {e}')
        return jsonify({'status': 'error', 'message': 'Could not create survey type'}), 500
    return jsonify({'status': 'success', 'survey_type': st}), 201


@app.route('/api/survey-types/<survey_type_id>', methods=['PUT'])
@login_required
def update_survey_type(survey_type_id):
    """Admin-only: edit a survey type's name/description/icon/color."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    data = request.get_json(silent=True) or {}
    st = survey_type_service.update_survey_type(
        survey_type_id,
        name=InputSanitizer.sanitize_string(data.get('name', ''), max_length=80) if 'name' in data else None,
        description=InputSanitizer.sanitize_string(data.get('description', ''), max_length=300) if 'description' in data else None,
        icon=InputSanitizer.sanitize_string(data.get('icon', ''), max_length=40) if 'icon' in data else None,
        color=InputSanitizer.sanitize_string(data.get('color', ''), max_length=20) if 'color' in data else None,
    )
    if not st:
        return jsonify({'status': 'error', 'message': 'Survey type not found'}), 404
    return jsonify({'status': 'success', 'survey_type': st}), 200


@app.route('/api/survey-types/<survey_type_id>', methods=['DELETE'])
@login_required
def delete_survey_type(survey_type_id):
    """Admin-only: remove a survey type."""
    if current_role() != 'admin':
        return jsonify({'status': 'error', 'message': 'Admins only'}), 403
    if survey_type_service.delete_survey_type(survey_type_id):
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'error', 'message': 'Survey type not found'}), 404


@app.route('/api/select-survey-type', methods=['POST'])
@login_required
def api_select_survey_type():
    """
    Store selected survey type in session
    
    Expects JSON with survey_type_id
    
    Returns:
        200: Success with survey type info
        400: Invalid survey type ID or missing field
        500: Internal server error
        
    Requirements: Task 4.2
    """
    try:
        # Handle JSON parsing errors
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format or Content-Type must be application/json'
            }), 400
        
        # Validate JSON structure
        if not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400
        
        # Get and sanitize survey_type_id
        survey_type_id = data.get('survey_type_id', '')
        survey_type_id = InputSanitizer.sanitize_string(survey_type_id, max_length=50)
        
        if not survey_type_id:
            return jsonify({
                'status': 'error',
                'message': 'survey_type_id is required'
            }), 400
        
        # Validate survey type exists
        if not survey_type_service.validate_survey_type(survey_type_id):
            return jsonify({
                'status': 'error',
                'message': f'Invalid survey type: {survey_type_id}'
            }), 400
        
        # Get survey type details
        survey_type = survey_type_service.get_survey_type_by_id(survey_type_id)
        
        if not survey_type:
            return jsonify({
                'status': 'error',
                'message': f'Survey type not found: {survey_type_id}'
            }), 400
        
        # Store in session
        session['survey_type_id'] = survey_type_id
        session['survey_type_name'] = survey_type['name']
        session.modified = True
        
        return jsonify({
            'status': 'success',
            'message': 'Survey type selected successfully',
            'survey_type': survey_type
        }), 200
        
    except Exception as e:
        app.logger.error(f'Error selecting survey type: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while selecting survey type'
        }), 500


@app.route('/questions/manage')
@require_admin
def question_manager_ui():
    """
    Render the Question Manager UI (question_manager.html)
    This page is designed for admin users to create, edit, and manage inspection questions
    Requires admin authentication - non-admin users are redirected to inspection form
    
    Requirements: 1.1, 7.1
    """
    return render_template('question_manager.html',
                         username=session.get('user'),
                         communities=ALL_COMMUNITIES)


@app.route('/api/questions', methods=['GET'])
@login_required
def get_questions():
    """
    Get active questions with community and survey type filtering
    
    Query Parameters:
        community (optional): Filter questions by community name
        survey_type (optional): Filter questions by survey type ID
        
    Behavior:
        - For staff users: Automatically filters by their assigned community
        - For admin users: Returns all active questions, or filters by community parameter if provided
        - If survey_type is provided, filters questions by that survey type
        
    Returns:
        200: JSON with status and questions array
        400: Invalid survey type
        500: Internal server error
    """
    try:
        # Sanitize community filter from query parameter
        community_filter = request.args.get('community')
        if community_filter:
            community_filter = InputSanitizer.sanitize_community_name(community_filter)
        
        # Get survey type filter from query parameter
        survey_type_filter = request.args.get('survey_type')
        if survey_type_filter:
            survey_type_filter = InputSanitizer.sanitize_string(survey_type_filter, max_length=50)
            # Validate survey type
            if not survey_type_service.validate_survey_type(survey_type_filter):
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid survey type: {survey_type_filter}'
                }), 400
        
        # Determine which questions to return, by role
        role = current_role()
        if role == 'admin':
            if community_filter:
                questions = question_manager.get_questions_for_community(community_filter)
            else:
                questions = question_manager.get_all_active_questions()
        elif role == 'regional':
            # Regionals must pick a community within their region
            allowed = regional_communities()
            if community_filter and community_filter in allowed:
                questions = question_manager.get_questions_for_community(community_filter)
            else:
                questions = []
        else:
            # Staff user - always filter by their assigned community
            questions = question_manager.get_questions_for_community(session.get('community'))
        
        # Apply survey type filter if provided
        if survey_type_filter:
            questions = question_filter_service.filter_by_survey_type(questions, survey_type_filter)
        
        return jsonify({
            'status': 'success',
            'questions': questions
        }), 200
        
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f'Error retrieving questions: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while retrieving questions'
        }), 500


# ==================== QUESTION MANAGEMENT API ====================

@app.route('/api/questions', methods=['POST'])
@require_admin
def create_question():
    """
    API endpoint to create a new inspection question
    Requires admin authentication
    Expects JSON with text, photo_required, and communities array
    
    Error Handling:
    - 400: JSON parsing errors, validation errors, missing fields
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Handle JSON parsing errors
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format or Content-Type must be application/json'
            }), 400
        
        # Validate JSON structure
        if not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400
        
        # Sanitize input data
        sanitized_data = InputSanitizer.sanitize_question_data(data)
        
        # Extract fields
        text = sanitized_data.get('text', '')
        interpretive_guideline = sanitized_data.get('interpretive_guideline', '')
        photo_required = sanitized_data.get('photo_required', False)
        communities = sanitized_data.get('communities', [])
        survey_types = sanitized_data.get('survey_types', [])

        # Validate text is non-empty
        if not text or not text.strip():
            return jsonify({
                'status': 'error',
                'message': 'Question text cannot be empty'
            }), 400

        # Validate communities array is non-empty
        if not communities or len(communities) == 0:
            return jsonify({
                'status': 'error',
                'message': 'At least one community must be selected'
            }), 400

        pass_criteria = sanitized_data.get('pass_criteria', [])

        # Create question using QuestionManager
        question = question_manager.create_question(text, photo_required, communities, survey_types, interpretive_guideline, pass_criteria)

        activity_service.log(session.get('user'), 'question_created', text)

        return jsonify({
            'status': 'success',
            'question': question
        }), 201
        
    except ValueError as e:
        # Validation errors from QuestionManager
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except IOError as e:
        # File system errors
        app.logger.error(f'File system error creating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error: Failed to save question'
        }), 500
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error creating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while creating question'
        }), 500


@app.route('/api/questions/<question_id>', methods=['PUT'])
@require_admin
def update_question(question_id):
    """
    API endpoint to update an existing inspection question
    Requires admin authentication
    Expects JSON with text, photo_required, and communities array
    
    Error Handling:
    - 400: JSON parsing errors, validation errors, missing fields
    - 404: Question not found
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Sanitize question_id
        question_id = InputSanitizer.sanitize_string(question_id, max_length=100)
        
        # Handle JSON parsing errors
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON format or Content-Type must be application/json'
            }), 400
        
        # Validate JSON structure
        if not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400
        
        # Sanitize input data
        sanitized_data = InputSanitizer.sanitize_question_data(data)
        
        # Extract fields
        text = sanitized_data.get('text', '')
        interpretive_guideline = sanitized_data.get('interpretive_guideline', '')
        photo_required = sanitized_data.get('photo_required', False)
        communities = sanitized_data.get('communities', [])
        survey_types = sanitized_data.get('survey_types', [])

        # Validate text is non-empty
        if not text or not text.strip():
            return jsonify({
                'status': 'error',
                'message': 'Question text cannot be empty'
            }), 400

        # Validate communities array is non-empty
        if not communities or len(communities) == 0:
            return jsonify({
                'status': 'error',
                'message': 'At least one community must be selected'
            }), 400

        pass_criteria = sanitized_data.get('pass_criteria', [])

        # Update question using QuestionManager
        question = question_manager.update_question(question_id, text, photo_required, communities, survey_types, interpretive_guideline, pass_criteria)
        
        # Check if question was found
        if question is None:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404

        activity_service.log(session.get('user'), 'question_updated', text)

        return jsonify({
            'status': 'success',
            'question': question
        }), 200
        
    except ValueError as e:
        # Validation errors from QuestionManager
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except IOError as e:
        # File system errors
        app.logger.error(f'File system error updating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error: Failed to save question'
        }), 500
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error updating question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while updating question'
        }), 500


@app.route('/api/questions/<question_id>', methods=['DELETE'])
@require_admin
def delete_question(question_id):
    """
    API endpoint to delete an inspection question (soft delete)
    Requires admin authentication
    Performs soft delete by setting is_active to False
    
    Error Handling:
    - 404: Question not found
    - 500: Internal server errors (file system, etc.)
    """
    try:
        # Sanitize question_id
        question_id = InputSanitizer.sanitize_string(question_id, max_length=100)
        
        # Delete question using QuestionManager (soft delete)
        success = question_manager.delete_question(question_id)
        
        # Check if question was found
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404

        activity_service.log(session.get('user'), 'question_deleted', f'Question {question_id}')

        return jsonify({
            'status': 'success',
            'message': 'Question deleted successfully'
        }), 200
        
    except IOError as e:
        # File system errors
        app.logger.error(f'File system error deleting question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error: Failed to save changes'
        }), 500
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error deleting question: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while deleting question'
        }), 500


@app.route('/api/questions/bulk-delete', methods=['POST'])
@require_admin
def bulk_delete_questions():
    """
    API endpoint to soft-delete multiple questions in one request
    Requires admin authentication
    Expects JSON: { "question_ids": ["id1", "id2", ...] }

    Error Handling:
    - 400: Invalid JSON, missing/empty question_ids
    - 500: Internal server errors
    """
    try:
        data = request.get_json(silent=True)

        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }), 400

        question_ids = data.get('question_ids')
        if not isinstance(question_ids, list) or len(question_ids) == 0:
            return jsonify({
                'status': 'error',
                'message': 'question_ids must be a non-empty array'
            }), 400

        deleted = 0
        not_found = []
        for raw_id in question_ids:
            qid = InputSanitizer.sanitize_string(str(raw_id), max_length=100)
            if not qid:
                continue
            if question_manager.delete_question(qid):
                deleted += 1
            else:
                not_found.append(qid)

        if deleted:
            activity_service.log(session.get('user'), 'question_deleted', f'Deleted {deleted} question(s)')

        return jsonify({
            'status': 'success',
            'message': f'Deleted {deleted} question(s)',
            'deleted': deleted,
            'not_found': not_found
        }), 200

    except IOError as e:
        app.logger.error(f'File system error during bulk delete: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error: Failed to save changes'
        }), 500
    except Exception as e:
        app.logger.error(f'Unexpected error during bulk delete: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while deleting questions'
        }), 500


# ==================== REGIONS API ====================

@app.route('/api/regions', methods=['GET'])
@login_required
def get_regions():
    """
    Get the regional structure: each region with its leadership roster and
    assigned communities. Used by the dashboard Regions view.
    """
    try:
        # Enrich a copy of each leader with their uploaded photo (if any),
        # without mutating the stored region data.
        enriched = []
        for region in region_service.get_all_regions():
            r = dict(region)
            r['leadership'] = [
                {**leader, 'photo': profile_service.get_leader_photo(region.get('id', ''), leader.get('name', ''))}
                for leader in region.get('leadership', [])
            ]
            enriched.append(r)
        return jsonify({
            'status': 'success',
            'regions': enriched
        }), 200
    except Exception as e:
        app.logger.error(f'Error retrieving regions: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while retrieving regions'
        }), 500


@app.route('/api/regions/assign', methods=['POST'])
@require_admin
def assign_region_community():
    """
    Assign a community to a region (move existing, add new, or restore from
    Unassigned). The community ends up belonging only to the target region.
    Expects JSON: { "community": "...", "region_id": "..." }
    """
    try:
        data = request.get_json(silent=True)
        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({'status': 'error', 'message': 'Request body must be a JSON object'}), 400

        community = InputSanitizer.sanitize_community_name(data.get('community', ''))
        region_id = InputSanitizer.sanitize_string(data.get('region_id', ''), max_length=50)

        if not community:
            return jsonify({'status': 'error', 'message': 'community is required'}), 400
        if not region_id:
            return jsonify({'status': 'error', 'message': 'region_id is required'}), 400

        if not region_service.assign_community(community, region_id):
            return jsonify({'status': 'error', 'message': f'Unknown region: {region_id}'}), 400

        activity_service.log(session.get('user'), 'region_assigned', f'Assigned {community} to {region_id}')

        return jsonify({'status': 'success', 'regions': region_service.get_all_regions()}), 200
    except IOError as e:
        app.logger.error(f'File system error assigning community: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error: Failed to save changes'}), 500
    except Exception as e:
        app.logger.error(f'Unexpected error assigning community: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while assigning community'}), 500


@app.route('/api/regions/rename', methods=['POST'])
@require_admin
def rename_region():
    """Rename a region's display name (admin only). The region id is unchanged,
    so user scoping is unaffected. Expects JSON: { region_id, name }."""
    try:
        data = request.get_json(silent=True)
        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({'status': 'error', 'message': 'Request body must be a JSON object'}), 400

        region_id = InputSanitizer.sanitize_string(data.get('region_id', ''), max_length=50)
        new_name = InputSanitizer.sanitize_string(data.get('name', ''), max_length=80)

        if not region_id or not new_name:
            return jsonify({'status': 'error', 'message': 'region_id and name are required'}), 400
        if region_id == 'unassigned':
            return jsonify({'status': 'error', 'message': 'The Unassigned group cannot be renamed'}), 400

        if not region_service.rename_region(region_id, new_name):
            return jsonify({'status': 'error', 'message': 'Could not rename region (unknown id or unchanged name)'}), 400

        activity_service.log(session.get('user'), 'region_renamed', f'Renamed region {region_id} to "{new_name}"')
        return jsonify({'status': 'success', 'regions': region_service.get_all_regions()}), 200
    except Exception as e:
        app.logger.error(f'Unexpected error renaming region: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while renaming region'}), 500


@app.route('/api/regions/rename-community', methods=['POST'])
@require_admin
def rename_region_community():
    """
    Rename a community everywhere it's stored: the regional structure,
    the inspection questions, and historical submissions.
    Expects JSON: { "old_name": "...", "new_name": "..." }
    """
    try:
        data = request.get_json(silent=True)
        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({'status': 'error', 'message': 'Request body must be a JSON object'}), 400

        old_name = InputSanitizer.sanitize_community_name(data.get('old_name', ''))
        new_name = InputSanitizer.sanitize_community_name(data.get('new_name', ''))
        if not old_name or not new_name:
            return jsonify({'status': 'error', 'message': 'old_name and new_name are required'}), 400
        if old_name == new_name:
            return jsonify({'status': 'success', 'regions': region_service.get_all_regions()}), 200

        region_service.rename_community(old_name, new_name)
        try:
            question_manager.rename_community(old_name, new_name)
            inspection_service.rename_community(old_name, new_name)
        except Exception as e:
            app.logger.error(f'Partial error during community rename: {str(e)}')

        activity_service.log(session.get('user'), 'community_renamed',
                             f'Renamed "{old_name}" to "{new_name}"')

        return jsonify({'status': 'success', 'regions': region_service.get_all_regions()}), 200
    except IOError as e:
        app.logger.error(f'File system error renaming community: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error: Failed to save changes'}), 500
    except Exception as e:
        app.logger.error(f'Unexpected error renaming community: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while renaming community'}), 500


@app.route('/api/regions/leader-photo', methods=['POST'])
@require_admin
def upload_leader_photo():
    """Upload a photo for a region leadership member (admin only)."""
    try:
        region_id = InputSanitizer.sanitize_string(request.form.get('region_id', ''), max_length=50)
        leader_name = InputSanitizer.sanitize_string(request.form.get('leader_name', ''), max_length=120)

        if not region_id or not leader_name:
            return jsonify({'status': 'error', 'message': 'region_id and leader_name are required'}), 400
        if 'photo' not in request.files:
            return jsonify({'status': 'error', 'message': 'No photo provided'}), 400

        file = request.files['photo']
        if not file or file.filename == '':
            return jsonify({'status': 'error', 'message': 'No photo provided'}), 400
        if not allowed_file(file.filename):
            return jsonify({'status': 'error', 'message': 'Invalid file type. Only images are allowed.'}), 400

        ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"leader_{secure_filename(region_id)}_{secure_filename(leader_name)}_{timestamp}.{ext}"
        try:
            file.save(os.path.join(AVATARS_FOLDER, filename))
        except IOError as e:
            app.logger.error(f'Error saving leader photo: {str(e)}')
            return jsonify({'status': 'error', 'message': 'Failed to save photo'}), 500

        relative_path = f"avatars/{filename}"
        profile_service.set_leader_photo(region_id, leader_name, relative_path)
        return jsonify({'status': 'success', 'photo': relative_path}), 200
    except Exception as e:
        app.logger.error(f'Error uploading leader photo: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while uploading photo'}), 500


@app.route('/api/regions/leader', methods=['POST'])
@require_admin
def manage_region_leader():
    """
    Add, update, or delete a leadership member in a region (admin only).
    Expects JSON:
      { "action": "add",    "region_id": "...", "name": "...", "role": "...", "email": "..." }
      { "action": "update", "region_id": "...", "index": N, "name": "...", "role": "...", "email": "..." }
      { "action": "delete", "region_id": "...", "index": N }
    """
    try:
        data = request.get_json(silent=True)
        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({'status': 'error', 'message': 'Request body must be a JSON object'}), 400

        action = InputSanitizer.sanitize_string(data.get('action', ''), max_length=20)

        # Move/reorder uses from_/to_ region ids rather than a single region_id
        if action == 'move':
            from_region = InputSanitizer.sanitize_string(data.get('from_region_id', ''), max_length=50)
            to_region = InputSanitizer.sanitize_string(data.get('to_region_id', ''), max_length=50)
            from_index = data.get('from_index')
            to_index = data.get('to_index')
            if not from_region or not to_region:
                return jsonify({'status': 'error', 'message': 'from_region_id and to_region_id are required'}), 400
            if not isinstance(from_index, int):
                return jsonify({'status': 'error', 'message': 'from_index is required'}), 400

            moved = region_service.move_leader(
                from_region, from_index, to_region,
                to_index if isinstance(to_index, int) else None
            )
            if not moved:
                return jsonify({'status': 'error', 'message': 'Could not move leader (bad region or index)'}), 400

            # Carry the leader's photo to the new region key
            name = moved.get('name', '')
            if from_region != to_region and name:
                photo = profile_service.get_leader_photo(from_region, name)
                if photo:
                    profile_service.set_leader_photo(to_region, name, photo)

            activity_service.log(session.get('user'), 'leader_moved',
                                 f'Moved {name} from {from_region} to {to_region}')
            return jsonify({'status': 'success'}), 200

        region_id = InputSanitizer.sanitize_string(data.get('region_id', ''), max_length=50)
        if not region_id:
            return jsonify({'status': 'error', 'message': 'region_id is required'}), 400

        if action == 'delete':
            index = data.get('index')
            if not isinstance(index, int):
                return jsonify({'status': 'error', 'message': 'index is required'}), 400
            if not region_service.remove_leader(region_id, index):
                return jsonify({'status': 'error', 'message': 'Could not delete leader (bad region or index)'}), 400
            activity_service.log(session.get('user'), 'leader_removed', f'Removed a leader from {region_id}')

        elif action in ('add', 'update'):
            name = InputSanitizer.sanitize_string(data.get('name', ''), max_length=120)
            role = InputSanitizer.sanitize_string(data.get('role', ''), max_length=40)
            email = InputSanitizer.sanitize_string(data.get('email', ''), max_length=120)
            if not name:
                return jsonify({'status': 'error', 'message': 'Leader name is required'}), 400

            if action == 'add':
                if not region_service.add_leader(region_id, name, role, email):
                    return jsonify({'status': 'error', 'message': f'Unknown region: {region_id}'}), 400
                activity_service.log(session.get('user'), 'leader_added', f'Added {name} ({role}) to {region_id}')
            else:
                index = data.get('index')
                if not isinstance(index, int):
                    return jsonify({'status': 'error', 'message': 'index is required'}), 400
                if not region_service.update_leader(region_id, index, name, role, email):
                    return jsonify({'status': 'error', 'message': 'Could not update leader (bad region or index)'}), 400
                activity_service.log(session.get('user'), 'leader_updated', f'Updated {name} ({role}) in {region_id}')
        else:
            return jsonify({'status': 'error', 'message': 'action must be add, update, delete, or move'}), 400

        return jsonify({'status': 'success'}), 200
    except IOError as e:
        app.logger.error(f'File system error managing leader: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error: Failed to save changes'}), 500
    except Exception as e:
        app.logger.error(f'Unexpected error managing leader: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while managing leadership'}), 500


@app.route('/api/regions/remove-community', methods=['POST'])
@require_admin
def remove_region_community():
    """
    Remove a community from the regional structure entirely.
    Expects JSON: { "community": "..." }
    """
    try:
        data = request.get_json(silent=True)
        if data is None or not InputSanitizer.validate_json_structure(data, dict):
            return jsonify({'status': 'error', 'message': 'Request body must be a JSON object'}), 400

        community = InputSanitizer.sanitize_community_name(data.get('community', ''))
        if not community:
            return jsonify({'status': 'error', 'message': 'community is required'}), 400

        found = region_service.remove_community(community)
        if not found:
            return jsonify({'status': 'error', 'message': 'Community not found in any region'}), 404

        activity_service.log(session.get('user'), 'region_removed', f'Removed {community} from regions')

        return jsonify({'status': 'success', 'regions': region_service.get_all_regions()}), 200
    except IOError as e:
        app.logger.error(f'File system error removing community: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error: Failed to save changes'}), 500
    except Exception as e:
        app.logger.error(f'Unexpected error removing community: {str(e)}')
        return jsonify({'status': 'error', 'message': 'Internal server error while removing community'}), 500


# ==================== INSPECTION SUBMISSION API ====================

@app.route('/api/inspections', methods=['POST'])
@login_required
def submit_inspection():
    """
    API endpoint for inspection submission
    Requires authentication using @login_required decorator
    Accepts multipart/form-data with responses array
    Validates each response has question_id and condition
    Handles optional photo uploads for each response
    Saves photos using FileUploadHandler
    Creates submission using InspectionService
    Returns 201 with submission data on success
    Returns 400 with error message on validation failure
    
    Error Handling:
    - 400: JSON parsing errors, validation errors, missing fields, invalid file types/sizes
    - 500: Internal server errors (file system, etc.)
    
    Requirements: 3.1, 3.3, 4.1, 4.2, 4.3, 4.4, 5.1, 5.7, 5.8
    """
    try:
        # Get user info from session
        username = session.get('user')
        survey_type_id = session.get('survey_type_id')
        role = current_role()

        # Sanitize user info
        username = InputSanitizer.sanitize_username(username)

        # Resolve the community being inspected, by role:
        #  - staff: their fixed community
        #  - regional: a community they pick (must be within their region)
        #  - admin: not allowed
        if role == 'admin':
            return jsonify({'status': 'error', 'message': 'Admin users cannot submit inspections'}), 400
        elif role == 'regional':
            community = InputSanitizer.sanitize_community_name(request.form.get('community', ''))
            if not community or community not in regional_communities():
                return jsonify({'status': 'error', 'message': 'Select a valid community in your region'}), 400
        else:
            community = session.get('community')
            if community:
                community = InputSanitizer.sanitize_community_name(community)
            if not community:
                return jsonify({'status': 'error', 'message': 'No community assigned to this account'}), 400
        
        # Validate survey type is selected
        if not survey_type_id:
            return jsonify({
                'status': 'error',
                'message': 'Survey type must be selected before submitting inspection'
            }), 400
        
        # Validate survey type is valid
        if not survey_type_service.validate_survey_type(survey_type_id):
            return jsonify({
                'status': 'error',
                'message': f'Invalid survey type in session: {survey_type_id}'
            }), 400
        
        # Parse responses from form data
        # Expected format: responses as JSON string in form data
        responses_json = request.form.get('responses')
        
        if not responses_json:
            return jsonify({
                'status': 'error',
                'message': 'No responses provided'
            }), 400
        
        # Parse JSON responses with error handling
        try:
            responses_data = json.loads(responses_json)
        except json.JSONDecodeError as e:
            return jsonify({
                'status': 'error',
                'message': f'Invalid JSON format for responses: {str(e)}'
            }), 400
        
        # Validate responses is a list
        if not InputSanitizer.validate_json_structure(responses_data, list):
            return jsonify({
                'status': 'error',
                'message': 'Responses must be an array'
            }), 400
        
        # Process each response
        processed_responses = []
        
        for idx, response in enumerate(responses_data):
            # Validate response is a dictionary
            if not isinstance(response, dict):
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: must be a JSON object'
                }), 400
            
            # Sanitize response data
            sanitized_response = InputSanitizer.sanitize_response_data(response)
            
            # Validate required fields: question_id and condition
            question_id = sanitized_response.get('question_id')
            condition = sanitized_response.get('condition')
            
            if not question_id:
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: question_id is required'
                }), 400
            
            if not condition:
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: condition is required'
                }), 400
            
            # Validate condition value (Pass/Fail)
            if condition not in ['Pass', 'Fail']:
                return jsonify({
                    'status': 'error',
                    'message': f'Response {idx}: condition must be "Pass" or "Fail"'
                }), 400
            
            # Get optional fields
            question_text = sanitized_response.get('question_text', '')
            description = sanitized_response.get('description', '')
            
            # Handle optional photo upload
            photo_path = None
            photo_field_name = f'photo_{idx}'
            
            if photo_field_name in request.files:
                photo_file = request.files[photo_field_name]
                
                # Only process if file was actually uploaded
                if photo_file and photo_file.filename:
                    # Validate file using FileUploadHandler
                    is_valid, error_message = file_upload_handler.validate_file(photo_file)
                    
                    if not is_valid:
                        return jsonify({
                            'status': 'error',
                            'message': f'Response {idx}: {error_message}'
                        }), 400
                    
                    # Save photo using FileUploadHandler
                    try:
                        photo_path = file_upload_handler.save_file(photo_file, username, community)
                    except IOError as e:
                        app.logger.error(f'File system error saving photo: {str(e)}')
                        return jsonify({
                            'status': 'error',
                            'message': f'Response {idx}: Internal server error - Failed to save photo'
                        }), 500
                    except Exception as e:
                        app.logger.error(f'Unexpected error saving photo: {str(e)}')
                        return jsonify({
                            'status': 'error',
                            'message': f'Response {idx}: Failed to save photo'
                        }), 400
            
            # Optional routing of this item's comment to Clinical / Ops
            route_to = (response.get('route_to') or '').strip().lower()
            if route_to not in ('clinical', 'ops'):
                route_to = None

            # Create response object
            response_obj = {
                'question_id': question_id,
                'question_text': question_text,
                'condition': condition,
                'description': description,
                'photo_path': photo_path,
                'route_to': route_to,
                'answered_at': datetime.now().isoformat()
            }

            processed_responses.append(response_obj)
        
        # Create submission using InspectionService
        try:
            submission = inspection_service.create_submission(
                username=username,
                community=community,
                responses=processed_responses,
                survey_type_id=survey_type_id,
                inspector_name=(session.get('display_name') or resolve_display_name(username))
            )
            
            # Clear survey type from session after successful submission
            session.pop('survey_type_id', None)
            session.pop('survey_type_name', None)
            session.modified = True

            # Audit log
            activity_service.log(username, 'inspection_submitted',
                                 f'Submitted inspection for {community}',
                                 meta={'community': community})
            
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 400
        except IOError as e:
            app.logger.error(f'File system error creating submission: {str(e)}')
            return jsonify({
                'status': 'error',
                'message': 'Internal server error: Failed to save inspection'
            }), 500
        
        # Fire off the post-visit summary email (best-effort; never blocks the
        # response or fails the submission if email is down/unconfigured).
        if email_service.enabled:
            try:
                survey_name = (survey_type_service.get_survey_type_name(submission.get('survey_type_id'))
                               if submission.get('survey_type_id') else None)
                community = submission.get('community')
                region = region_for_community(community)
                region_id = region.get('id') if region else None
                recipients = region_leader_emails(community)
                recipients += settings_service.recipients_for_inspection(
                    region_id, submission.get('inspector_name'))
                # criteria lookup so the email can show "must include to pass" per failed item
                criteria_map = {}
                for q in question_manager.get_all_active_questions():
                    crit = q.get('pass_criteria') or []
                    if q.get('id'):
                        criteria_map[q['id']] = crit
                    if q.get('text'):
                        criteria_map['t:' + q['text'].strip().lower()] = crit
                email_service.send_inspection_report(submission, recipients, survey_name, criteria_map)

                # Route any item-level comments directed to Clinical / Ops
                for route in ('clinical', 'ops'):
                    items = [r for r in submission.get('responses', [])
                             if r.get('route_to') == route and (r.get('description') or '').strip()]
                    if items:
                        to = settings_service.recipients_for_route(route)
                        if to:
                            email_service.send_directed_comments(to, route, submission, items)
            except Exception as e:
                app.logger.error(f'Post-visit email step failed: {e}')

        # Return success with submission data
        return jsonify({
            'status': 'success',
            'submission': submission
        }), 201
        
    except Exception as e:
        # Unexpected errors
        app.logger.error(f'Unexpected error submitting inspection: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while submitting inspection'
        }), 500


@app.route('/api/inspections', methods=['GET'])
@login_required
def get_inspections():
    """
    Get inspection submissions with community and survey type filtering
    
    Query Parameters:
        community (optional): Filter submissions by community name (admin only)
        survey_type (optional): Filter submissions by survey type ID
        
    Behavior:
        - For staff users: Automatically filters by their assigned community
        - For admin users: Returns all submissions, or filters by community parameter if provided
        - If survey_type is provided, filters submissions by that survey type
        
    Returns:
        200: JSON with status and submissions array
        400: Invalid survey type
        500: Internal server error
        
    Requirements: 9.1, Task 4.5
    """
    try:
        # Sanitize community filter from query parameter
        community_filter = request.args.get('community')
        if community_filter:
            community_filter = InputSanitizer.sanitize_community_name(community_filter)
        
        # Get survey type filter from query parameter
        survey_type_filter = request.args.get('survey_type')
        if survey_type_filter:
            survey_type_filter = InputSanitizer.sanitize_string(survey_type_filter, max_length=50)
            # Validate survey type
            if not survey_type_service.validate_survey_type(survey_type_filter):
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid survey type: {survey_type_filter}'
                }), 400
        
        # Determine which submissions to return, by role
        role = current_role()
        if role == 'admin':
            if community_filter:
                submissions = inspection_service.get_submissions_by_community(community_filter)
            else:
                submissions = inspection_service.get_all_submissions()
        elif role == 'regional':
            # Regionals see submissions across their region's communities
            allowed = set(regional_communities())
            all_subs = inspection_service.get_all_submissions()
            if community_filter and community_filter in allowed:
                submissions = [s for s in all_subs if s.get('community') == community_filter]
            else:
                submissions = [s for s in all_subs if s.get('community') in allowed]
        else:
            # Staff user - always filter by their assigned community
            submissions = inspection_service.get_submissions_by_community(session.get('community'))
        
        # Apply survey type filter if provided
        if survey_type_filter:
            submissions = [
                sub for sub in submissions
                if sub.get('survey_type_id') == survey_type_filter
            ]

        # Enrich with a friendly inspector name. Prefer the name stored on the
        # submission (captured at visit time), else resolve from the username.
        # When photos live in S3, also attach a short-lived signed URL to each
        # response so the private objects can be displayed.
        enriched = []
        for sub in submissions:
            uname = sub.get('username', '')
            name = sub.get('inspector_name') or resolve_display_name(uname)
            new_sub = {**sub, 'inspector_name': name}
            if file_upload_handler.use_s3 and isinstance(sub.get('responses'), list):
                new_responses = []
                for resp in sub['responses']:
                    r = dict(resp)
                    if r.get('photo_path'):
                        r['photo_url'] = file_upload_handler.generate_presigned_url(r['photo_path'])
                    new_responses.append(r)
                new_sub['responses'] = new_responses
            enriched.append(new_sub)

        return jsonify({
            'status': 'success',
            'submissions': enriched
        }), 200
        
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f'Error retrieving inspections: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error while retrieving inspections'
        }), 500


# ==================== REPORT EXPORTS (CSV / XLSX / PDF) ====================

def _scoped_submissions_for_export():
    """Inspection submissions visible to the current user, role-scoped exactly
    like the Reports view (admin = all, regional = their region, staff = their
    community), each enriched with a friendly inspector name."""
    role = current_role()
    if role == 'admin':
        submissions = inspection_service.get_all_submissions()
    elif role == 'regional':
        allowed = set(regional_communities())
        submissions = [s for s in inspection_service.get_all_submissions()
                       if s.get('community') in allowed]
    else:
        submissions = inspection_service.get_submissions_by_community(session.get('community'))
    out = []
    for sub in submissions:
        name = sub.get('inspector_name') or resolve_display_name(sub.get('username', ''))
        out.append({**sub, 'inspector_name': name})
    return out


# Columns shared by every export format.
_EXPORT_HEADERS = ['Community', 'Region', 'Survey Type', 'Inspector',
                   'Submitted', 'Standard', 'Result', 'Comment']


def _export_rows():
    """Flatten scoped submissions into one row per question response."""
    rows = []
    for sub in _scoped_submissions_for_export():
        community = sub.get('community', '') or ''
        region = region_for_community(community)
        region_name = region.get('name', '') if region else ''
        survey_name = survey_type_service.get_survey_type_name(sub.get('survey_type_id')) or ''
        inspector = sub.get('inspector_name', '') or ''
        submitted = (sub.get('submitted_at', '') or '')[:19].replace('T', ' ')
        responses = sub.get('responses') or []
        if not responses:
            rows.append([community, region_name, survey_name, inspector, submitted, '', '', ''])
            continue
        for r in responses:
            rows.append([
                community, region_name, survey_name, inspector, submitted,
                r.get('question_text', '') or '',
                r.get('condition', '') or '',
                (r.get('description', '') or '').replace('\r', ' ').replace('\n', ' '),
            ])
    return rows


def _export_filename(ext):
    return f"atlas-inspections-{datetime.now().strftime('%Y%m%d')}.{ext}"


def _export_summary():
    """Aggregate stats for the summary section of every export, computed from the
    same role-scoped submissions as the detail rows."""
    subs = _scoped_submissions_for_export()
    total_visits = len(subs)
    passes = fails = total_responses = 0
    by_type = {}        # survey_type_id -> count of responses
    performers = {}     # inspector -> {visits, last}
    for sub in subs:
        stid = sub.get('survey_type_id')
        responses = sub.get('responses') or []
        for r in responses:
            total_responses += 1
            cond = (r.get('condition') or '')
            if cond == 'Pass':
                passes += 1
            elif cond == 'Fail':
                fails += 1
            if stid:
                by_type[stid] = by_type.get(stid, 0) + 1
        name = sub.get('inspector_name') or 'Unknown'
        p = performers.setdefault(name, {'visits': 0, 'last': ''})
        p['visits'] += 1
        sa = (sub.get('submitted_at') or '')
        if sa > p['last']:
            p['last'] = sa

    by_survey_type = sorted(
        [(survey_type_service.get_survey_type_name(k) or k, v) for k, v in by_type.items()],
        key=lambda x: x[1], reverse=True)
    top_performers = sorted(
        [(n, d['visits'], (d['last'] or '')[:10]) for n, d in performers.items()],
        key=lambda x: x[1], reverse=True)[:10]

    pass_rate = round(passes / total_responses * 100) if total_responses else 0
    return {
        'total_visits': total_visits,
        'total_responses': total_responses,
        'passes': passes, 'fails': fails, 'pass_rate': pass_rate,
        'by_survey_type': by_survey_type,
        'top_performers': top_performers,
    }


@app.route('/api/reports/export.csv')
@login_required
def export_reports_csv():
    """Download the inspection report data as CSV (role-scoped)."""
    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)

    # --- Summary block ---
    s = _export_summary()
    writer.writerow(['Atlas Senior Living — Inspection Report'])
    writer.writerow(['Generated', datetime.now().strftime('%Y-%m-%d %H:%M')])
    writer.writerow([])
    writer.writerow(['Total visits', s['total_visits']])
    writer.writerow(['Total responses', s['total_responses']])
    writer.writerow(['Pass', s['passes']])
    writer.writerow(['Fail', s['fails']])
    writer.writerow(['Pass rate', f"{s['pass_rate']}%"])
    writer.writerow([])
    writer.writerow(['Survey type', 'Responses'])
    for name, count in s['by_survey_type']:
        writer.writerow([name, count])
    writer.writerow([])
    writer.writerow(['Top performers', 'Visits', 'Last visit'])
    for name, visits, last in s['top_performers']:
        writer.writerow([name, visits, last])
    writer.writerow([])
    writer.writerow(['DETAIL'])

    # --- Detail table ---
    writer.writerow(_EXPORT_HEADERS)
    writer.writerows(_export_rows())
    from flask import Response
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{_export_filename("csv")}"'},
    )


@app.route('/api/reports/export.xlsx')
@login_required
def export_reports_xlsx():
    """Download the inspection report data as a styled Excel workbook."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    header_fill = PatternFill('solid', fgColor='00285C')
    header_font = Font(bold=True, color='FFFFFF')

    wb = Workbook()

    # ---------- Summary sheet ----------
    summ = wb.active
    summ.title = 'Summary'
    s = _export_summary()
    title_font = Font(bold=True, size=14, color='00285C')
    label_font = Font(bold=True)

    summ['A1'] = 'Atlas Senior Living — Inspection Report'
    summ['A1'].font = title_font
    summ['A2'] = f"Generated {datetime.now().strftime('%B %d, %Y %H:%M')}"
    summ['A2'].font = Font(italic=True, color='6B7280')

    kpis = [('Total visits', s['total_visits']), ('Total responses', s['total_responses']),
            ('Pass', s['passes']), ('Fail', s['fails']), ('Pass rate', f"{s['pass_rate']}%")]
    row = 4
    for label, val in kpis:
        summ.cell(row=row, column=1, value=label).font = label_font
        summ.cell(row=row, column=2, value=val)
        row += 1

    row += 1
    summ.cell(row=row, column=1, value='Survey Type Breakdown').font = title_font
    row += 1
    summ.cell(row=row, column=1, value='Survey type').font = header_font
    summ.cell(row=row, column=1).fill = header_fill
    summ.cell(row=row, column=2, value='Responses').font = header_font
    summ.cell(row=row, column=2).fill = header_fill
    row += 1
    for name, count in s['by_survey_type']:
        summ.cell(row=row, column=1, value=name)
        summ.cell(row=row, column=2, value=count)
        row += 1

    row += 1
    summ.cell(row=row, column=1, value='Top Performers').font = title_font
    row += 1
    for col, h in enumerate(['Team member', 'Visits', 'Last visit'], start=1):
        c = summ.cell(row=row, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
    row += 1
    for name, visits, last in s['top_performers']:
        summ.cell(row=row, column=1, value=name)
        summ.cell(row=row, column=2, value=visits)
        summ.cell(row=row, column=3, value=last)
        row += 1

    summ.column_dimensions['A'].width = 30
    summ.column_dimensions['B'].width = 14
    summ.column_dimensions['C'].width = 16

    # ---------- Detail sheet ----------
    ws = wb.create_sheet('Inspections')
    for col, name in enumerate(_EXPORT_HEADERS, start=1):
        c = ws.cell(row=1, column=col, value=name)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(vertical='center')

    rows = _export_rows()
    for r in rows:
        ws.append(r)

    # Color the Result cells (Pass green, Fail red).
    pass_font = Font(color='0F8A5F', bold=True)
    fail_font = Font(color='D13212', bold=True)
    for i in range(len(rows)):
        cell = ws.cell(row=i + 2, column=7)  # Result column
        if (cell.value or '') == 'Pass':
            cell.font = pass_font
        elif (cell.value or '') == 'Fail':
            cell.font = fail_font

    widths = [26, 16, 20, 20, 19, 44, 9, 50]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = 'A2'

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(
        out, as_attachment=True, download_name=_export_filename('xlsx'),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@app.route('/api/reports/export.pdf')
@login_required
def export_reports_pdf():
    """Download the inspection report data as a PDF table (role-scoped)."""
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer)

    rows = _export_rows()
    styles = getSampleStyleSheet()
    cell = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7.5, leading=9)
    head = ParagraphStyle('head', parent=styles['Normal'], fontSize=8,
                          leading=10, textColor=colors.white, fontName='Helvetica-Bold')

    # Build a Paragraph-wrapped table so long text wraps instead of overflowing.
    table_data = [[Paragraph(h, head) for h in _EXPORT_HEADERS]]
    for r in rows:
        table_data.append([Paragraph((str(v) if v is not None else ''), cell) for v in r])

    col_widths = [1.5 * inch, 0.9 * inch, 1.2 * inch, 1.2 * inch, 1.05 * inch,
                  2.4 * inch, 0.55 * inch, 2.6 * inch]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                            leftMargin=0.4 * inch, rightMargin=0.4 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    summ = _export_summary()
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], textColor=colors.HexColor('#00285c'),
                        spaceBefore=10, spaceAfter=6)
    story = [
        Paragraph('Atlas Senior Living — Inspection Report', styles['Title']),
        Paragraph(f"Generated {datetime.now().strftime('%B %d, %Y %H:%M')} · {len(rows)} rows",
                  styles['Normal']),
        Spacer(1, 8),
    ]

    # ---- Summary section ----
    kpi_data = [[
        Paragraph('<b>Total visits</b>', cell), Paragraph('<b>Total responses</b>', cell),
        Paragraph('<b>Pass</b>', cell), Paragraph('<b>Fail</b>', cell),
        Paragraph('<b>Pass rate</b>', cell),
    ], [
        Paragraph(str(summ['total_visits']), cell), Paragraph(str(summ['total_responses']), cell),
        Paragraph(f"<font color='#0f8a5f'>{summ['passes']}</font>", cell),
        Paragraph(f"<font color='#d13212'>{summ['fails']}</font>", cell),
        Paragraph(f"{summ['pass_rate']}%", cell),
    ]]
    kpi_tbl = Table(kpi_data, colWidths=[1.6 * inch] * 5)
    kpi_tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9dfe8')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f7')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_tbl)

    if summ['by_survey_type']:
        story.append(Paragraph('Survey Type Breakdown', h2))
        st_data = [[Paragraph('<b>Survey type</b>', cell), Paragraph('<b>Responses</b>', cell)]]
        st_data += [[Paragraph(n, cell), Paragraph(str(c), cell)] for n, c in summ['by_survey_type']]
        st_tbl = Table(st_data, colWidths=[3.5 * inch, 1.2 * inch])
        st_tbl.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9dfe8')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f7')),
        ]))
        story.append(st_tbl)

    if summ['top_performers']:
        story.append(Paragraph('Top Performers', h2))
        tp_data = [[Paragraph('<b>Team member</b>', cell), Paragraph('<b>Visits</b>', cell),
                    Paragraph('<b>Last visit</b>', cell)]]
        tp_data += [[Paragraph(n, cell), Paragraph(str(v), cell), Paragraph(l, cell)]
                    for n, v, l in summ['top_performers']]
        tp_tbl = Table(tp_data, colWidths=[3 * inch, 1 * inch, 1.4 * inch])
        tp_tbl.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9dfe8')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f7')),
        ]))
        story.append(tp_tbl)

    story.append(Paragraph('Detailed Responses', h2))
    if rows:
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00285c')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9dfe8')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fb')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph('No inspection data available.', styles['Normal']))

    doc.build(story)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=_export_filename('pdf'),
                     mimetype='application/pdf')


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(401)
def unauthorized(error):
    """Handle 401 errors - redirect to login"""
    return redirect(url_for('login')), 401


# ==================== MAIN ====================

if __name__ == '__main__':
    # Local development server only. In production the app is served by gunicorn
    # (see deploy/), which imports `app` directly and ignores this block.
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'  # off by default; set FLASK_DEBUG=1 for local dev
    app.run(host='0.0.0.0', port=port, debug=debug)
