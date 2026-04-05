import { Router, Response } from "express";
import * as admin from "firebase-admin";
import { db } from "../index";
import { requireAuth, requirePermission, AuthRequest, writeAudit } from "../middleware/auth";

export const subscriptionsRouter = Router();

/** GET /api/subscriptions/plans — public */
subscriptionsRouter.get("/plans", async (_req, res: Response): Promise<void> => {
  const snap = await db.collection("subscription_plans").orderBy("price").get();
  res.json(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
});

/** GET /api/subscriptions */
subscriptionsRouter.get(
  "/",
  requireAuth,
  requirePermission("VIEW_SUBSCRIPTIONS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const pageSize = Math.min(100, parseInt(req.query.per_page as string) || 20);
      const status   = req.query.status as string | undefined;

      let query: admin.firestore.Query = db.collection("subscriptions").orderBy("start_date", "desc");

      if (status === "active") {
        query = query.where("renewal_date", ">=", new Date().toISOString().split("T")[0])
                     .where("auto_renew", "==", true);
      } else if (status === "cancelled") {
        query = query.where("auto_renew", "==", false);
      }

      const afterDoc = req.query.after as string | undefined;
      if (afterDoc) {
        const snap = await db.collection("subscriptions").doc(afterDoc).get();
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

/** GET /api/subscriptions/:id */
subscriptionsRouter.get(
  "/:id",
  requireAuth,
  requirePermission("VIEW_SUBSCRIPTIONS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("subscriptions").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Subscription not found" }); return; }

      const [events, orders] = await Promise.all([
        db.collection("subscriptions").doc(req.params.id)
          .collection("events").orderBy("event_date", "desc").limit(20).get(),
        db.collection("orders").where("subscription_id", "==", req.params.id)
          .orderBy("created_at", "desc").limit(20).get(),
      ]);

      res.json({
        id: doc.id,
        ...doc.data(),
        events: events.docs.map((d) => ({ id: d.id, ...d.data() })),
        orders: orders.docs.map((d) => ({ id: d.id, ...d.data() })),
      });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** POST /api/subscriptions — create */
subscriptionsRouter.post(
  "/",
  requireAuth,
  requirePermission("EDIT_SUBSCRIPTIONS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const { plan_id, product_id, customer_id, start_date } = req.body;
      if (!plan_id || !product_id || !customer_id || !start_date) {
        res.status(400).json({ error: "Missing required fields: plan_id, product_id, customer_id, start_date" });
        return;
      }

      const ref = await db.collection("subscriptions").add({
        plan_id, product_id, customer_id,
        renewal_date: req.body.renewal_date ?? null,
        start_date,
        auto_renew:  req.body.auto_renew ?? true,
        created_at:  admin.firestore.FieldValue.serverTimestamp(),
      });

      await db.collection("subscriptions").doc(ref.id)
        .collection("events").add({
          event_type: "Created",
          event_date: new Date().toISOString().split("T")[0],
        });

      res.status(201).json({ message: "Subscription created", subscription_id: ref.id });
    } catch (err) {
      res.status(400).json({ error: String(err) });
    }
  }
);

/** PATCH /api/subscriptions/:id/cancel */
subscriptionsRouter.patch(
  "/:id/cancel",
  requireAuth,
  requirePermission("EDIT_SUBSCRIPTIONS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("subscriptions").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Not found" }); return; }

      await doc.ref.update({
        auto_renew: false, renewal_date: null,
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      });
      await doc.ref.collection("events").add({
        event_type: "Cancelled",
        event_date: new Date().toISOString().split("T")[0],
      });
      await writeAudit(req.user!.uid, "subscription", req.params.id, "UPDATE", "status: Active", "status: Cancelled");

      res.json({ message: "Subscription cancelled" });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** PATCH /api/subscriptions/:id/pause */
subscriptionsRouter.patch(
  "/:id/pause",
  requireAuth,
  requirePermission("EDIT_SUBSCRIPTIONS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("subscriptions").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Not found" }); return; }

      await doc.ref.update({
        auto_renew: false,
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      });
      await doc.ref.collection("events").add({
        event_type: "Paused",
        event_date: new Date().toISOString().split("T")[0],
      });

      res.json({ message: "Subscription paused" });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);
