from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from decorators import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@role_required('admin')
def admin_dashboard():
    return jsonify({"message": "Welcome to Admin Dashboard"})


@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_all_users():
    # Example placeholder
    return jsonify({"message": "List of users coming soon"})
