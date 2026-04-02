"""Product & inventory routes: /api/products, /api/inventory"""
from flask import Blueprint, request, jsonify, g
from src.db.init_db import get_db
from src.middleware.auth import require_auth, require_permission

products_bp = Blueprint("products", __name__, url_prefix="/api/products")
inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


# ── PRODUCTS ──────────────────────────────────────────────────────────────────

@products_bp.get("/")
@require_auth
def list_products():
    db = get_db()
    fandom_id = request.args.get("fandom_id", type=int)
    in_stock = request.args.get("in_stock")

    where_parts = []
    params = []

    if fandom_id:
        where_parts.append("p.product_fandom_id = ?")
        params.append(fandom_id)
    if in_stock == "true":
        where_parts.append("p.product_stock > 0")

    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    rows = db.execute(f"""
        SELECT p.*, t.theme_name FROM product p
        LEFT JOIN theme t ON p.product_fandom_id = t.theme_id
        {where}
        ORDER BY p.product_name
    """, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@products_bp.get("/<int:product_id>")
@require_auth
def get_product(product_id):
    db = get_db()
    product = db.execute("""
        SELECT p.*, t.theme_name FROM product p
        LEFT JOIN theme t ON p.product_fandom_id = t.theme_id
        WHERE p.product_id = ?
    """, (product_id,)).fetchone()

    if not product:
        db.close()
        return jsonify({"error": "Product not found"}), 404

    inventory = db.execute("""
        SELECT i.*, w.warehouse_name FROM inventory i
        JOIN warehouse w ON i.warehouse_id = w.warehouse_id
        WHERE i.product_id = ?
    """, (product_id,)).fetchall()

    db.close()
    return jsonify({**dict(product), "inventory": [dict(i) for i in inventory]})


@products_bp.post("/")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def create_product():
    data = request.get_json(silent=True) or {}
    required = ["product_name", "product_price", "product_cost", "product_fandom_id"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    db = get_db()
    try:
        cur = db.execute("""
            INSERT INTO product (product_name, product_desc, product_price, product_cost,
                product_fandom_id, product_stock)
            VALUES (?,?,?,?,?,?)
        """, (
            data["product_name"], data.get("product_desc"),
            data["product_price"], data["product_cost"],
            data["product_fandom_id"], data.get("product_stock", 0)
        ))
        db.commit()
        product_id = cur.lastrowid
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400

    db.close()
    return jsonify({"message": "Product created", "product_id": product_id}), 201


@products_bp.put("/<int:product_id>")
@require_auth
@require_permission("MANAGE_PRODUCTS")
def update_product(product_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    if not db.execute("SELECT 1 FROM product WHERE product_id = ?", (product_id,)).fetchone():
        db.close()
        return jsonify({"error": "Product not found"}), 404

    allowed = ["product_name", "product_desc", "product_price", "product_cost",
               "product_fandom_id", "product_stock"]
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        db.close()
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    db.execute(f"UPDATE product SET {set_clause} WHERE product_id = ?",
               list(updates.values()) + [product_id])
    db.commit()
    db.close()
    return jsonify({"message": "Product updated"})


# ── INVENTORY ─────────────────────────────────────────────────────────────────

@inventory_bp.get("/")
@require_auth
@require_permission("VIEW_INVENTORY")
def list_inventory():
    db = get_db()
    warehouse_id = request.args.get("warehouse_id", type=int)
    low_stock = request.args.get("low_stock")

    where_parts = []
    params = []

    if warehouse_id:
        where_parts.append("i.warehouse_id = ?")
        params.append(warehouse_id)
    if low_stock == "true":
        where_parts.append("(i.quantity_availability - i.quantity_reserved) < 500")

    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    rows = db.execute(f"""
        SELECT i.*, p.product_name, p.product_price, w.warehouse_name,
               (i.quantity_availability - i.quantity_reserved) AS net_available,
               CASE
                   WHEN (i.quantity_availability - i.quantity_reserved) <= 0 THEN 'Out of Stock'
                   WHEN (i.quantity_availability - i.quantity_reserved) < 500 THEN 'Low Stock'
                   ELSE 'In Stock'
               END AS stock_status
        FROM inventory i
        JOIN product p ON i.product_id = p.product_id
        JOIN warehouse w ON i.warehouse_id = w.warehouse_id
        {where}
        ORDER BY p.product_name, w.warehouse_name
    """, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@inventory_bp.patch("/<int:inventory_id>")
@require_auth
@require_permission("EDIT_INVENTORY")
def update_inventory(inventory_id):
    data = request.get_json(silent=True) or {}
    db = get_db()

    existing = db.execute("SELECT * FROM inventory WHERE inventory_id = ?", (inventory_id,)).fetchone()
    if not existing:
        db.close()
        return jsonify({"error": "Inventory record not found"}), 404

    allowed = ["quantity_availability", "quantity_reserved", "quantity_damaged"]
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        db.close()
        return jsonify({"error": "No valid fields to update"}), 400

    old_value = {k: existing[k] for k in allowed if k in dict(existing)}
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    db.execute(f"UPDATE inventory SET {set_clause} WHERE inventory_id = ?",
               list(updates.values()) + [inventory_id])
    db.execute(
        "INSERT INTO audit_log (user_id,entity_name,entity_id,action_type,old_value,new_value) VALUES (?,?,?,?,?,?)",
        (g.user["user_id"], "inventory", inventory_id, "UPDATE", str(old_value), str(updates))
    )
    db.commit()
    db.close()
    return jsonify({"message": "Inventory updated"})


@inventory_bp.get("/warehouses")
@require_auth
@require_permission("VIEW_INVENTORY")
def list_warehouses():
    db = get_db()
    warehouses = db.execute("SELECT * FROM warehouse ORDER BY warehouse_name").fetchall()
    db.close()
    return jsonify([dict(w) for w in warehouses])
