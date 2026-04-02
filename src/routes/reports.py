"""Reports & analytics routes: /api/reports"""
from flask import Blueprint, jsonify
from src.db.init_db import get_db
from src.middleware.auth import require_auth, require_permission

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.get("/dashboard")
@require_auth
@require_permission("VIEW_REPORTS")
def dashboard():
    """Leadership dashboard KPIs."""
    db = get_db()

    total_active_subs = db.execute("""
        SELECT COUNT(*) FROM subscription
        WHERE renewal_date IS NOT NULL AND renewal_date >= DATE('now')
    """).fetchone()[0]

    unique_active_customers = db.execute("""
        SELECT COUNT(DISTINCT cus_id) FROM subscription
        WHERE renewal_date IS NOT NULL AND renewal_date >= DATE('now')
    """).fetchone()[0]

    current_month_revenue = db.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM payment_transaction
        WHERE payment_status = 'Completed'
          AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    """).fetchone()[0]

    current_month_failed = db.execute("""
        SELECT COUNT(*) FROM payment_transaction
        WHERE payment_status = 'Failed'
          AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    """).fetchone()[0]

    orders_awaiting = db.execute("""
        SELECT COUNT(*) FROM customer_order
        WHERE order_status IN ('Pending', 'Packed')
    """).fetchone()[0]

    regions_served = db.execute("""
        SELECT COUNT(DISTINCT province) FROM address
    """).fetchone()[0]

    db.close()
    return jsonify({
        "total_active_subscriptions": total_active_subs,
        "unique_active_customers": unique_active_customers,
        "current_month_revenue": float(current_month_revenue),
        "current_month_failed_payments": current_month_failed,
        "orders_awaiting_shipment": orders_awaiting,
        "regions_served": regions_served,
    })


@reports_bp.get("/subscribers/active")
@require_auth
@require_permission("VIEW_REPORTS")
def active_subscribers():
    """Active subscriber summary by plan."""
    db = get_db()
    rows = db.execute("""
        SELECT sp.plan_name,
               COUNT(DISTINCT s.subscription_id) AS active_subscriptions,
               COUNT(DISTINCT s.cus_id)          AS unique_customers
        FROM subscription s
        JOIN subscription_plan sp ON s.plan_id = sp.plan_id
        WHERE s.renewal_date IS NOT NULL AND s.renewal_date >= DATE('now')
        GROUP BY sp.plan_name
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/subscribers/growth")
@require_auth
@require_permission("VIEW_REPORTS")
def subscriber_growth():
    """Cumulative subscriber growth month over month."""
    db = get_db()
    rows = db.execute("""
        SELECT strftime('%Y-%m', s.start_date) AS signup_month,
               COUNT(*) AS new_subscriptions
        FROM subscription s
        GROUP BY signup_month
        ORDER BY signup_month
    """).fetchall()
    db.close()

    # Compute cumulative in Python
    cumulative = 0
    result = []
    for r in rows:
        cumulative += r["new_subscriptions"]
        result.append({**dict(r), "cumulative_subscriptions": cumulative})
    return jsonify(result)


@reports_bp.get("/subscribers/churn")
@require_auth
@require_permission("VIEW_REPORTS")
def churn_rate():
    """Monthly churn rate."""
    db = get_db()
    rows = db.execute("""
        WITH monthly_cancellations AS (
            SELECT strftime('%Y-%m', event_date) AS churn_month,
                   COUNT(*) AS cancellations
            FROM subscription_event
            WHERE event_type = 'Cancelled'
            GROUP BY churn_month
        ),
        monthly_active AS (
            SELECT strftime('%Y-%m', co.created_at) AS active_month,
                   COUNT(DISTINCT s.subscription_id) AS active_subs
            FROM customer_order co
            JOIN subscription s ON co.subscription_id = s.subscription_id
            GROUP BY active_month
        )
        SELECT ma.active_month,
               ma.active_subs,
               COALESCE(mc.cancellations, 0) AS cancellations,
               ROUND(CAST(COALESCE(mc.cancellations,0) AS FLOAT)
                   / ma.active_subs * 100, 2) AS churn_rate_pct
        FROM monthly_active ma
        LEFT JOIN monthly_cancellations mc ON ma.active_month = mc.churn_month
        ORDER BY ma.active_month
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/revenue/by-plan")
@require_auth
@require_permission("VIEW_REPORTS")
def revenue_by_plan():
    """Revenue broken down by subscription plan."""
    db = get_db()
    rows = db.execute("""
        SELECT sp.plan_name,
               COUNT(pt.transaction_id)                          AS total_transactions,
               ROUND(SUM(pt.amount), 2)                         AS gross_revenue,
               ROUND(SUM(pt.tax_amount), 2)                     AS total_tax,
               ROUND(SUM(COALESCE(pt.discount_amount, 0)), 2)   AS total_discounts,
               ROUND(SUM(pt.amount) - SUM(COALESCE(pt.discount_amount,0)), 2) AS net_revenue
        FROM payment_transaction pt
        JOIN subscription s ON pt.subscription_id = s.subscription_id
        JOIN subscription_plan sp ON s.plan_id = sp.plan_id
        WHERE pt.payment_status = 'Completed'
        GROUP BY sp.plan_name
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/revenue/monthly")
@require_auth
@require_permission("VIEW_REPORTS")
def monthly_revenue():
    """Monthly revenue summary."""
    db = get_db()
    rows = db.execute("""
        SELECT strftime('%Y-%m', created_at) AS revenue_month,
               ROUND(SUM(CASE WHEN payment_status='Completed' THEN amount ELSE 0 END), 2) AS completed_revenue,
               ROUND(SUM(CASE WHEN payment_status='Refunded'  THEN amount ELSE 0 END), 2) AS refunded_amount,
               ROUND(SUM(CASE WHEN payment_status='Failed'    THEN amount ELSE 0 END), 2) AS failed_amount,
               ROUND(SUM(CASE WHEN payment_status='Completed' THEN tax_amount ELSE 0 END), 2) AS tax_collected,
               COUNT(CASE WHEN payment_status='Failed' THEN 1 END) AS failed_count
        FROM payment_transaction
        GROUP BY revenue_month
        ORDER BY revenue_month
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/revenue/by-region")
@require_auth
@require_permission("VIEW_REPORTS")
def revenue_by_region():
    """Revenue by geographic region."""
    db = get_db()
    rows = db.execute("""
        SELECT a.province AS region,
               pt.currency_code,
               COUNT(pt.transaction_id) AS total_transactions,
               ROUND(SUM(pt.amount), 2) AS gross_revenue,
               ROUND(SUM(pt.tax_amount), 2) AS total_tax_collected
        FROM payment_transaction pt
        JOIN customer_order co ON pt.order_id = co.order_id
        JOIN subscription s ON co.subscription_id = s.subscription_id
        JOIN customer cu ON s.cus_id = cu.customer_id
        JOIN address a ON cu.customer_id = a.acc_id
        WHERE pt.payment_status = 'Completed'
        GROUP BY a.province, pt.currency_code
        ORDER BY gross_revenue DESC
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/fulfillment/by-release")
@require_auth
@require_permission("VIEW_REPORTS")
def fulfillment_by_release():
    """Units shipped per box type per release period."""
    db = get_db()
    rows = db.execute("""
        SELECT t.theme_name,
               strftime('%Y-%m', br.release_month) AS release_period,
               COUNT(co.order_id) AS total_orders,
               SUM(CASE WHEN co.order_status='Delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN co.order_status='Shipped'   THEN 1 ELSE 0 END) AS shipped,
               SUM(CASE WHEN co.order_status='Packed'    THEN 1 ELSE 0 END) AS packed,
               SUM(CASE WHEN co.order_status='Pending'   THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN co.order_status='Failed'    THEN 1 ELSE 0 END) AS failed
        FROM customer_order co
        JOIN box_release br ON co.release_id = br.release_id
        JOIN theme t ON br.theme_id = t.theme_id
        GROUP BY t.theme_name, release_period
        ORDER BY release_period DESC, t.theme_name
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/fulfillment/shipment-performance")
@require_auth
@require_permission("VIEW_REPORTS")
def shipment_performance():
    """Average delivery days per theme per release."""
    db = get_db()
    rows = db.execute("""
        SELECT t.theme_name,
               strftime('%Y-%m', br.release_month) AS release_period,
               COUNT(sh.shipment_id) AS total_shipments,
               SUM(CASE WHEN sh.shipment_status='Delivered' THEN 1 ELSE 0 END) AS delivered,
               ROUND(AVG(CASE
                   WHEN sh.delivered_date IS NOT NULL AND sh.shipped_date IS NOT NULL
                   THEN julianday(sh.delivered_date) - julianday(sh.shipped_date)
               END), 1) AS avg_delivery_days
        FROM shipment sh
        JOIN customer_order co ON sh.order_id = co.order_id
        JOIN box_release br ON co.release_id = br.release_id
        JOIN theme t ON br.theme_id = t.theme_id
        GROUP BY t.theme_name, release_period
        ORDER BY release_period DESC
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/inventory/overview")
@require_auth
@require_permission("VIEW_INVENTORY")
def inventory_overview():
    """Full inventory overview with stock status."""
    db = get_db()
    rows = db.execute("""
        SELECT p.product_name, p.product_price, p.product_cost, w.warehouse_name,
               i.quantity_availability, i.quantity_reserved, i.quantity_damaged,
               (i.quantity_availability - i.quantity_reserved) AS net_available,
               CASE
                   WHEN (i.quantity_availability - i.quantity_reserved) <= 0 THEN 'Out of Stock'
                   WHEN (i.quantity_availability - i.quantity_reserved) < 500 THEN 'Low Stock'
                   ELSE 'In Stock'
               END AS stock_status
        FROM inventory i
        JOIN product p ON i.product_id = p.product_id
        JOIN warehouse w ON i.warehouse_id = w.warehouse_id
        ORDER BY stock_status, p.product_name
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/inventory/damaged")
@require_auth
@require_permission("VIEW_INVENTORY")
def damaged_inventory():
    """Damaged inventory with damage rate percentage."""
    db = get_db()
    rows = db.execute("""
        SELECT w.warehouse_name, p.product_name, i.quantity_damaged,
               ROUND(CAST(i.quantity_damaged AS FLOAT)
                   / (i.quantity_availability + i.quantity_reserved + i.quantity_damaged) * 100, 2)
                   AS damage_rate_pct
        FROM inventory i
        JOIN product p ON i.product_id = p.product_id
        JOIN warehouse w ON i.warehouse_id = w.warehouse_id
        WHERE i.quantity_damaged > 0
        ORDER BY damage_rate_pct DESC
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/themes/popularity")
@require_auth
@require_permission("VIEW_REPORTS")
def theme_popularity():
    """Fandom / theme popularity by customers and orders."""
    db = get_db()
    rows = db.execute("""
        SELECT t.theme_name,
               COUNT(DISTINCT ct.customer_id) AS customers_interested,
               COUNT(DISTINCT co.order_id)    AS total_orders_placed
        FROM theme t
        LEFT JOIN customer_theme ct ON t.theme_id = ct.theme_id
        LEFT JOIN box_release br ON t.theme_id = br.theme_id
        LEFT JOIN customer_order co ON br.release_id = co.release_id
        GROUP BY t.theme_name
        ORDER BY customers_interested DESC
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@reports_bp.get("/audit-log")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def audit_log():
    """Recent audit log entries."""
    db = get_db()
    limit = min(200, int(request.args.get("limit", 50)) if hasattr(jsonify, '__module__') else 50)
    from flask import request as req
    limit = min(200, req.args.get("limit", 50, type=int))
    rows = db.execute("""
        SELECT al.*, su.username FROM audit_log al
        LEFT JOIN system_user su ON al.user_id = su.user_id
        ORDER BY al.audit_id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])
