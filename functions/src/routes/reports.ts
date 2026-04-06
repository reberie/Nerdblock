import { Router, Response } from "express";
import { db } from "../index";
import { requireAuth, requirePermission, AuthRequest } from "../middleware/auth";

export const reportsRouter = Router();

// ── helpers ──────────────────────────────────────────────────────────────────
const monthOf = (iso: string) => iso?.slice(0, 7) ?? "unknown";

/** GET /api/reports/dashboard */
reportsRouter.get(
  "/dashboard",
  requireAuth,
  requirePermission("VIEW_REPORTS"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      const today = new Date().toISOString().split("T")[0];
      const thisMonth = today.slice(0, 7);

      const [activeSubs, pendingOrders, txSnap, failSnap, regionsSnap] = await Promise.all([
        db.collection("subscriptions")
          .where("renewal_date", ">=", today).where("auto_renew", "==", true).get(),
        db.collection("orders")
          .where("order_status", "in", ["Pending", "Packed"]).get(),
        db.collection("payment_transactions")
          .where("payment_status", "==", "Completed")
          .where("created_at", ">=", `${thisMonth}-01`).get(),
        db.collection("payment_transactions")
          .where("payment_status", "==", "Failed")
          .where("created_at", ">=", `${thisMonth}-01`).get(),
        db.collection("customers").get(),
      ]);

      const currentRevenue = txSnap.docs.reduce((s, d) => s + (d.data().amount ?? 0), 0);
      const uniqueCustomers = new Set(activeSubs.docs.map((d) => d.data().customer_id)).size;

      // regions = distinct provinces from customer addresses
      const provinces = new Set<string>();
      regionsSnap.docs.forEach((d) => {
        const p = d.data().province;
        if (p) provinces.add(p);
      });

      res.json({
        total_active_subscriptions:  activeSubs.size,
        unique_active_customers:     uniqueCustomers,
        current_month_revenue:       Math.round(currentRevenue * 100) / 100,
        current_month_failed_payments: failSnap.size,
        orders_awaiting_shipment:    pendingOrders.size,
        regions_served:              provinces.size,
      });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/subscribers/active */
reportsRouter.get(
  "/subscribers/active",
  requireAuth,
  requirePermission("VIEW_REPORTS"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      const today = new Date().toISOString().split("T")[0];
      const snap  = await db.collection("subscriptions")
        .where("renewal_date", ">=", today).where("auto_renew", "==", true).get();

      // Group by plan_id
      const planMap: Record<string, { subs: number; customers: Set<string> }> = {};
      const planIds = new Set<string>();
      snap.docs.forEach((d) => {
        const { plan_id, customer_id } = d.data();
        planIds.add(plan_id);
        if (!planMap[plan_id]) planMap[plan_id] = { subs: 0, customers: new Set() };
        planMap[plan_id].subs++;
        planMap[plan_id].customers.add(customer_id);
      });

      // Fetch plan names
      const planDocs = await Promise.all([...planIds].map((id) =>
        db.collection("subscription_plans").doc(id).get()
      ));
      const planNames: Record<string, string> = {};
      planDocs.forEach((d) => { if (d.exists) planNames[d.id] = d.data()!.plan_name; });

      res.json(Object.entries(planMap).map(([plan_id, v]) => ({
        plan_name:            planNames[plan_id] ?? plan_id,
        active_subscriptions: v.subs,
        unique_customers:     v.customers.size,
      })));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/subscribers/growth */
reportsRouter.get(
  "/subscribers/growth",
  requireAuth,
  requirePermission("VIEW_REPORTS"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      const snap = await db.collection("subscriptions").orderBy("start_date").get();
      const monthly: Record<string, number> = {};
      snap.docs.forEach((d) => {
        const m = monthOf(d.data().start_date);
        monthly[m] = (monthly[m] ?? 0) + 1;
      });

      let cumulative = 0;
      res.json(Object.entries(monthly).sort().map(([month, count]) => {
        cumulative += count;
        return { signup_month: month, new_subscriptions: count, cumulative_subscriptions: cumulative };
      }));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/subscribers/churn */
reportsRouter.get(
  "/subscribers/churn",
  requireAuth,
  requirePermission("VIEW_REPORTS"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      // Cancellation events (subcollections)
      const subSnap   = await db.collection("subscriptions").get();
      const cancelMap: Record<string, number> = {};
      const activeMap: Record<string, Set<string>> = {};

      // Active by month from orders
      const orderSnap = await db.collection("orders").get();
      orderSnap.docs.forEach((d) => {
        const m = monthOf(d.data().created_at);
        if (!activeMap[m]) activeMap[m] = new Set();
        activeMap[m].add(d.data().subscription_id);
      });

      // Get cancellations from events subcollections
      await Promise.all(subSnap.docs.map(async (subDoc) => {
        const events = await subDoc.ref.collection("events")
          .where("event_type", "==", "Cancelled").get();
        events.docs.forEach((e) => {
          const m = monthOf(e.data().event_date);
          cancelMap[m] = (cancelMap[m] ?? 0) + 1;
        });
      }));

      res.json(
        Object.entries(activeMap)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([month, subs]) => ({
            active_month:  month,
            active_subs:   subs.size,
            cancellations: cancelMap[month] ?? 0,
            churn_rate_pct: subs.size > 0
              ? Math.round(((cancelMap[month] ?? 0) / subs.size) * 10000) / 100
              : 0,
          }))
      );
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/revenue/by-plan */
reportsRouter.get(
  "/revenue/by-plan",
  requireAuth,
  requirePermission("VIEW_REPORTS"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      const snap = await db.collection("payment_transactions")
        .where("payment_status", "==", "Completed").get();

      // Need subscription→plan mapping
      const subIds = [...new Set(snap.docs.map((d) => d.data().subscription_id))];
      const subDocs = await Promise.all(subIds.map((id) =>
        db.collection("subscriptions").doc(id).get()
      ));
      const subPlan: Record<string, string> = {};
      subDocs.forEach((d) => { if (d.exists) subPlan[d.id] = d.data()!.plan_id; });

      const planIds = [...new Set(Object.values(subPlan))];
      const planDocs = await Promise.all(planIds.map((id) =>
        db.collection("subscription_plans").doc(id).get()
      ));
      const planName: Record<string, string> = {};
      planDocs.forEach((d) => { if (d.exists) planName[d.id] = d.data()!.plan_name; });

      const grouped: Record<string, { txns: number; gross: number; tax: number; discount: number }> = {};
      snap.docs.forEach((d) => {
        const data = d.data();
        const planId = subPlan[data.subscription_id] ?? "unknown";
        const name   = planName[planId] ?? planId;
        if (!grouped[name]) grouped[name] = { txns: 0, gross: 0, tax: 0, discount: 0 };
        grouped[name].txns++;
        grouped[name].gross    += data.amount    ?? 0;
        grouped[name].tax      += data.tax_amount ?? 0;
        grouped[name].discount += data.discount_amount ?? 0;
      });

      res.json(Object.entries(grouped).map(([plan_name, v]) => ({
        plan_name,
        total_transactions: v.txns,
        gross_revenue: Math.round(v.gross    * 100) / 100,
        total_tax:     Math.round(v.tax      * 100) / 100,
        total_discounts: Math.round(v.discount * 100) / 100,
        net_revenue: Math.round((v.gross - v.discount) * 100) / 100,
      })));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/revenue/monthly */
reportsRouter.get(
  "/revenue/monthly",
  requireAuth,
  requirePermission("VIEW_REPORTS"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      const snap = await db.collection("payment_transactions").get();
      const monthly: Record<string, {
        completed: number; refunded: number; failed: number; tax: number; failed_count: number;
      }> = {};

      snap.docs.forEach((d) => {
        const { created_at, payment_status, amount, tax_amount } = d.data();
        const m = monthOf(created_at);
        if (!monthly[m]) monthly[m] = { completed:0, refunded:0, failed:0, tax:0, failed_count:0 };
        if (payment_status === "Completed") { monthly[m].completed += amount ?? 0; monthly[m].tax += tax_amount ?? 0; }
        if (payment_status === "Refunded")  { monthly[m].refunded  += amount ?? 0; }
        if (payment_status === "Failed")    { monthly[m].failed    += amount ?? 0; monthly[m].failed_count++; }
      });

      res.json(Object.entries(monthly).sort().map(([month, v]) => ({
        revenue_month:     month,
        completed_revenue: Math.round(v.completed * 100) / 100,
        refunded_amount:   Math.round(v.refunded  * 100) / 100,
        failed_amount:     Math.round(v.failed    * 100) / 100,
        tax_collected:     Math.round(v.tax       * 100) / 100,
        failed_count:      v.failed_count,
      })));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/themes/popularity */
reportsRouter.get(
  "/themes/popularity",
  requireAuth,
  requirePermission("VIEW_REPORTS"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      const [themes, ctSnap, orderSnap, releaseSnap] = await Promise.all([
        db.collection("themes").get(),
        db.collection("customer_themes").get(),
        db.collection("orders").get(),
        db.collection("box_releases").get(),
      ]);

      const releaseTheme: Record<string, string> = {};
      releaseSnap.docs.forEach((d) => { releaseTheme[d.id] = d.data().theme_id; });

      const ordersByTheme: Record<string, number> = {};
      orderSnap.docs.forEach((d) => {
        const themeId = releaseTheme[d.data().release_id];
        if (themeId) ordersByTheme[themeId] = (ordersByTheme[themeId] ?? 0) + 1;
      });

      const custByTheme: Record<string, number> = {};
      ctSnap.docs.forEach((d) => {
        const { theme_id } = d.data();
        custByTheme[theme_id] = (custByTheme[theme_id] ?? 0) + 1;
      });

      res.json(themes.docs.map((d) => ({
        theme_name:          d.data().theme_name,
        customers_interested: custByTheme[d.id]   ?? 0,
        total_orders_placed:  ordersByTheme[d.id] ?? 0,
      })).sort((a, b) => b.customers_interested - a.customers_interested));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/inventory/overview */
reportsRouter.get(
  "/inventory/overview",
  requireAuth,
  requirePermission("VIEW_INVENTORY"),
  async (_req: AuthRequest, res: Response): Promise<void> => {
    try {
      const [invSnap, prodSnap, whSnap] = await Promise.all([
        db.collection("inventory").get(),
        db.collection("products").get(),
        db.collection("warehouses").get(),
      ]);
      const products:   Record<string, Record<string, unknown>> = {};
      const warehouses: Record<string, string> = {};
      prodSnap.docs.forEach((d) => { products[d.id]   = d.data(); });
      whSnap.docs.forEach((d)   => { warehouses[d.id] = d.data().warehouse_name; });

      res.json(invSnap.docs.map((d) => {
        const data = d.data();
        const net  = (data.quantity_availability ?? 0) - (data.quantity_reserved ?? 0);
        return {
          id: d.id,
          product_name:          products[data.product_id]?.product_name,
          product_price:         products[data.product_id]?.product_price,
          warehouse_name:        warehouses[data.warehouse_id],
          quantity_availability: data.quantity_availability,
          quantity_reserved:     data.quantity_reserved,
          quantity_damaged:      data.quantity_damaged,
          net_available: net,
          stock_status:  net <= 0 ? "Out of Stock" : net < 500 ? "Low Stock" : "In Stock",
        };
      }));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);

/** GET /api/reports/audit-log */
reportsRouter.get(
  "/audit-log",
  requireAuth,
  requirePermission("VIEW_AUDIT_LOG"),
  async (req: AuthRequest, res: Response): Promise<void> => {
    try {
      const limit = Math.min(200, parseInt(req.query.limit as string) || 50);
      const snap  = await db.collection("audit_logs")
        .orderBy("created_at", "desc").limit(limit).get();
      res.json(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  }
);
