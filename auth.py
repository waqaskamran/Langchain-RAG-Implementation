from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
from models import db, User, Role
from datetime import timedelta
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from models import db, User, Role
from datetime import timedelta

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/auth')

def get_or_create_role(role_name):
    """Return existing Role or create it (committed in caller)."""
    role_name = role_name.strip().lower()
    if not role_name:
        return None
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name)
        db.session.add(role)
        # do not commit here; caller will commit once
    return role

def normalize_roles_input(raw):
    """
    Accept:
      - list: ["admin","manager"]
      - string: "admin" or "admin,manager"
    Return list of normalized role names.
    """
    if not raw:
        return []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        # support comma separated or single role
        items = [r.strip() for r in raw.split(',') if r.strip()]
    else:
        # unsupported type
        return []
    # normalize to lowercase unique
    seen = []
    for it in items:
        n = it.lower().strip()
        if n and n not in seen:
            seen.append(n)
    return seen


from models import User, Role, db

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    password = data.get('password')
    role_names = data.get('roles', ['applicant'])

    print(f"DEBUG - role_names after get: {role_names}")


    # Ensure role_names is a list
    if isinstance(role_names, str):
        role_names = [role_names]

    if not all([first_name, email, password]):
        return jsonify({"error": "Missing required fields"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    hashed_pw = generate_password_hash(password)

    # Fetch or create roles
    roles = []
    for role_name in role_names:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            # optional: auto-create role
            role = Role(name=role_name)
            db.session.add(role)
        roles.append(role)

    # Create user and assign roles
    new_user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=hashed_pw,
        roles=roles  # ✅ assign properly
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "User registered successfully",
        "roles": [r.name for r in new_user.roles]
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    if not (email and password):
        return jsonify({"error": "Missing credentials"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    role_names = [r.name for r in user.roles]

    # ✅ Include user info and roles in the token
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'roles': role_names,
            'email': user.email
        }
    )

    return jsonify({
        'token': access_token,
        'roles': role_names,
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    }), 200

@auth_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    # create new access token (and optionally new refresh token)
    access = create_access_token(identity=identity)
    return jsonify(access_token=access)


# -----------------------
# Protected Route Example
# -----------------------
@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    current_user = get_jwt_identity()
    user_obj = User.query.get(current_user['id'])
    return jsonify({
        'id': user_obj.id,
        'full_name': user_obj.full_name,
        'email': user_obj.email,
        'role': user_obj.role
    })
