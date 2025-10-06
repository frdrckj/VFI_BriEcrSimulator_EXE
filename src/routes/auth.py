from flask import Blueprint, jsonify, request, session, current_app
from src.models.user import User, db
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403

        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        }), 200

    return jsonify({'error': 'Invalid username or password'}), 401

@auth_bp.route('/register', methods=['POST'])
@admin_required
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    is_admin = data.get('is_admin', False)

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict()
    }), 201

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    # Check if login is required from main app config
    require_login = current_app.config.get('REQUIRE_LOGIN', True)

    if not require_login:
        # Return authenticated with dummy user when login is disabled
        return jsonify({
            'authenticated': True,
            'user': {'username': 'dev-mode', 'is_admin': False}
        }), 200

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return jsonify({
                'authenticated': True,
                'user': user.to_dict()
            }), 200

    return jsonify({'authenticated': False}), 200

@auth_bp.route('/init-admin', methods=['POST'])
def init_admin():
    # Check if any users exist
    if User.query.first():
        return jsonify({'error': 'Admin already initialized'}), 400

    # Create default admin user
    admin = User(username='admin', is_admin=True)
    admin.set_password('P@ssw0rd')
    db.session.add(admin)
    db.session.commit()

    return jsonify({'message': 'Admin user created successfully'}), 201
