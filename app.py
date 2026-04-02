"""
NerdBlock Store - REST API Backend
Flask + SQLite3

Start: python app.py
Base URL: http://localhost:5000/api
"""
import os
import sys

# Ensure imports work from project root
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify
from flask_cors import CORS

from src.db.init_db import init_db
from src.routes.auth import auth_bp
from src.routes.customers import customers_bp
from src.routes.subscriptions import subscriptions_bp
from src.routes.products import products_bp, inventory_bp
from src.routes.orders import orders_bp, shipments_bp
from src.routes.reports import reports_bp

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(customers_bp)
app.register_blueprint(subscriptions_bp)
app.register_blueprint(products_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(shipments_bp)
app.register_blueprint(reports_bp)


@app.get("/")
def root():
    return jsonify({
        "name": "NerdBlock Store API",
        "version": "1.0.0",
        "endpoints": {
            "auth":          "/api/auth/login | /api/auth/me",
            "customers":     "/api/customers",
            "subscriptions": "/api/subscriptions | /api/subscriptions/plans",
            "products":      "/api/products",
            "inventory":     "/api/inventory | /api/inventory/warehouses",
            "orders":        "/api/orders",
            "shipments":     "/api/shipments",
            "reports": {
                "dashboard":            "/api/reports/dashboard",
                "active_subscribers":   "/api/reports/subscribers/active",
                "subscriber_growth":    "/api/reports/subscribers/growth",
                "churn_rate":           "/api/reports/subscribers/churn",
                "revenue_by_plan":      "/api/reports/revenue/by-plan",
                "monthly_revenue":      "/api/reports/revenue/monthly",
                "revenue_by_region":    "/api/reports/revenue/by-region",
                "fulfillment":          "/api/reports/fulfillment/by-release",
                "shipment_performance": "/api/reports/fulfillment/shipment-performance",
                "inventory_overview":   "/api/reports/inventory/overview",
                "damaged_inventory":    "/api/reports/inventory/damaged",
                "theme_popularity":     "/api/reports/themes/popularity",
                "audit_log":            "/api/reports/audit-log",
            }
        }
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    print("Initializing NerdBlock database...")
    init_db()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"🚀 NerdBlock API running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
