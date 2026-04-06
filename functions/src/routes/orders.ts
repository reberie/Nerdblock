import { Router, Response } from "express";
import * as admin from "firebase-admin";
import { db } from "../index";
import { requireAuth, requirePermission, AuthRequest, writeAudit } from "../middleware/auth";

export const ordersRouter   = Router();
export const shipmentsRouter = Router();

const VALID_ORDER_STATUSES    = new Set(["Pending","Packed","Shipped","Delivered","Failed","Cancelled"]);
const VALID_SHIPMENT_STATUSES = new Set(["Pending","Shipped","In Transit","Delivered","Failed","Returned"]);

// ── ORDERS ───────────────────────────────────────────────────────────────────

ordersRouter.get(
  "/",
  requireAuth,
  requirePermission("VIEW_ORDERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const pageSize = Math.min(100, parseInt(req.query.per_page as string) || 20);
      const status   = req.query.status as string | undefined;

      let query: admin.firestore.Query = db.collection("orders").orderBy("created_at", "desc");
      if (status && VALID_ORDER_STATUSES.has(status)) {
        query = query.where("order_status", "==", status);
      }

      const afterDoc = req.query.after as string | undefined;
      if (afterDoc) {
        const snap = await db.collection("orders").doc(afterDoc).get();
        if (snap.exists) query = query.startAfter(snap);
      }

      const snapshot = await query.limit(pageSize).get();
      res.json({
        data: snapshot.docs.map((d) => ({ id: d.id, ...d.data() })),
        next_cursor: snapshot.docs.length === pageSize
          ? snapshot.docs[snapshot.docs.length - 1].id : null,
      });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

ordersRouter.get(
  "/:id",
  requireAuth,
  requirePermission("VIEW_ORDERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("orders").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Order not found" }); return; }

      const [shipments, transactions] = await Promise.all([
        db.collection("shipments").where("order_id", "==", req.params.id)
          .orderBy("shipped_date", "desc").get(),
        db.collection("payment_transactions").where("order_id", "==", req.params.id).get(),
      ]);

      res.json({
        id: doc.id,
        ...doc.data(),
        shipments:    shipments.docs.map((d) => ({ id: d.id, ...d.data() })),
        transactions: transactions.docs.map((d) => ({ id: d.id, ...d.data() })),
      });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

ordersRouter.patch(
  "/:id/status",
  requireAuth,
  requirePermission("EDIT_ORDERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const { order_status } = req.body;
      if (!VALID_ORDER_STATUSES.has(order_status)) {
        res.status(400).json({ error: `Invalid status. Valid: ${[...VALID_ORDER_STATUSES].join(", ")}` }); return;
      }

      const doc = await db.collection("orders").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Order not found" }); return; }

      const old_status = doc.data()!.order_status;
      await doc.ref.update({
        order_status,
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      });
      await writeAudit(
        req.user!.uid, "order", req.params.id,
        "UPDATE", `status: ${old_status}`, `status: ${order_status}`
      );

      res.json({ message: `Order status updated to ${order_status}` });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

// ── CREATE ORDER ─────────────────────────────────────────────────────────────
ordersRouter.post(
  "/",
  requireAuth,
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const { subscription_id, release_id, customer_id } = req.body;
      if (!subscription_id || !customer_id) {
        res.status(400).json({ error: "subscription_id and customer_id required" });
        return;
      }
      const ref = await db.collection("orders").add({
        subscription_id,
        release_id:  release_id ?? null,
        customer_id,
        order_status: req.body.order_status ?? "Pending",
        created_at:  admin.firestore.FieldValue.serverTimestamp(),
      });
      res.status(201).json({ message: "Order created", order_id: ref.id });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

// ── SHIPMENTS ────────────────────────────────────────────────────────────────

shipmentsRouter.get(
  "/",
  requireAuth,
  requirePermission("VIEW_ORDERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      let query: admin.firestore.Query = db.collection("shipments").orderBy("shipped_date", "desc");
      const status = req.query.status as string | undefined;
      if (status) query = query.where("shipment_status", "==", status);

      const snap = await query.limit(100).get();
      res.json(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

shipmentsRouter.post(
  "/",
  requireAuth,
  requirePermission("PROCESS_SHIPMENTS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      if (!req.body.order_id) { res.status(400).json({ error: "order_id is required" }); return; }

      const orderDoc = await db.collection("orders").doc(req.body.order_id).get();
      if (!orderDoc.exists) { res.status(404).json({ error: "Order not found" }); return; }

      const ref = await db.collection("shipments").add({
        order_id:        req.body.order_id,
        customer_id:     orderDoc.data()!.customer_id,
        shipment_status: req.body.shipment_status  ?? "Pending",
        tracking_number: req.body.tracking_number  ?? null,
        shipped_date:    req.body.shipped_date      ?? null,
        delivered_date:  req.body.delivered_date    ?? null,
        created_at:      admin.firestore.FieldValue.serverTimestamp(),
      });

      if (req.body.shipped_date) {
        await orderDoc.ref.update({ order_status: "Shipped", updated_at: admin.firestore.FieldValue.serverTimestamp() });
      }

      res.status(201).json({ message: "Shipment created", shipment_id: ref.id });
    } catch (err) {
      res.status(400).json({ error: String(err) });
    }
  }
);

shipmentsRouter.patch(
  "/:id",
  requireAuth,
  requirePermission("PROCESS_SHIPMENTS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("shipments").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Shipment not found" }); return; }

      const { shipment_status } = req.body;
      if (shipment_status && !VALID_SHIPMENT_STATUSES.has(shipment_status)) {
        res.status(400).json({ error: "Invalid shipment_status" }); return;
      }

      const allowed = ["shipment_status","tracking_number","shipped_date","delivered_date"];
      const updates: Record<string, unknown> = {};
      for (const key of allowed) {
        if (req.body[key] !== undefined) updates[key] = req.body[key];
      }
      updates.updated_at = admin.firestore.FieldValue.serverTimestamp();
      await doc.ref.update(updates);

      // Sync order status on delivery
      if (shipment_status === "Delivered" && doc.data()!.order_id) {
        await db.collection("orders").doc(doc.data()!.order_id).update({
          order_status: "Delivered",
          updated_at: admin.firestore.FieldValue.serverTimestamp(),
        });
      }

      res.json({ message: "Shipment updated" });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);
