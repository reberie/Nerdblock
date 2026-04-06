import { Router, Response } from "express";
import * as admin from "firebase-admin";
import { db } from "../index";
import { requireAuth, requirePermission, AuthRequest } from "../middleware/auth";

export const productsRouter = Router();

/** GET /api/products — public */
productsRouter.get("/", async (req, res: Response): Promise<void> => {
  try {
    let query: admin.firestore.Query = db.collection("products").orderBy("product_name");
    if (req.query.fandom_id) query = query.where("product_fandom_id", "==", req.query.fandom_id);
    if (req.query.in_stock === "true") query = query.where("product_stock", ">", 0);

    const snap = await query.get();
    res.json(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

/** GET /api/products/:id — public */
productsRouter.get("/:id", async (req, res: Response): Promise<void> => {
  try {
    const doc = await db.collection("products").doc(req.params.id).get();
    if (!doc.exists) { res.status(404).json({ error: "Product not found" }); return; }

    const inventory = await db.collection("inventory")
      .where("product_id", "==", req.params.id).get();

    res.json({
      id: doc.id,
      ...doc.data(),
      inventory: inventory.docs.map((d) => ({ id: d.id, ...d.data() })),
    });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

/** POST /api/products */
productsRouter.post(
  "/",
  requireAuth,
  requirePermission("MANAGE_PRODUCTS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const { product_name, product_price, product_cost, product_fandom_id } = req.body;
      if (!product_name || product_price == null || product_cost == null || !product_fandom_id) {
        res.status(400).json({ error: "Missing required fields" }); return;
      }

      const ref = await db.collection("products").add({
        product_name,
        product_desc:      req.body.product_desc ?? null,
        product_price:     Number(product_price),
        product_cost:      Number(product_cost),
        product_fandom_id,
        product_stock:     req.body.product_stock ?? 0,
        created_at:        admin.firestore.FieldValue.serverTimestamp(),
      });
      res.status(201).json({ message: "Product created", product_id: ref.id });
    } catch (err) {
      res.status(400).json({ error: String(err) });
    }
  }
);

/** PUT /api/products/:id */
productsRouter.put(
  "/:id",
  requireAuth,
  requirePermission("MANAGE_PRODUCTS"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const doc = await db.collection("products").doc(req.params.id).get();
      if (!doc.exists) { res.status(404).json({ error: "Product not found" }); return; }

      const allowed = ["product_name","product_desc","product_price","product_cost",
                       "product_fandom_id","product_stock"];
      const updates: Record<string, unknown> = {};
      for (const key of allowed) {
        if (req.body[key] !== undefined) updates[key] = req.body[key];
      }

      updates.updated_at = admin.firestore.FieldValue.serverTimestamp();
      await db.collection("products").doc(req.params.id).update(updates);
      res.json({ message: "Product updated" });
    } catch (err) {
      res.status(400).json({ error: String(err) });
    }
  }
);
