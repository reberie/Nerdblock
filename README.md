# NerdBlock Store — Backend API

A RESTful API backend for the NerdBlock subscription box store, built with **Python Flask** and **SQLite3**. The schema is fully derived from the project's Data Dictionary and 3NF ERD.

---

## Quick Start

```bash
# Install dependencies
pip install flask flask-cors pyjwt

# Start the server
python app.py
# → http://localhost:5000
```

---

## Authentication

All protected endpoints require a **Bearer token** in the `Authorization` header.

### Login
```
POST /api/auth/login
Content-Type: application/json

{ "username": "alex.ceo", "password": "Admin123!" }
```

**Response:**
```json
{
  "token": "<jwt>",
  "user": { "user_id": 1, "username": "alex.ceo", "roles": ["Administrator", "Leadership"] }
}
```

### Get current user
```
GET /api/auth/me
Authorization: Bearer <token>
```

---

## Seeded System Users

| Username | Password | Roles |
|---|---|---|
| `alex.ceo` | `Admin123!` | Administrator, Leadership |
| `sarah.support` | `Support1!` | Customer Support |
| `mike.warehouse` | `Warehouse1!` | Warehouse Staff |
| `jenny.inventory` | `Inventory1!` | Inventory Manager |
| `omar.marketing` | `Marketing1!` | Marketing |
| `lisa.support` | `Support2!` | Customer Support |

---

## Endpoint Reference

### Customers `/api/customers`
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/customers` | VIEW_CUSTOMERS | List all (paginated, searchable) |
| GET | `/api/customers/:id` | VIEW_CUSTOMERS | Full profile incl. subs, addresses |
| POST | `/api/customers` | EDIT_CUSTOMERS | Create customer |
| PUT | `/api/customers/:id` | EDIT_CUSTOMERS | Update customer |
| DELETE | `/api/customers/:id` | DELETE_CUSTOMERS | Delete (no active subs) |

**Query params:** `page`, `per_page`, `search`

### Subscriptions `/api/subscriptions`
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/subscriptions` | VIEW_SUBSCRIPTIONS | List (filter by `status=active|cancelled|paused`) |
| GET | `/api/subscriptions/:id` | VIEW_SUBSCRIPTIONS | Detail with events & orders |
| POST | `/api/subscriptions` | EDIT_SUBSCRIPTIONS | Create subscription |
| PATCH | `/api/subscriptions/:id/cancel` | EDIT_SUBSCRIPTIONS | Cancel |
| PATCH | `/api/subscriptions/:id/pause` | EDIT_SUBSCRIPTIONS | Pause |
| GET | `/api/subscriptions/plans` | (any auth) | List subscription plans |

### Products `/api/products`
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/products` | (any auth) | List (filter `fandom_id`, `in_stock=true`) |
| GET | `/api/products/:id` | (any auth) | Product + inventory detail |
| POST | `/api/products` | MANAGE_PRODUCTS | Create product |
| PUT | `/api/products/:id` | MANAGE_PRODUCTS | Update product |

### Inventory `/api/inventory`
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/inventory` | VIEW_INVENTORY | Overview (filter `warehouse_id`, `low_stock=true`) |
| PATCH | `/api/inventory/:id` | EDIT_INVENTORY | Update quantities |
| GET | `/api/inventory/warehouses` | VIEW_INVENTORY | List warehouses |

### Orders `/api/orders`
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/orders` | VIEW_ORDERS | List (paginated, filter `status`) |
| GET | `/api/orders/:id` | VIEW_ORDERS | Detail with shipments & payments |
| PATCH | `/api/orders/:id/status` | EDIT_ORDERS | Update order status |

**Valid statuses:** `Pending`, `Packed`, `Shipped`, `Delivered`, `Failed`, `Cancelled`

### Shipments `/api/shipments`
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/shipments` | VIEW_ORDERS | List (filter `status`) |
| POST | `/api/shipments` | PROCESS_SHIPMENTS | Create shipment |
| PATCH | `/api/shipments/:id` | PROCESS_SHIPMENTS | Update shipment (auto-syncs order status) |

### Reports `/api/reports`
| Endpoint | Permission | Description |
|---|---|---|
| GET `/api/reports/dashboard` | VIEW_REPORTS | Leadership KPIs snapshot |
| GET `/api/reports/subscribers/active` | VIEW_REPORTS | Active subs by plan |
| GET `/api/reports/subscribers/growth` | VIEW_REPORTS | Monthly cumulative growth |
| GET `/api/reports/subscribers/churn` | VIEW_REPORTS | Monthly churn rate |
| GET `/api/reports/revenue/by-plan` | VIEW_REPORTS | Revenue per plan |
| GET `/api/reports/revenue/monthly` | VIEW_REPORTS | Monthly revenue summary |
| GET `/api/reports/revenue/by-region` | VIEW_REPORTS | Revenue by region |
| GET `/api/reports/fulfillment/by-release` | VIEW_REPORTS | Orders per box release |
| GET `/api/reports/fulfillment/shipment-performance` | VIEW_REPORTS | Avg delivery days |
| GET `/api/reports/inventory/overview` | VIEW_INVENTORY | Full inventory status |
| GET `/api/reports/inventory/damaged` | VIEW_INVENTORY | Damaged goods report |
| GET `/api/reports/themes/popularity` | VIEW_REPORTS | Fandom popularity |
| GET `/api/reports/audit-log` | VIEW_AUDIT_LOG | Audit trail (`?limit=50`) |

---

## Database

- **Engine:** SQLite3 (via Python stdlib — no native build required)
- **File:** `src/db/nerdblock.db` (auto-created on first run)
- **Tables:** 27 tables matching the NerdBlock Data Dictionary & 3NF schema
- **Seed data:** 15 customers, 15+ products, 16 subscriptions, 31 orders, 200+ rows total

## Project Structure

```
nerdblock-backend/
├── app.py                        # Entry point, Flask app, blueprint registration
├── src/
│   ├── db/
│   │   ├── init_db.py            # Schema creation + seed data
│   │   └── nerdblock.db          # SQLite database (auto-generated)
│   ├── middleware/
│   │   └── auth.py               # JWT generation, require_auth, require_permission
│   └── routes/
│       ├── auth.py               # /api/auth
│       ├── customers.py          # /api/customers
│       ├── subscriptions.py      # /api/subscriptions
│       ├── products.py           # /api/products + /api/inventory
│       ├── orders.py             # /api/orders + /api/shipments
│       └── reports.py            # /api/reports/*
└── README.md
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | `nerdblock-dev-secret-change-in-prod` | JWT signing key |
| `PORT` | `5000` | Server port |
| `FLASK_DEBUG` | `1` | Debug mode (`0` for production) |
