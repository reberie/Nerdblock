import { Router, Response } from "express";
import * as admin from "firebase-admin";
import { db } from "../index";
import { requireAuth, requirePermission, AuthRequest, writeAudit } from "../middleware/auth";

export const customersRouter = Router();

/** GET /api/customers — paginated list with optional search */
customersRouter.get(
  "/",
  requireAuth,
  requirePermission("VIEW_CUSTOMERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const pageSize = Math.min(100, parseInt(req.query.per_page as string) || 20);
      const search   = (req.query.search as string || "").toLowerCase();

      let query: admin.firestore.Query = db.collection("customers").orderBy("last_name");

      // Firestore doesn't support full-text search natively — use startAt/endAt for prefix
      if (search) {
        query = query
          .where("search_index", "array-contains", search);
      }

      // Cursor-based pagination
      const afterDoc = req.query.after as string | undefined;
      if (afterDoc) {
        const snap = await db.collection("customers").doc(afterDoc).get();
        if (snap.exists) query = query.startAfter(snap);
      }

      const snapshot = await query.limit(pageSize).get();
      const customers = snapshot.docs.map((d) => ({ id: d.id, ...d.data() }));

      res.json({
        data: customers,
        next_cursor: snapshot.docs.length === pageSize
          ? snapshot.docs[snapshot.docs.length - 1].id
          : null,
      });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/customers/:id — full profile */
customersRouter.get(
  "/:id",
  requireAuth,
  requirePermission("VIEW_CUSTOMERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("customers").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Customer not found" }); return; }

      const [addresses, billing, themes, ratings, subs] = await Promise.all([
        db.collection("customers").doc(req.params.id).collection("addresses").get(),
        db.collection("customers").doc(req.params.id).collection("billing_addresses").get(),
        db.collection("customer_themes").where("customer_id", "==", req.params.id).get(),
        db.collection("customer_content_ratings").where("customer_id", "==", req.params.id).get(),
        db.collection("subscriptions").where("customer_id", "==", req.params.id)
          .orderBy("start_date", "desc").limit(20).get(),
      ]);

      res.json({
        id: doc.id,
        ...doc.data(),
        addresses:                  addresses.docs.map((d) => ({ id: d.id, ...d.data() })),
        billing_addresses:          billing.docs.map((d) => ({ id: d.id, ...d.data() })),
        theme_preferences:          themes.docs.map((d) => d.data()),
        content_rating_preferences: ratings.docs.map((d) => d.data()),
        subscriptions:              subs.docs.map((d) => ({ id: d.id, ...d.data() })),
      });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** POST /api/customers — create */
customersRouter.post(
  "/",
  requireAuth,
  requirePermission("EDIT_CUSTOMERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const { first_name, last_name, email, birth_date, accnt_theme_id } = req.body;
      if (!first_name || !last_name || !email || !birth_date || !accnt_theme_id) {
        res.status(400).json({ error: "Missing required fields: first_name, last_name, email, birth_date, accnt_theme_id" });
        return;
      }

      // Build search_index for prefix search
      const search_index = [
        ...first_name.toLowerCase().split(""),
        ...last_name.toLowerCase().split(""),
        email.toLowerCase(),
        `${first_name} ${last_name}`.toLowerCase(),
      ].filter((v, i, a) => a.indexOf(v) === i);

      const ref = await db.collection("customers").add({
        first_name,
        last_name,
        email,
        phone_number:    req.body.phone_number    ?? null,
        birth_date,
        age_restricted:  req.body.age_restricted  ?? false,
        accnt_theme_id,
        clothing_size:   req.body.clothing_size   ?? null,
        age_rating_pref: req.body.age_rating_pref ?? "ALL",
        search_index,
        created_at: admin.firestore.FieldValue.serverTimestamp(),
      });

      res.status(201).json({ message: "Customer created", customer_id: ref.id });
    } catch (err) {
      res.status(400).json({ error: String(err) });
    }
  }
);

/** PUT /api/customers/:id — update */
customersRouter.put(
  "/:id",
  requireAuth,
  requirePermission("EDIT_CUSTOMERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("customers").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Customer not found" }); return; }

      const allowed = ["first_name", "last_name", "email", "phone_number",
                       "clothing_size", "age_rating_pref", "accnt_theme_id", "age_restricted"];
      const updates: Record<string, unknown> = {};
      for (const key of allowed) {
        if (req.body[key] !== undefined) updates[key] = req.body[key];
      }

      if (Object.keys(updates).length === 0) {
        res.status(400).json({ error: "No valid fields to update" }); return;
      }

      updates.updated_at = admin.firestore.FieldValue.serverTimestamp();
      await db.collection("customers").doc(req.params.id).update(updates);
      await writeAudit(req.user!.uid, "customer", req.params.id, "UPDATE", "", JSON.stringify(updates));

      res.json({ message: "Customer updated" });
    } catch (err) {
      res.status(400).json({ error: String(err) });
    }
  }
);

/** DELETE /api/customers/:id */
customersRouter.delete(
  "/:id",
  requireAuth,
  requirePermission("DELETE_CUSTOMERS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const hasSubs = await db.collection("subscriptions")
        .where("customer_id", "==", req.params.id).limit(1).get();
      if (!hasSubs.empty) {
        res.status(409).json({ error: "Cannot delete customer with active subscriptions" }); return;
      }

      await db.collection("customers").doc(req.params.id).delete();
      res.json({ message: "Customer deleted" });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);
