import * as functions from "firebase-functions";
import * as admin from "firebase-admin";
import express from "express";
import cors from "cors";

import { authRouter }          from "./routes/auth";
import { customersRouter }     from "./routes/customers";
import { subscriptionsRouter } from "./routes/subscriptions";
import { productsRouter }      from "./routes/products";
import { inventoryRouter }     from "./routes/inventory";
import { ordersRouter }        from "./routes/orders";
import { shipmentsRouter }     from "./routes/shipments";
import { reportsRouter }       from "./routes/reports";

// ── Firebase Admin init ──────────────────────────────────────────────────────
admin.initializeApp();
export const db   = admin.firestore();
export const auth = admin.auth();

// ── Express app ──────────────────────────────────────────────────────────────
const app = express();
app.use(cors({ origin: true }));
app.use(express.json());

// ── Routes ───────────────────────────────────────────────────────────────────
app.use("/auth",          authRouter);
app.use("/customers",     customersRouter);
app.use("/subscriptions", subscriptionsRouter);
app.use("/products",      productsRouter);
app.use("/inventory",     inventoryRouter);
app.use("/orders",        ordersRouter);
app.use("/shipments",     shipmentsRouter);
app.use("/reports",       reportsRouter);

// ── Health check ─────────────────────────────────────────────────────────────
app.get("/", (_req, res) => {
  res.json({
    name: "NerdBlock Store API",
    version: "2.0.0",
    platform: "Firebase Cloud Functions + Firestore",
    endpoints: {
      auth:          "/api/auth/login | /api/auth/me",
      customers:     "/api/customers",
      subscriptions: "/api/subscriptions | /api/subscriptions/plans",
      products:      "/api/products",
      inventory:     "/api/inventory",
      orders:        "/api/orders",
      shipments:     "/api/shipments",
      reports:       "/api/reports/dashboard | ...13 report endpoints",
    },
  });
});

// 404
app.use((_req, res) => res.status(404).json({ error: "Endpoint not found" }));

// ── Export as Cloud Function ─────────────────────────────────────────────────
export const api = functions
  .runWith({ memory: "512MB", timeoutSeconds: 60 })
  .https.onRequest(app);

// ── Firestore triggers ───────────────────────────────────────────────────────

/** Auto-log subscription status changes */
export const onSubscriptionUpdate = functions.firestore
  .document("subscriptions/{subId}")
  .onUpdate(async (change, context) => {
    const before = change.before.data();
    const after  = change.after.data();
    if (before.auto_renew !== after.auto_renew || before.renewal_date !== after.renewal_date) {
      await db.collection("audit_logs").add({
        entity_name: "subscription",
        entity_id:   context.params.subId,
        action_type: "UPDATE",
        old_value:   JSON.stringify({ auto_renew: before.auto_renew, renewal_date: before.renewal_date }),
        new_value:   JSON.stringify({ auto_renew: after.auto_renew,  renewal_date: after.renewal_date }),
        created_at:  admin.firestore.FieldValue.serverTimestamp(),
      });
    }
  });

/** Auto-log order status changes */
export const onOrderUpdate = functions.firestore
  .document("orders/{orderId}")
  .onUpdate(async (change, context) => {
    const before = change.before.data();
    const after  = change.after.data();
    if (before.order_status !== after.order_status) {
      await db.collection("audit_logs").add({
        entity_name: "order",
        entity_id:   context.params.orderId,
        action_type: "UPDATE",
        old_value:   `status: ${before.order_status}`,
        new_value:   `status: ${after.order_status}`,
        created_at:  admin.firestore.FieldValue.serverTimestamp(),
      });
    }
  });

/** Sync shipment → order status automatically */
export const onShipmentUpdate = functions.firestore
  .document("shipments/{shipId}")
  .onUpdate(async (change) => {
    const after = change.after.data();
    if (!after.order_id) return;
    const statusMap: Record<string, string> = {
      Shipped:    "Shipped",
      "In Transit": "Shipped",
      Delivered:  "Delivered",
    };
    const newOrderStatus = statusMap[after.shipment_status];
    if (newOrderStatus) {
      await db.collection("orders").doc(after.order_id).update({
        order_status: newOrderStatus,
        updated_at:   admin.firestore.FieldValue.serverTimestamp(),
      });
    }
  });
