"""Orders & shipments routes: /api/orders, /api/shipments"""
from flask import Blueprint, request, jsonify, g
from src.db.init_db import get_db
from src.middleware.auth import require_auth, require_permission

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")
shipments_bp = Blueprint("shipments", __name__, url_prefix="/api/shipments")

VALID_ORDER_STATUSES = {"Pending", "Packed", "Shipped", "Delivered", "Failed", "Cancelled"}
VALID_SHIPMENT_STATUSES = {"Pending", "Shipped", "In Transit", "Delivered", "Failed", "Returned"}


# ── ORDERS ────────────────────────────────────────────────────────────────────

@orders_bp.get("/")
@require_auth
@require_permission("VIEW_ORDERS")
def list_orders():
    db = get_db()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, request.args.get("per_page", 20, type=int))
    status = request.args.get("status")
    offset = (page - 1) * per_page

    where_parts = []
    params = []
    if status:
        where_parts.append("co.order_status = ?")
        params.append(status)

    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    base_q = f"""
        FROM customer_order co
        JOIN subscription s ON co.subscription_id = s.subscription_id
        JOIN customer c ON s.cus_id = c.customer_id
        JOIN box_release br ON co.release_id = br.release_id
        JOIN theme t ON br.theme_id = t.theme_id
        {where}
    """
    total = db.execute(f"SELECT COUNT(*) {base_q}", params).fetchone()[0]
    rows = db.execute(f"""
        SELECT co.*, c.first_name, c.last_name, c.email,
               t.theme_name, br.release_month
        {base_q}
        ORDER BY co.created_at DESC LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()
    db.close()

    return jsonify({
        "data": [dict(r) for r in rows],
        "pagination": {"page": page, "per_page": per_page, "total": total,
                       "pages": (total + per_page - 1) // per_page}
    })


@orders_bp.get("/<int:order_id>")
@require_auth
@require_permission("VIEW_ORDERS")
def get_order(order_id):
    db = get_db()
    order = db.execute("""
        SELECT co.*, c.first_name, c.last_name, c.email,
               t.theme_name, br.release_month, br.is_spoiler_visible,
               sp.plan_name
        FROM customer_order co
        JOIN subscription s ON co.subscription_id = s.subscription_id
        JOIN subscription_plan sp ON s.plan_id = sp.plan_id
        JOIN customer c ON s.cus_id = c.customer_id
        JOIN box_release br ON co.release_id = br.release_id
        JOIN theme t ON br.theme_id = t.theme_id
        WHERE co.order_id = ?
    """, (order_id,)).fetchone()

    if not order:
        db.close()
        return jsonify({"error": "Order not found"}), 404

    shipments = db.execute(
        "SELECT * FROM shipment WHERE order_id = ? ORDER BY shipped_date DESC",
        (order_id,)
    ).fetchall()

    transactions = db.execute(
        "SELECT * FROM payment_transaction WHERE order_id = ?",
        (order_id,)
    ).fetchall()

    db.close()
    return jsonify({
        **dict(order),
        "shipments": [dict(s) for s in shipments],
        "transactions": [dict(t) for t in transactions],
    })


@orders_bp.patch("/<int:order_id>/status")
@require_auth
@require_permission("EDIT_ORDERS")
def update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("order_status")
    if new_status not in VALID_ORDER_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(VALID_ORDER_STATUSES)}"}), 400

    db = get_db()
    existing = db.execute("SELECT order_status FROM customer_order WHERE order_id = ?", (order_id,)).fetchone()
    if not existing:
        db.close()
        return jsonify({"error": "Order not found"}), 404

    db.execute("UPDATE customer_order SET order_status = ? WHERE order_id = ?", (new_status, order_id))
    db.execute(
        "INSERT INTO audit_log (user_id,entity_name,entity_id,action_type,old_value,new_value) VALUES (?,?,?,?,?,?)",
        (g.user["user_id"], "customer_order", order_id, "UPDATE",
         f"status: {existing['order_status']}", f"status: {new_status}")
    )
    db.commit()
    db.close()
    return jsonify({"message": f"Order status updated to {new_status}"})


# ── SHIPMENTS ─────────────────────────────────────────────────────────────────

@shipments_bp.get("/")
@require_auth
@require_permission("VIEW_ORDERS")
def list_shipments():
    db = get_db()
    status = request.args.get("status")
    where = "WHERE sh.shipment_status = ?" if status else ""
    params = [status] if status else []

    rows = db.execute(f"""
        SELECT sh.*, co.order_status, c.first_name, c.last_name
        FROM shipment sh
        JOIN customer_order co ON sh.order_id = co.order_id
        JOIN subscription s ON co.subscription_id = s.subscription_id
        JOIN customer c ON s.cus_id = c.customer_id
        {where}
        ORDER BY sh.shipped_date DESC
    """, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@shipments_bp.post("/")
@require_auth
@require_permission("PROCESS_SHIPMENTS")
def create_shipment():
    data = request.get_json(silent=True) or {}
    if not data.get("order_id"):
        return jsonify({"error": "order_id is required"}), 400

    db = get_db()
    if not db.execute("SELECT 1 FROM customer_order WHERE order_id = ?", (data["order_id"],)).fetchone():
        db.close()
        return jsonify({"error": "Order not found"}), 404

    try:
        cur = db.execute("""
            INSERT INTO shipment (order_id, shipment_status, tracking_number, shipped_date, delivered_date)
            VALUES (?,?,?,?,?)
        """, (
            data["order_id"],
            data.get("shipment_status", "Pending"),
            data.get("tracking_number"),
            data.get("shipped_date"),
            data.get("delivered_date")
        ))
        shipment_id = cur.lastrowid
        # Auto-update order status when shipped
        if data.get("shipped_date"):
            db.execute("UPDATE customer_order SET order_status = 'Shipped' WHERE order_id = ?", (data["order_id"],))
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400

    db.close()
    return jsonify({"message": "Shipment created", "shipment_id": shipment_id}), 201


@shipments_bp.patch("/<int:shipment_id>")
@require_auth
@require_permission("PROCESS_SHIPMENTS")
def update_shipment(shipment_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    existing = db.execute("SELECT * FROM shipment WHERE shipment_id = ?", (shipment_id,)).fetchone()
    if not existing:
        db.close()
        return jsonify({"error": "Shipment not found"}), 404

    allowed = ["shipment_status", "tracking_number", "shipped_date", "delivered_date"]
    updates = {k: v for k, v in data.items() if k in allowed}

    if "shipment_status" in updates and updates["shipment_status"] not in VALID_SHIPMENT_STATUSES:
        db.close()
        return jsonify({"error": f"Invalid shipment status"}), 400

    if not updates:
        db.close()
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    db.execute(f"UPDATE shipment SET {set_clause} WHERE shipment_id = ?",
               list(updates.values()) + [shipment_id])

    # Sync order status when shipment is delivered
    if updates.get("shipment_status") == "Delivered":
        db.execute("UPDATE customer_order SET order_status = 'Delivered' WHERE order_id = ?",
                   (existing["order_id"],))

    db.commit()
    db.close()
    return jsonify({"message": "Shipment updated"})
