"""JWT authentication middleware for NerdBlock API."""
import os
import hashlib
from functools import wraps
from flask import request, jsonify, g
import jwt

SECRET_KEY = os.environ.get("JWT_SECRET", "nerdblock-dev-secret-change-in-prod")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(user_id: int, username: str, roles: list) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "roles": roles,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def require_auth(f):
    """Decorator: verifies Bearer token and injects g.user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            g.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def require_permission(permission_code: str):
    """Decorator factory: checks g.user has the given permission via DB."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from src.db.init_db import get_db
            user_id = g.user.get("user_id")
            db = get_db()
            row = db.execute("""
                SELECT 1 FROM user_role ur
                JOIN role_permissions rp ON ur.role_id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.permission_id
                WHERE ur.user_id = ? AND p.permission_code = ?
            """, (user_id, permission_code)).fetchone()
            db.close()
            if not row:
                return jsonify({"error": f"Permission denied: {permission_code} required"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
