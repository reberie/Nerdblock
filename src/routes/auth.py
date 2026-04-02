"""Authentication routes: /api/auth"""
from flask import Blueprint, request, jsonify, g
from src.db.init_db import get_db
from src.middleware.auth import hash_password, generate_token, require_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    db = get_db()
    user = db.execute(
        "SELECT * FROM system_user WHERE username = ? AND is_active = 1", (username,)
    ).fetchone()

    if not user or user["password_hash"] != hash_password(password):
        db.close()
        return jsonify({"error": "Invalid credentials"}), 401

    roles = db.execute("""
        SELECT r.role_name FROM user_role ur
        JOIN role r ON ur.role_id = r.role_id
        WHERE ur.user_id = ?
    """, (user["user_id"],)).fetchall()
    db.close()

    role_names = [r["role_name"] for r in roles]
    token = generate_token(user["user_id"], user["username"], role_names)

    return jsonify({
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user["email"],
            "roles": role_names,
        }
    })


@auth_bp.get("/me")
@require_auth
def me():
    db = get_db()
    user = db.execute(
        "SELECT user_id, username, email, is_active, created_at FROM system_user WHERE user_id = ?",
        (g.user["user_id"],)
    ).fetchone()

    roles = db.execute("""
        SELECT r.role_name FROM user_role ur
        JOIN role r ON ur.role_id = r.role_id
        WHERE ur.user_id = ?
    """, (g.user["user_id"],)).fetchall()

    permissions = db.execute("""
        SELECT DISTINCT p.permission_code FROM user_role ur
        JOIN role_permissions rp ON ur.role_id = rp.role_id
        JOIN permissions p ON rp.permission_id = p.permission_id
        WHERE ur.user_id = ?
    """, (g.user["user_id"],)).fetchall()

    db.close()

    return jsonify({
        **dict(user),
        "roles": [r["role_name"] for r in roles],
        "permissions": [p["permission_code"] for p in permissions],
    })
