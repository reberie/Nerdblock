import { Router, Response } from "express";
import * as admin from "firebase-admin";
import { db } from "../index";
import { requireAuth, requirePermission, AuthRequest, writeAudit } from "../middleware/auth";

export const inventoryRouter = Router();

/** GET /api/inventory */
inventoryRouter.get(
  "/",
  requireAuth,
  requirePermission("VIEW_INVENTORY"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      let query: admin.firestore.Query = db.collection("inventory");
      if (req.query.warehouse_id) query = query.where("warehouse_id", "==", req.query.warehouse_id);

      const snap = await query.get();
      let rows = snap.docs.map((d) => {
        const data = d.data();
        const net_available = (data.quantity_availability ?? 0) - (data.quantity_reserved ?? 0);
        return {
          id: d.id,
          ...data,
          net_available,
          stock_status:
            net_available <= 0   ? "Out of Stock" :
            net_available < 500  ? "Low Stock"    : "In Stock",
        };
      });

      if (req.query.low_stock === "true") {
        rows = rows.filter((r) => r.stock_status !== "In Stock");
      }

      rows.sort((a, b) => a.stock_status.localeCompare(b.stock_status));
      res.json(rows);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/inventory/warehouses */
inventoryRouter.get(
  "/warehouses",
  requireAuth,
  requirePermission("VIEW_INVENTORY"),
  async (_req, res: Response): Promise<void> => {
    const snap = await db.collection("warehouses").orderBy("warehouse_name").get();
    res.json(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  }
);

/** PATCH /api/inventory/:id */
inventoryRouter.patch(
  "/:id",
  requireAuth,
  requirePermission("EDIT_INVENTORY"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("inventory").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Inventory record not found" }); return; }

      const allowed = ["quantity_availability", "quantity_reserved", "quantity_damaged"];
      const updates: Record<string, unknown> = {};
      const old = doc.data()!;

      for (const key of allowed) {
        if (req.body[key] !== undefined) updates[key] = req.body[key];
      }
      if (Object.keys(updates).length === 0) {
        res.status(400).json({ error: "No valid fields to update" }); return;
      }

      const oldValues: Record<string, unknown> = {};
      for (const key of Object.keys(updates)) oldValues[key] = old[key];

      updates.updated_at = admin.firestore.FieldValue.serverTimestamp();
      await doc.ref.update(updates);
      await writeAudit(
        req.user!.uid, "inventory", req.params.id,
        "UPDATE", JSON.stringify(oldValues), JSON.stringify(updates)
      );

      res.json({ message: "Inventory updated" });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);
