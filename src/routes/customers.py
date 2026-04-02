"""Customer routes: /api/customers"""
from flask import Blueprint, request, jsonify, g
from src.db.init_db import get_db
from src.middleware.auth import require_auth, require_permission

customers_bp = Blueprint("customers", __name__, url_prefix="/api/customers")


def _row_to_dict(row):
    return dict(row) if row else None


@customers_bp.get("/")
@require_auth
@require_permission("VIEW_CUSTOMERS")
def list_customers():
    db = get_db()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, request.args.get("per_page", 20, type=int))
    search = request.args.get("search", "").strip()
    offset = (page - 1) * per_page

    base_q = """
        FROM customer c
        LEFT JOIN theme t ON c.accnt_theme_id = t.theme_id
    """
    where = ""
    params = []
    if search:
        where = "WHERE c.first_name LIKE ? OR c.last_name LIKE ? OR c.email LIKE ?"
        s = f"%{search}%"
        params = [s, s, s]

    total = db.execute(f"SELECT COUNT(*) {base_q} {where}", params).fetchone()[0]
    rows = db.execute(
        f"""SELECT c.*, t.theme_name {base_q} {where}
            ORDER BY c.customer_id LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    ).fetchall()
    db.close()

    return jsonify({
        "data": [dict(r) for r in rows],
        "pagination": {"page": page, "per_page": per_page, "total": total,
                       "pages": (total + per_page - 1) // per_page}
    })


@customers_bp.get("/<int:customer_id>")
@require_auth
@require_permission("VIEW_CUSTOMERS")
def get_customer(customer_id):
    db = get_db()
    customer = db.execute(
        """SELECT c.*, t.theme_name FROM customer c
           LEFT JOIN theme t ON c.accnt_theme_id = t.theme_id
           WHERE c.customer_id = ?""",
        (customer_id,)
    ).fetchone()

    if not customer:
        db.close()
        return jsonify({"error": "Customer not found"}), 404

    addresses = db.execute(
        "SELECT * FROM address WHERE acc_id = ?", (customer_id,)
    ).fetchall()

    billing = db.execute(
        "SELECT * FROM billing_address WHERE acc_id = ?", (customer_id,)
    ).fetchall()

    themes = db.execute("""
        SELECT t.theme_id, t.theme_name FROM customer_theme ct
        JOIN theme t ON ct.theme_id = t.theme_id
        WHERE ct.customer_id = ?
    """, (customer_id,)).fetchall()

    ratings = db.execute("""
        SELECT cr.rating_id, cr.rating_name FROM customer_content_rating ccr
        JOIN content_rating cr ON ccr.rating_id = cr.rating_id
        WHERE ccr.customer_id = ?
    """, (customer_id,)).fetchall()

    subscriptions = db.execute("""
        SELECT s.*, sp.plan_name, sp.price FROM subscription s
        JOIN subscription_plan sp ON s.plan_id = sp.plan_id
        WHERE s.cus_id = ?
        ORDER BY s.start_date DESC
    """, (customer_id,)).fetchall()

    db.close()

    return jsonify({
        **dict(customer),
        "addresses": [dict(a) for a in addresses],
        "billing_addresses": [dict(b) for b in billing],
        "theme_preferences": [dict(t) for t in themes],
        "content_rating_preferences": [dict(r) for r in ratings],
        "subscriptions": [dict(s) for s in subscriptions],
    })


@customers_bp.post("/")
@require_auth
@require_permission("EDIT_CUSTOMERS")
def create_customer():
    data = request.get_json(silent=True) or {}
    required = ["first_name", "last_name", "email", "birth_date", "accnt_theme_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    db = get_db()
    try:
        cur = db.execute("""
            INSERT INTO customer (first_name, last_name, email, phone_number, birth_date,
                age_restricted, accnt_theme_id, clothing_size, age_rating_pref)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            data["first_name"], data["last_name"], data["email"],
            data.get("phone_number"), data["birth_date"],
            int(data.get("age_restricted", 0)), data["accnt_theme_id"],
            data.get("clothing_size"), data.get("age_rating_pref", "ALL")
        ))
        db.commit()
        customer_id = cur.lastrowid
    except Exception as e:
        db.close()
        if "UNIQUE" in str(e):
            return jsonify({"error": "Email already exists"}), 409
        return jsonify({"error": str(e)}), 400

    db.close()
    return jsonify({"message": "Customer created", "customer_id": customer_id}), 201


@customers_bp.put("/<int:customer_id>")
@require_auth
@require_permission("EDIT_CUSTOMERS")
def update_customer(customer_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    existing = db.execute("SELECT 1 FROM customer WHERE customer_id = ?", (customer_id,)).fetchone()
    if not existing:
        db.close()
        return jsonify({"error": "Customer not found"}), 404

    allowed = ["first_name", "last_name", "email", "phone_number",
               "clothing_size", "age_rating_pref", "accnt_theme_id", "age_restricted"]
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        db.close()
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [customer_id]

    try:
        db.execute(f"UPDATE customer SET {set_clause} WHERE customer_id = ?", values)
        db.execute(
            "INSERT INTO audit_log (user_id,entity_name,entity_id,action_type,old_value,new_value) VALUES (?,?,?,?,?,?)",
            (g.user["user_id"], "customer", customer_id, "UPDATE", "fields updated", str(updates))
        )
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400

    db.close()
    return jsonify({"message": "Customer updated"})


@customers_bp.delete("/<int:customer_id>")
@require_auth
@require_permission("DELETE_CUSTOMERS")
def delete_customer(customer_id):
    db = get_db()
    existing = db.execute("SELECT 1 FROM customer WHERE customer_id = ?", (customer_id,)).fetchone()
    if not existing:
        db.close()
        return jsonify({"error": "Customer not found"}), 404

    # Soft delete via deactivation isn't in the schema, so we check for dependencies
    has_subs = db.execute("SELECT 1 FROM subscription WHERE cus_id = ?", (customer_id,)).fetchone()
    if has_subs:
        db.close()
        return jsonify({"error": "Cannot delete customer with active subscriptions"}), 409

    db.execute("DELETE FROM customer_theme WHERE customer_id = ?", (customer_id,))
    db.execute("DELETE FROM customer_content_rating WHERE customer_id = ?", (customer_id,))
    db.execute("DELETE FROM address WHERE acc_id = ?", (customer_id,))
    db.execute("DELETE FROM billing_address WHERE acc_id = ?", (customer_id,))
    db.execute("DELETE FROM customer WHERE customer_id = ?", (customer_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Customer deleted"})
