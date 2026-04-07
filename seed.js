/**
 * NerdBlock Firestore Seed Script
 * Run: node seed.js  (from project root, with emulators running)
 * Or against production: GOOGLE_APPLICATION_CREDENTIALS=./serviceAccount.json node seed.js
 */

const admin = require("./functions/node_modules/firebase-admin");

// ── Init ──────────────────────────────────────────────────────────────────────
const useEmulator = process.env.FIRESTORE_EMULATOR_HOST || !process.env.GOOGLE_APPLICATION_CREDENTIALS;
if (useEmulator) {
  process.env.FIRESTORE_EMULATOR_HOST = process.env.FIRESTORE_EMULATOR_HOST || "localhost:8080";
  admin.initializeApp({ projectId: "nerdblock-268a3" });
  console.log("🔧 Using Firestore emulator at", process.env.FIRESTORE_EMULATOR_HOST);
} else {
  const serviceAccount = require("./serviceAccount.json");
  admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
  console.log("☁️  Using production Firestore");
}

const db = admin.firestore();

// ── Batch helper ──────────────────────────────────────────────────────────────
async function batchWrite(collection, docs) {
  const chunks = [];
  for (let i = 0; i < docs.length; i += 400) chunks.push(docs.slice(i, i + 400));
  for (const chunk of chunks) {
    const batch = db.batch();
    chunk.forEach(({ id, data }) => {
      const ref = id ? db.collection(collection).doc(id) : db.collection(collection).doc();
      batch.set(ref, data);
    });
    await batch.commit();
  }
  console.log(`  ✓ ${collection} (${docs.length} docs)`);
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function seed() {
  console.log("\n🌱 Seeding NerdBlock Firestore...\n");

  await batchWrite("roles", [
    { id: "admin",     data: { role_name: "Administrator",   permissions: ["VIEW_CUSTOMERS","EDIT_CUSTOMERS","DELETE_CUSTOMERS","VIEW_SUBSCRIPTIONS","EDIT_SUBSCRIPTIONS","VIEW_ORDERS","EDIT_ORDERS","VIEW_INVENTORY","EDIT_INVENTORY","VIEW_REPORTS","EXPORT_REPORTS","MANAGE_USERS","VIEW_AUDIT_LOG","MANAGE_PRODUCTS","PROCESS_SHIPMENTS"] } },
    { id: "support",   data: { role_name: "Customer Support",permissions: ["VIEW_CUSTOMERS","EDIT_CUSTOMERS","VIEW_SUBSCRIPTIONS","EDIT_SUBSCRIPTIONS","VIEW_ORDERS","EDIT_ORDERS"] } },
    { id: "warehouse", data: { role_name: "Warehouse Staff", permissions: ["VIEW_ORDERS","VIEW_INVENTORY","PROCESS_SHIPMENTS"] } },
    { id: "inventory", data: { role_name: "Inventory Manager",permissions: ["VIEW_ORDERS","VIEW_INVENTORY","EDIT_INVENTORY","MANAGE_PRODUCTS"] } },
    { id: "marketing", data: { role_name: "Marketing",       permissions: ["VIEW_CUSTOMERS","VIEW_SUBSCRIPTIONS","VIEW_REPORTS","EXPORT_REPORTS"] } },
    { id: "leadership",data: { role_name: "Leadership",      permissions: ["VIEW_REPORTS","EXPORT_REPORTS","VIEW_AUDIT_LOG"] } },
  ]);

  await batchWrite("themes", [
    { id: "t1", data: { theme_name: "Classic Nerd" } },
    { id: "t2", data: { theme_name: "Horror"       } },
    { id: "t3", data: { theme_name: "Sci-Fi"       } },
    { id: "t4", data: { theme_name: "Comic Books"  } },
    { id: "t5", data: { theme_name: "Arcade"       } },
    { id: "t6", data: { theme_name: "Anime"        } },
    { id: "t7", data: { theme_name: "Gaming"       } },
    { id: "t8", data: { theme_name: "Fantasy"      } },
  ]);

  await batchWrite("content_ratings", [
    { id: "r1", data: { rating_name: "All Ages"     } },
    { id: "r2", data: { rating_name: "Teen (13+)"   } },
    { id: "r3", data: { rating_name: "Mature (18+)" } },
  ]);

  await batchWrite("warehouses", [
    { id: "w1", data: { warehouse_name: "Toronto Main Warehouse"      } },
    { id: "w2", data: { warehouse_name: "Vancouver Fulfillment Center" } },
    { id: "w3", data: { warehouse_name: "US East Distribution Hub"    } },
  ]);

  await batchWrite("subscription_plans", [
    { id: "plan_monthly", data: { plan_name: "Monthly",          duration_months: "1",  price: 29.99, is_prepaid: false } },
    { id: "plan_3mo",     data: { plan_name: "3-Month Prepaid",  duration_months: "3",  price: 79.99, is_prepaid: true  } },
    { id: "plan_6mo",     data: { plan_name: "6-Month Prepaid",  duration_months: "6",  price: 149.99,is_prepaid: true  } },
    { id: "plan_12mo",    data: { plan_name: "12-Month Prepaid", duration_months: "12", price: 269.99,is_prepaid: true  } },
  ]);

  await batchWrite("products", [
    { id: "prod1",  data: { product_name: "Batman Bobblehead",          product_desc: "Collectible Batman bobblehead figure",          product_price: 24.99, product_cost: 8.50,  product_fandom_id: "t4", product_stock: 11500 } },
    { id: "prod2",  data: { product_name: "Star Wars Lightsaber Replica",product_desc: "Miniature lightsaber desk replica",              product_price: 34.99, product_cost: 12.75, product_fandom_id: "t3", product_stock: 6000  } },
    { id: "prod3",  data: { product_name: "Naruto Kunai Set",            product_desc: "Set of 3 replica kunai throwing knives",         product_price: 19.99, product_cost: 6.25,  product_fandom_id: "t6", product_stock: 8500  } },
    { id: "prod4",  data: { product_name: "Retro Pac-Man Mug",           product_desc: "Ceramic mug with classic Pac-Man art",           product_price: 14.99, product_cost: 5.00,  product_fandom_id: "t5", product_stock: 5500  } },
    { id: "prod5",  data: { product_name: "Stranger Things T-Shirt",     product_desc: "Upside Down graphic tee",                        product_price: 29.99, product_cost: 9.50,  product_fandom_id: "t2", product_stock: 10700 } },
    { id: "prod6",  data: { product_name: "D20 Dice Set (Gold)",         product_desc: "Premium metal D20 dice set in gold finish",      product_price: 18.99, product_cost: 4.75,  product_fandom_id: "t8", product_stock: 9000  } },
    { id: "prod7",  data: { product_name: "Spider-Man Web Shooter Toy",  product_desc: "Spring-loaded web shooter replica",              product_price: 27.99, product_cost: 11.00, product_fandom_id: "t4", product_stock: 8300  } },
    { id: "prod8",  data: { product_name: "Minecraft Creeper Plush",     product_desc: "Soft plush creeper - 12 inch",                   product_price: 22.99, product_cost: 7.25,  product_fandom_id: "t7", product_stock: 6400  } },
    { id: "prod9",  data: { product_name: "Classic NerdBlock Enamel Pin",product_desc: "Limited edition NerdBlock logo enamel pin",      product_price: 9.99,  product_cost: 2.50,  product_fandom_id: "t1", product_stock: 15000 } },
    { id: "prod10", data: { product_name: "Zelda Hyrule Crest Keychain", product_desc: "Metal keychain with Hyrule crest design",        product_price: 12.99, product_cost: 3.75,  product_fandom_id: "t7", product_stock: 7600  } },
    { id: "prod11", data: { product_name: "Alien Xenomorph Figure",      product_desc: "6-inch Xenomorph articulated figure",            product_price: 39.99, product_cost: 14.00, product_fandom_id: "t3", product_stock: 2200  } },
    { id: "prod12", data: { product_name: "Dragon Ball Z Poster Set",    product_desc: "Set of 3 DBZ art posters",                       product_price: 16.99, product_cost: 4.50,  product_fandom_id: "t6", product_stock: 4000  } },
    { id: "prod14", data: { product_name: "TMNT Pizza Box Coasters",     product_desc: "Set of 4 cork coasters in pizza box",            product_price: 15.99, product_cost: 5.25,  product_fandom_id: "t1", product_stock: 5000  } },
    { id: "prod15", data: { product_name: "Mortal Kombat Arcade Token",  product_desc: "Replica brass arcade token",                     product_price: 11.99, product_cost: 3.00,  product_fandom_id: "t5", product_stock: 3200  } },
  ]);

  await batchWrite("inventory", [
    { id: "inv1",  data: { product_id:"prod1", warehouse_id:"w1", quantity_availability:8500, quantity_reserved:2000, quantity_damaged:45 } },
    { id: "inv2",  data: { product_id:"prod2", warehouse_id:"w1", quantity_availability:4200, quantity_reserved:1500, quantity_damaged:20 } },
    { id: "inv3",  data: { product_id:"prod3", warehouse_id:"w1", quantity_availability:6000, quantity_reserved:1800, quantity_damaged:10 } },
    { id: "inv4",  data: { product_id:"prod4", warehouse_id:"w1", quantity_availability:3500, quantity_reserved:800,  quantity_damaged:5  } },
    { id: "inv5",  data: { product_id:"prod5", warehouse_id:"w1", quantity_availability:7200, quantity_reserved:2500, quantity_damaged:30 } },
    { id: "inv6",  data: { product_id:"prod9", warehouse_id:"w1", quantity_availability:15000,quantity_reserved:3000, quantity_damaged:0  } },
    { id: "inv7",  data: { product_id:"prod1", warehouse_id:"w2", quantity_availability:3000, quantity_reserved:800,  quantity_damaged:10 } },
    { id: "inv8",  data: { product_id:"prod2", warehouse_id:"w2", quantity_availability:1800, quantity_reserved:600,  quantity_damaged:5  } },
    { id: "inv9",  data: { product_id:"prod11",warehouse_id:"w2", quantity_availability:2200, quantity_reserved:500,  quantity_damaged:7  } },
    { id: "inv10", data: { product_id:"prod5", warehouse_id:"w3", quantity_availability:3500, quantity_reserved:1200, quantity_damaged:18 } },
    { id: "inv11", data: { product_id:"prod14",warehouse_id:"w3", quantity_availability:5000, quantity_reserved:1100, quantity_damaged:0  } },
  ]);

  await batchWrite("box_releases", [
    { id: "rel1",  data: { theme_id:"t1", release_month:"2026-01-01", is_spoiler_visible:true  } },
    { id: "rel2",  data: { theme_id:"t2", release_month:"2026-01-01", is_spoiler_visible:true  } },
    { id: "rel3",  data: { theme_id:"t3", release_month:"2026-01-01", is_spoiler_visible:true  } },
    { id: "rel4",  data: { theme_id:"t4", release_month:"2026-01-01", is_spoiler_visible:true  } },
    { id: "rel7",  data: { theme_id:"t1", release_month:"2026-02-01", is_spoiler_visible:true  } },
    { id: "rel8",  data: { theme_id:"t2", release_month:"2026-02-01", is_spoiler_visible:true  } },
    { id: "rel13", data: { theme_id:"t1", release_month:"2026-03-01", is_spoiler_visible:false } },
    { id: "rel14", data: { theme_id:"t2", release_month:"2026-03-01", is_spoiler_visible:false } },
    { id: "rel15", data: { theme_id:"t3", release_month:"2026-03-01", is_spoiler_visible:false } },
    { id: "rel16", data: { theme_id:"t4", release_month:"2026-03-01", is_spoiler_visible:false } },
    { id: "rel17", data: { theme_id:"t5", release_month:"2026-03-01", is_spoiler_visible:false } },
    { id: "rel18", data: { theme_id:"t6", release_month:"2026-03-01", is_spoiler_visible:false } },
    { id: "rel19", data: { theme_id:"t7", release_month:"2026-03-01", is_spoiler_visible:false } },
    { id: "rel20", data: { theme_id:"t8", release_month:"2026-03-01", is_spoiler_visible:false } },
  ]);

  // NOTE: System users are created via Firebase Auth + a Cloud Function trigger.
  // To create staff accounts, use the Firebase Console or Admin SDK:
  //   auth.createUser({ email, password }) then set system_users/{uid} doc with roles array.
  console.log("\n  ℹ️  Staff accounts: create via Firebase Console → Authentication → Add User");
  console.log("     Then add a system_users/{uid} doc with { username, roles: ['Administrator'], is_active: true }");

  console.log("\n✅ Seed complete!\n");
  process.exit(0);
}

seed().catch((err) => { console.error("❌ Seed failed:", err); process.exit(1); });
