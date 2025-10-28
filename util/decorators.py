from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt,get_jwt_identity
from functools import wraps
from models import User



def role_required(*required_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            current_user_id = get_jwt_identity()
            
            # Query user from database
            user = User.query.get(int(current_user_id))
            
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            user_role_names = [r.name for r in user.roles]
            
            print(f"DEBUG - User roles from DB: {user_role_names}")
            print(f"DEBUG - Required roles: {required_roles}")
            
            # Check if user has any of the required roles
            if not any(role in user_role_names for role in required_roles):
                return jsonify({"error": "Access denied"}), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator
