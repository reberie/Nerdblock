# NerdBlock Store — Firebase Edition

Full-stack subscription box store running on **Firebase** (Auth + Firestore + Cloud Functions + Hosting).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  public/index.html                                          │
│  Firebase Hosting  ─────────→  Firebase Auth (sign-in)     │
│  Vanilla JS SPA    ─────────→  Firestore (products/plans)   │
│                    ─────────→  Cloud Functions API (orders) │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  Firebase Auth                  Cloud Functions
  (ID tokens)          Express app → Firestore (all writes)
                                 Firestore Triggers (audit log,
                                   order sync, shipment sync)
```

---

## Quick Start (Local Emulators)

### Prerequisites
```bash
npm install -g firebase-tools
node --version   # needs v18+
```

### 1 — Create your Firebase project
1. Go to [console.firebase.google.com](https://console.firebase.google.com)
2. Click **Add project** → name it `nerdblock` (or anything you like)
3. Enable **Authentication** → Sign-in method → **Email/Password**
4. Enable **Firestore** → Start in **production mode**
5. Enable **Hosting**

### 2 — Wire in your config
Open `public/index.html` and replace the placeholder config block (~line 540):

```js
const firebaseConfig = {
  apiKey:            "YOUR_API_KEY",        // ← from Firebase Console
  authDomain:        "YOUR_PROJECT.firebaseapp.com",
  projectId:         "YOUR_PROJECT",
  storageBucket:     "YOUR_PROJECT.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId:             "YOUR_APP_ID"
};
```

Also replace `YOUR_PROJECT_ID` in `api.http` and the `API_BASE` line in `index.html`.

Get these values from: **Firebase Console → Project Settings → Your apps → SDK setup and configuration**

### 3 — Install dependencies
```bash
cd functions
npm install
npm run build      # compiles TypeScript → lib/
cd ..
```

### 4 — Log in and initialize
```bash
firebase login
firebase use --add   # select your project
```

### 5 — Start emulators
```bash
firebase emulators:start
```

Opens:
| Service | URL |
|---|---|
| **Hosting** (frontend) | http://localhost:5000 |
| **Functions** (API) | http://localhost:5001 |
| **Firestore** | http://localhost:8080 |
| **Auth** | http://localhost:9099 |
| **Emulator UI** | http://localhost:4000 |

### 6 — Seed the database
```bash
node seed.js
```

This populates: themes, content ratings, warehouses, subscription plans, products, inventory, box releases.

### 7 — Create your first staff user
In the **Emulator UI** (http://localhost:4000):
1. Go to **Authentication** → Add user → enter email + password
2. Copy the generated UID
3. Go to **Firestore** → `system_users` collection → Add document with that UID:
```json
{
  "username": "alex.ceo",
  "roles": ["Administrator", "Leadership"],
  "is_active": true
}
```

---

## Deploy to Production

```bash
cd functions && npm run build && cd ..
firebase deploy
```

Or deploy individually:
```bash
firebase deploy --only hosting      # frontend only
firebase deploy --only functions    # API only
firebase deploy --only firestore    # rules + indexes only
```

---

## Project Structure

```
nerdblock-firebase/
├── public/
│   └── index.html              ← SPA frontend (Firebase SDK, auth, Firestore reads)
├── functions/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── index.ts            ← Express app entry + Firestore triggers
│       ├── middleware/
│       │   └── auth.ts         ← Firebase ID token verifier + permission checker
│       └── routes/
│           ├── auth.ts         ← GET /api/auth/me
│           ├── customers.ts    ← CRUD /api/customers
│           ├── subscriptions.ts← CRUD /api/subscriptions + cancel/pause
│           ├── products.ts     ← CRUD /api/products
│           ├── inventory.ts    ← /api/inventory + warehouses
│           ├── orders.ts       ← /api/orders + /api/shipments
│           └── reports.ts      ← 10 analytics endpoints
├── firestore.rules             ← Role-based security rules
├── firestore.indexes.json      ← Composite indexes
├── firebase.json               ← Hosting + Functions + Emulator config
├── seed.js                     ← One-time Firestore data seeder
├── api.http                    ← REST Client test file (VS Code)
└── .vscode/
    ├── settings.json
    ├── launch.json
    └── extensions.json
```

---

## API Endpoints

All endpoints are prefixed with `/api`. Protected endpoints require `Authorization: Bearer <Firebase ID Token>`.

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/auth/me` | ✅ | Current user profile + roles + permissions |

> **Login is client-side** — use `signInWithEmailAndPassword()` from the Firebase Auth SDK. The resulting ID token is passed as the Bearer token to all API calls.

### Customers
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/customers` | VIEW_CUSTOMERS | Paginated list (cursor-based) |
| GET | `/customers/:id` | VIEW_CUSTOMERS | Full profile with addresses, subs, prefs |
| POST | `/customers` | EDIT_CUSTOMERS | Create |
| PUT | `/customers/:id` | EDIT_CUSTOMERS | Update |
| DELETE | `/customers/:id` | DELETE_CUSTOMERS | Delete (blocks if has subscriptions) |

### Subscriptions
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/subscriptions/plans` | public | All subscription plans |
| GET | `/subscriptions` | VIEW_SUBSCRIPTIONS | List (filter: `status=active/cancelled`) |
| GET | `/subscriptions/:id` | VIEW_SUBSCRIPTIONS | Detail with events + orders |
| POST | `/subscriptions` | EDIT_SUBSCRIPTIONS | Create |
| PATCH | `/subscriptions/:id/cancel` | EDIT_SUBSCRIPTIONS | Cancel |
| PATCH | `/subscriptions/:id/pause` | EDIT_SUBSCRIPTIONS | Pause |

### Products & Inventory
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/products` | public | List (filter: `fandom_id`, `in_stock=true`) |
| GET | `/products/:id` | public | Detail + inventory per warehouse |
| POST | `/products` | MANAGE_PRODUCTS | Create |
| PUT | `/products/:id` | MANAGE_PRODUCTS | Update |
| GET | `/inventory` | VIEW_INVENTORY | Overview (filter: `warehouse_id`, `low_stock=true`) |
| GET | `/inventory/warehouses` | VIEW_INVENTORY | Warehouse list |
| PATCH | `/inventory/:id` | EDIT_INVENTORY | Update quantities |

### Orders & Shipments
| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/orders` | VIEW_ORDERS | Paginated (filter: `status`) |
| GET | `/orders/:id` | VIEW_ORDERS | Detail with shipments + transactions |
| POST | `/orders` | authenticated | Create order |
| PATCH | `/orders/:id/status` | EDIT_ORDERS | Update status |
| GET | `/shipments` | VIEW_ORDERS | List (filter: `status`) |
| POST | `/shipments` | PROCESS_SHIPMENTS | Create shipment (auto-syncs order) |
| PATCH | `/shipments/:id` | PROCESS_SHIPMENTS | Update (auto-syncs order on delivery) |

### Reports
| Endpoint | Permission |
|---|---|
| GET `/reports/dashboard` | VIEW_REPORTS |
| GET `/reports/subscribers/active` | VIEW_REPORTS |
| GET `/reports/subscribers/growth` | VIEW_REPORTS |
| GET `/reports/subscribers/churn` | VIEW_REPORTS |
| GET `/reports/revenue/by-plan` | VIEW_REPORTS |
| GET `/reports/revenue/monthly` | VIEW_REPORTS |
| GET `/reports/themes/popularity` | VIEW_REPORTS |
| GET `/reports/inventory/overview` | VIEW_INVENTORY |
| GET `/reports/audit-log?limit=50` | VIEW_AUDIT_LOG |

---

## Firestore Collections

| Collection | Description |
|---|---|
| `customers` | Customer profiles (+ `addresses/`, `billing_addresses/` subcollections) |
| `subscriptions` | Subscriptions (+ `events/` subcollection) |
| `subscription_plans` | Plan definitions (Monthly, 3-Month, 6-Month, 12-Month) |
| `products` | Box products |
| `inventory` | Stock levels per product per warehouse |
| `box_releases` | Monthly box releases per theme |
| `orders` | Customer orders |
| `shipments` | Shipment tracking |
| `payment_transactions` | Payment records |
| `themes` | Fandom/theme lookup |
| `content_ratings` | Age rating lookup |
| `warehouses` | Warehouse locations |
| `system_users` | Staff user profiles + roles |
| `roles` | Role → permissions mapping |
| `audit_logs` | Written only by Cloud Functions/triggers |

---

## Firestore Triggers (Automatic)

Three triggers run in the background with no API call needed:

- **`onSubscriptionUpdate`** — writes to `audit_logs` whenever a subscription's renewal or auto_renew changes
- **`onOrderUpdate`** — writes to `audit_logs` whenever an order status changes  
- **`onShipmentUpdate`** — automatically syncs the parent order's status when a shipment is marked Shipped or Delivered

---

## Staff Roles & Permissions

| Role | Permissions |
|---|---|
| Administrator | All 15 permissions |
| Customer Support | View/edit customers, view/edit subscriptions, view/edit orders |
| Warehouse Staff | View orders, view inventory, process shipments |
| Inventory Manager | View orders, view/edit inventory, manage products |
| Marketing | View customers, view subscriptions, view/export reports |
| Leadership | View/export reports, view audit log |
