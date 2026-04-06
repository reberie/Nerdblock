import { Router, Response } from "express";
import { requireAuth, AuthRequest } from "../middleware/auth";
import { db } from "../index";

export const authRouter = Router();

/**
 * GET /api/auth/me
 * Returns the current user's profile, roles, and permissions.
 * NOTE: Login/signup is handled client-side with the Firebase Auth SDK.
 *       The frontend calls firebase.auth().signInWithEmailAndPassword()
 *       and passes the resulting ID token in the Authorization header.
 */
authRouter.get("/me", requireAuth, async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userDoc = await db.collection("system_users").doc(req.user!.uid).get();
    if (!userDoc.exists) {
      res.status(404).json({ error: "User profile not found" });
      return;
    }
    const data = userDoc.data()!;
    res.json({
      uid:         req.user!.uid,
      email:       req.user!.email,
      username:    data.username,
      roles:       req.user!.roles,
      permissions: req.user!.permissions,
      is_active:   data.is_active ?? true,
      created_at:  data.created_at,
    });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});
