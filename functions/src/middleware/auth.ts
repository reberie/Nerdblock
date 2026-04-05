import { Request, Response, NextFunction } from "express";
import { auth, db } from "../index";

export interface AuthRequest extends Request {
  user?: {
    uid: string;
    email?: string;
    roles: string[];
    permissions: string[];
  };
}

/** Verifies the Firebase ID token from the Authorization header */
export async function requireAuth(
  req: AuthRequest,
  res: Response,
  next: NextFunction
): Promise<void> {
  const header = req.headers.authorization || "";
  if (!header.startsWith("Bearer ")) {
    res.status(401).json({ error: "Missing or malformed Authorization header" });
    return;
  }
  const idToken = header.slice(7);
  try {
    const decoded = await auth.verifyIdToken(idToken);
    const userDoc = await db.collection("system_users").doc(decoded.uid).get();
    const userData = userDoc.data() || {};
    const roles: string[] = userData.roles || [];

    // Collect all permissions for the user's roles
    const permsSet = new Set<string>();
    for (const role of roles) {
      const roleDoc = await db.collection("roles").where("role_name", "==", role).limit(1).get();
      if (!roleDoc.empty) {
        const rolePerms: string[] = roleDoc.docs[0].data().permissions || [];
        rolePerms.forEach((p) => permsSet.add(p));
      }
    }

    req.user = {
      uid: decoded.uid,
      email: decoded.email,
      roles,
      permissions: Array.from(permsSet),
    };
    next();
  } catch {
    res.status(401).json({ error: "Invalid or expired token" });
  }
}

/** Checks that req.user has the specified permission */
export function requirePermission(permissionCode: string) {
  return (req: AuthRequest, res: Response, next: NextFunction): void => {
    if (!req.user?.permissions.includes(permissionCode)) {
      res.status(403).json({ error: `Permission denied: ${permissionCode} required` });
      return;
    }
    next();
  };
}

/** Write an audit log entry from a Cloud Function handler */
export async function writeAudit(
  uid: string,
  entityName: string,
  entityId: string,
  actionType: string,
  oldValue: string,
  newValue: string
): Promise<void> {
  const { db: firestoreDb } = await import("../index");
  const admin = await import("firebase-admin");
  await firestoreDb.collection("audit_logs").add({
    user_id:     uid,
    entity_name: entityName,
    entity_id:   entityId,
    action_type: actionType,
    old_value:   oldValue,
    new_value:   newValue,
    created_at:  admin.firestore.FieldValue.serverTimestamp(),
  });
}
