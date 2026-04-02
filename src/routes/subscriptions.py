"""Subscription routes: /api/subscriptions"""
from flask import Blueprint, request, jsonify, g
from src.db.init_db import get_db
from src.middleware.auth import require_auth, require_permission

subscriptions_bp = Blueprint("subscriptions", __name__, url_prefix="/api/subscriptions")


@subscriptions_bp.get("/")
@require_auth
@require_permission("VIEW_SUBSCRIPTIONS")
def list_subscriptions():
    db = get_db()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, request.args.get("per_page", 20, type=int))
    status = request.args.get("status")  # "active" | "cancelled" | "paused"
    offset = (page - 1) * per_page

    where_parts = []
    params = []

    if status == "active":
        where_parts.append("s.renewal_date >= DATE('now')")
    elif status == "cancelled":
        where_parts.append("s.renewal_date IS NULL AND s.auto_renew = 0")
    elif status == "paused":
        where_parts.append("s.auto_renew = 0 AND s.renewal_date IS NOT NULL")

    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    base_q = f"""
        FROM subscription s
        JOIN subscription_plan sp ON s.plan_id = sp.plan_id
        JOIN customer c ON s.cus_id = c.customer_id
        {where}
    """
    total = db.execute(f"SELECT COUNT(*) {base_q}", params).fetchone()[0]
    rows = db.execute(f"""
        SELECT s.*, sp.plan_name, sp.price, sp.duration_months,
               c.first_name, c.last_name, c.email
        {base_q}
        ORDER BY s.start_date DESC LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()
    db.close()

    return jsonify({
        "data": [dict(r) for r in rows],
        "pagination": {"page": page, "per_page": per_page, "total": total,
                       "pages": (total + per_page - 1) // per_page}
    })


@subscriptions_bp.get("/<int:subscription_id>")
@require_auth
@require_permission("VIEW_SUBSCRIPTIONS")
def get_subscription(subscription_id):
    db = get_db()
    sub = db.execute("""
        SELECT s.*, sp.plan_name, sp.price, sp.duration_months, sp.is_prepaid,
               c.first_name, c.last_name, c.email
        FROM subscription s
        JOIN subscription_plan sp ON s.plan_id = sp.plan_id
        JOIN customer c ON s.cus_id = c.customer_id
        WHERE s.subscription_id = ?
    """, (subscription_id,)).fetchone()

    if not sub:
        db.close()
        return jsonify({"error": "Subscription not found"}), 404

    events = db.execute(
        "SELECT * FROM subscription_event WHERE subscription_id = ? ORDER BY event_date DESC",
        (subscription_id,)
    ).fetchall()

    orders = db.execute("""
        SELECT co.*, br.release_month FROM customer_order co
        JOIN box_release br ON co.release_id = br.release_id
        WHERE co.subscription_id = ? ORDER BY co.created_at DESC
    """, (subscription_id,)).fetchall()

    db.close()
    return jsonify({
        **dict(sub),
        "events": [dict(e) for e in events],
        "orders": [dict(o) for o in orders],
    })


@subscriptions_bp.post("/")
@require_auth
@require_permission("EDIT_SUBSCRIPTIONS")
def create_subscription():
    data = request.get_json(silent=True) or {}
    required = ["plan_id", "product_id", "cus_id", "start_date"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    db = get_db()
    try:
        cur = db.execute("""
            INSERT INTO subscription (plan_id, product_id, cus_id, renewal_date, start_date, auto_renew)
            VALUES (?,?,?,?,?,?)
        """, (
            data["plan_id"], data["product_id"], data["cus_id"],
            data.get("renewal_date"), data["start_date"],
            int(data.get("auto_renew", 1))
        ))
        subscription_id = cur.lastrowid
        db.execute(
            "INSERT INTO subscription_event (subscription_id, event_type, event_date) VALUES (?,?,DATE('now'))",
            (subscription_id, "Created")
        )
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400

    db.close()
    return jsonify({"message": "Subscription created", "subscription_id": subscription_id}), 201


@subscriptions_bp.patch("/<int:subscription_id>/cancel")
@require_auth
@require_permission("EDIT_SUBSCRIPTIONS")
def cancel_subscription(subscription_id):
    db = get_db()
    sub = db.execute("SELECT 1 FROM subscription WHERE subscription_id = ?", (subscription_id,)).fetchone()
    if not sub:
        db.close()
        return jsonify({"error": "Subscription not found"}), 404

    db.execute(
        "UPDATE subscription SET auto_renew = 0, renewal_date = NULL WHERE subscription_id = ?",
        (subscription_id,)
    )
    db.execute(
        "INSERT INTO subscription_event (subscription_id, event_type, event_date) VALUES (?,?,DATE('now'))",
        (subscription_id, "Cancelled")
    )
    db.execute(
        "INSERT INTO audit_log (user_id,entity_name,entity_id,action_type,old_value,new_value) VALUES (?,?,?,?,?,?)",
        (g.user["user_id"], "subscription", subscription_id, "UPDATE", "status: Active", "status: Cancelled")
    )
    db.commit()
    db.close()
    return jsonify({"message": "Subscription cancelled"})


@subscriptions_bp.patch("/<int:subscription_id>/pause")
@require_auth
@require_permission("EDIT_SUBSCRIPTIONS")
def pause_subscription(subscription_id):
    db = get_db()
    sub = db.execute("SELECT 1 FROM subscription WHERE subscription_id = ?", (subscription_id,)).fetchone()
    if not sub:
        db.close()
        return jsonify({"error": "Subscription not found"}), 404

    db.execute(
        "UPDATE subscription SET auto_renew = 0 WHERE subscription_id = ?",
        (subscription_id,)
    )
    db.execute(
        "INSERT INTO subscription_event (subscription_id, event_type, event_date) VALUES (?,?,DATE('now'))",
        (subscription_id, "Paused")
    )
    db.commit()
    db.close()
    return jsonify({"message": "Subscription paused"})


@subscriptions_bp.get("/plans")
@require_auth
def list_plans():
    db = get_db()
    plans = db.execute("SELECT * FROM subscription_plan ORDER BY price").fetchall()
    db.close()
    return jsonify([dict(p) for p in plans])
