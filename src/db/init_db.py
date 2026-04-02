"""
NerdBlock Database Initializer
Converts the MSSQL schema to SQLite and seeds with sample data.
"""
import sqlite3
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "nerdblock.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ── ACCESS CONTROL ────────────────────────────────────────────────────────
    c.executescript("""
    CREATE TABLE IF NOT EXISTS role (
        role_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name VARCHAR(100) NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS permissions (
        permission_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        permission_code VARCHAR(100) NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS system_user (
        user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username      VARCHAR(100) NOT NULL UNIQUE,
        email         VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        is_active     INTEGER NOT NULL DEFAULT 1,
        created_at    DATE NOT NULL DEFAULT (DATE('now'))
    );

    CREATE TABLE IF NOT EXISTS role_permissions (
        pk_role_permission INTEGER PRIMARY KEY AUTOINCREMENT,
        permission_id      INTEGER REFERENCES permissions(permission_id),
        role_id            INTEGER REFERENCES role(role_id)
    );

    CREATE TABLE IF NOT EXISTS user_role (
        pk_user_role INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER REFERENCES system_user(user_id),
        role_id      INTEGER REFERENCES role(role_id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER REFERENCES system_user(user_id),
        entity_id   INTEGER NOT NULL,
        entity_name VARCHAR(100) NOT NULL,
        action_type VARCHAR(50) NOT NULL,
        old_value   TEXT NOT NULL DEFAULT '',
        new_value   TEXT NOT NULL DEFAULT '',
        created_at  DATE NOT NULL DEFAULT (DATE('now'))
    );

    -- ── REFERENCE / LOOKUP ───────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS country (
        country_code VARCHAR(3) PRIMARY KEY,
        country_name VARCHAR(100) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS content_rating (
        rating_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        rating_name VARCHAR(50) NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS theme (
        theme_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        theme_name VARCHAR(100) NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS warehouse (
        warehouse_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        warehouse_name VARCHAR(100) NOT NULL UNIQUE
    );

    -- ── CUSTOMER MANAGEMENT ──────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS customer (
        customer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name     VARCHAR(255) NOT NULL,
        last_name      VARCHAR(255) NOT NULL,
        email          VARCHAR(255) NOT NULL UNIQUE,
        phone_number   INTEGER,
        birth_date     DATE NOT NULL,
        age_restricted INTEGER NOT NULL DEFAULT 0,
        accnt_theme_id INTEGER NOT NULL REFERENCES theme(theme_id),
        clothing_size  VARCHAR(3),
        age_rating_pref VARCHAR(3) NOT NULL DEFAULT 'ALL',
        created_at     DATE NOT NULL DEFAULT (DATE('now'))
    );

    CREATE TABLE IF NOT EXISTS address (
        address_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        acc_id       INTEGER NOT NULL REFERENCES customer(customer_id),
        address_type VARCHAR(50) NOT NULL,
        line_1       VARCHAR(255) NOT NULL,
        line_2       VARCHAR(255) NOT NULL DEFAULT '',
        city         VARCHAR(100) NOT NULL,
        province     VARCHAR(100) NOT NULL,
        postal_code  VARCHAR(20) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS billing_address (
        address_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        acc_id       INTEGER NOT NULL REFERENCES customer(customer_id),
        address_type VARCHAR(50) NOT NULL DEFAULT 'Billing',
        line_1       VARCHAR(255) NOT NULL,
        line_2       VARCHAR(255) NOT NULL DEFAULT '',
        city         VARCHAR(100) NOT NULL,
        province     VARCHAR(100) NOT NULL,
        postal_code  VARCHAR(20) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS customer_theme (
        pk_customer_theme INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id       INTEGER NOT NULL REFERENCES customer(customer_id),
        theme_id          INTEGER NOT NULL REFERENCES theme(theme_id)
    );

    CREATE TABLE IF NOT EXISTS customer_content_rating (
        pk_customer_rating INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id        INTEGER NOT NULL REFERENCES customer(customer_id),
        rating_id          INTEGER NOT NULL REFERENCES content_rating(rating_id)
    );

    -- ── SUBSCRIPTION MANAGEMENT ──────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS subscription_plan (
        plan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name       VARCHAR(100) NOT NULL UNIQUE,
        duration_months VARCHAR(20) NOT NULL,
        price           DECIMAL(10,2) NOT NULL,
        is_prepaid      INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS subscription (
        subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id         INTEGER REFERENCES subscription_plan(plan_id),
        product_id      INTEGER NOT NULL,
        cus_id          INTEGER NOT NULL REFERENCES customer(customer_id),
        renewal_date    DATE,
        start_date      DATE NOT NULL,
        auto_renew      INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS subscription_event (
        event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER REFERENCES subscription(subscription_id),
        event_type      VARCHAR(50) NOT NULL,
        event_date      DATE NOT NULL DEFAULT (DATE('now'))
    );

    -- ── PRODUCTS & INVENTORY ─────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS product (
        product_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name    VARCHAR(50) NOT NULL,
        product_desc    VARCHAR(255),
        product_price   DECIMAL(10,2) NOT NULL,
        product_cost    DECIMAL(10,2) NOT NULL,
        product_fandom_id INTEGER NOT NULL REFERENCES theme(theme_id),
        product_stock   INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS inventory (
        inventory_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id            INTEGER NOT NULL REFERENCES product(product_id),
        warehouse_id          INTEGER NOT NULL REFERENCES warehouse(warehouse_id),
        quantity_availability INTEGER NOT NULL DEFAULT 0,
        quantity_reserved     INTEGER NOT NULL DEFAULT 0,
        quantity_damaged      INTEGER NOT NULL DEFAULT 0,
        UNIQUE(product_id, warehouse_id)
    );

    -- ── ORDERS & FULFILLMENT ─────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS box_release (
        release_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        theme_id          INTEGER NOT NULL REFERENCES theme(theme_id),
        release_month     DATE NOT NULL,
        is_spoiler_visible INTEGER NOT NULL DEFAULT 0,
        UNIQUE(theme_id, release_month)
    );

    CREATE TABLE IF NOT EXISTS customer_order (
        order_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER NOT NULL REFERENCES subscription(subscription_id),
        release_id      INTEGER NOT NULL REFERENCES box_release(release_id),
        order_status    VARCHAR(20) NOT NULL DEFAULT 'Pending',
        created_at      DATE NOT NULL DEFAULT (DATE('now'))
    );

    CREATE TABLE IF NOT EXISTS shipment (
        shipment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id        INTEGER REFERENCES customer_order(order_id),
        shipment_status VARCHAR(50) NOT NULL,
        tracking_number INTEGER,
        shipped_date    DATE,
        delivered_date  DATE
    );

    -- ── FINANCIAL & TAX ──────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS payment_transaction (
        transaction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER NOT NULL REFERENCES subscription(subscription_id),
        order_id        INTEGER NOT NULL REFERENCES customer_order(order_id),
        amount          DECIMAL(10,2) NOT NULL,
        currency_code   VARCHAR(3) NOT NULL,
        tax_amount      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
        discount_amount DECIMAL(10,2),
        payment_status  VARCHAR(20) NOT NULL,
        created_at      DATE DEFAULT (DATE('now'))
    );

    CREATE TABLE IF NOT EXISTS tax_rate (
        tax_rate_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        country_code   VARCHAR(3) NOT NULL REFERENCES country(country_code),
        tax_name       VARCHAR(50) NOT NULL,
        tax_percentage DECIMAL(10,2) NOT NULL,
        effective_from DATE NOT NULL
    );

    -- ── LEGACY DATA MIGRATION ────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS legacy_import_batch (
        import_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        import_date     DATE NOT NULL DEFAULT (DATE('now')),
        source_system   VARCHAR(100) NOT NULL,
        status          VARCHAR(20) NOT NULL DEFAULT 'Pending'
    );

    CREATE TABLE IF NOT EXISTS legacy_import_log (
        import_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id      INTEGER NOT NULL REFERENCES legacy_import_batch(import_batch_id),
        entity_name   VARCHAR(100) NOT NULL,
        legacy_key    INTEGER NOT NULL,
        status        VARCHAR(20) NOT NULL,
        error_message TEXT
    );
    """)

    # Check if already seeded
    existing = c.execute("SELECT COUNT(*) FROM role").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    # ── SEED DATA ─────────────────────────────────────────────────────────────
    c.executescript("""
    INSERT INTO role (role_name) VALUES
        ('Administrator'),('Customer Support'),('Warehouse Staff'),
        ('Inventory Manager'),('Marketing'),('Leadership');

    INSERT INTO permissions (permission_code) VALUES
        ('VIEW_CUSTOMERS'),('EDIT_CUSTOMERS'),('DELETE_CUSTOMERS'),
        ('VIEW_SUBSCRIPTIONS'),('EDIT_SUBSCRIPTIONS'),
        ('VIEW_ORDERS'),('EDIT_ORDERS'),
        ('VIEW_INVENTORY'),('EDIT_INVENTORY'),
        ('VIEW_REPORTS'),('EXPORT_REPORTS'),
        ('MANAGE_USERS'),('VIEW_AUDIT_LOG'),
        ('MANAGE_PRODUCTS'),('PROCESS_SHIPMENTS');

    -- Admin gets all permissions
    INSERT INTO role_permissions (role_id, permission_id)
        SELECT 1, permission_id FROM permissions;

    -- Customer Support
    INSERT INTO role_permissions (role_id, permission_id) VALUES
        (2,1),(2,2),(2,4),(2,5),(2,6),(2,7);

    -- Warehouse Staff
    INSERT INTO role_permissions (role_id, permission_id) VALUES
        (3,6),(3,8),(3,15);

    -- Inventory Manager
    INSERT INTO role_permissions (role_id, permission_id) VALUES
        (4,6),(4,8),(4,9),(4,14);

    -- Marketing
    INSERT INTO role_permissions (role_id, permission_id) VALUES
        (5,1),(5,4),(5,10),(5,11);

    -- Leadership
    INSERT INTO role_permissions (role_id, permission_id) VALUES
        (6,10),(6,11),(6,13);

    INSERT INTO country (country_code, country_name) VALUES
        ('CA','Canada'),('US','United States'),('GB','United Kingdom'),
        ('DE','Germany'),('FR','France'),('AU','Australia'),
        ('JP','Japan'),('BR','Brazil'),('MX','Mexico'),('IN','India');

    INSERT INTO content_rating (rating_name) VALUES
        ('All Ages'),('Teen (13+)'),('Mature (18+)');

    INSERT INTO theme (theme_name) VALUES
        ('Classic Nerd'),('Horror'),('Sci-Fi'),('Comic Books'),
        ('Arcade'),('Anime'),('Gaming'),('Fantasy');

    INSERT INTO warehouse (warehouse_name) VALUES
        ('Toronto Main Warehouse'),
        ('Vancouver Fulfillment Center'),
        ('US East Distribution Hub');

    INSERT INTO subscription_plan (plan_name, duration_months, price, is_prepaid) VALUES
        ('Monthly','1',29.99,0),
        ('3-Month Prepaid','3',79.99,1),
        ('6-Month Prepaid','6',149.99,1),
        ('12-Month Prepaid','12',269.99,1);
    """)

    # Hash passwords properly
    def hash_pw(pw):
        return hashlib.sha256(pw.encode()).hexdigest()

    system_users = [
        ('alex.ceo',        'alex@nerdblock.com',    hash_pw('Admin123!'), 1),
        ('sarah.support',   'sarah@nerdblock.com',   hash_pw('Support1!'), 1),
        ('mike.warehouse',  'mike@nerdblock.com',    hash_pw('Warehouse1!'), 1),
        ('jenny.inventory', 'jenny@nerdblock.com',   hash_pw('Inventory1!'), 1),
        ('omar.marketing',  'omar@nerdblock.com',    hash_pw('Marketing1!'), 1),
        ('lisa.support',    'lisa@nerdblock.com',    hash_pw('Support2!'), 1),
    ]
    c.executemany(
        "INSERT INTO system_user (username, email, password_hash, is_active) VALUES (?,?,?,?)",
        system_users
    )

    c.executemany(
        "INSERT INTO user_role (user_id, role_id) VALUES (?,?)",
        [(1,1),(1,6),(2,2),(3,3),(4,4),(5,5),(6,2)]
    )

    customers = [
        ('James','Chen','james.chen@email.com',4165550101,'1992-03-15',0,1,'L','ALL'),
        ('Maria','Rodriguez','maria.r@email.com',6475550202,'1988-07-22',0,2,'M','ALL'),
        ('Aisha','Patel','aisha.p@email.com',None,'1995-11-30',0,6,'S','13+'),
        ('Liam',"O'Brien",'liam.ob@email.com',9055550404,'1990-01-10',0,3,'XL','ALL'),
        ('Yuki','Tanaka','yuki.t@email.com',None,'1997-05-18',0,6,'M','13+'),
        ('Sophie','Muller','sophie.m@email.com',None,'1993-09-25',0,2,'S','ALL'),
        ('David','Kim','david.kim@email.com',2125550707,'1985-12-02',0,4,'L','ALL'),
        ('Emma','Wilson','emma.w@email.com',None,'1991-06-14',0,1,'M','13+'),
        ('Carlos','Santos','carlos.s@email.com',None,'1994-08-07',0,7,'L','ALL'),
        ('Priya','Sharma','priya.s@email.com',None,'1996-02-28',0,6,'S','ALL'),
        ('Nathan','Brown','nathan.b@email.com',6045551111,'1989-04-19',0,3,'XL','ALL'),
        ('Olivia','Taylor','olivia.t@email.com',4165551212,'1998-10-11',0,1,'M','13+'),
        ('Kenji','Watanabe','kenji.w@email.com',None,'1987-07-03',0,6,'L','ALL'),
        ('Fatima','Al-Hassan','fatima.ah@email.com',9055551414,'1993-01-20',0,4,'M','ALL'),
        ('Ryan','Mitchell','ryan.m@email.com',6475551515,'2000-11-05',0,5,'L','ALL'),
    ]
    c.executemany(
        """INSERT INTO customer (first_name,last_name,email,phone_number,birth_date,
           age_restricted,accnt_theme_id,clothing_size,age_rating_pref) VALUES (?,?,?,?,?,?,?,?,?)""",
        customers
    )

    addresses = [
        (1,'Shipping','150 King St W','Unit 2201','Toronto','Ontario','M5H 1J9'),
        (2,'Shipping','3085 Hurontario St','Apt 1407','Mississauga','Ontario','L5B 1M8'),
        (3,'Shipping','25 Peel Centre Dr','N/A','Brampton','Ontario','L6T 3R5'),
        (4,'Shipping','481 North Service Rd','N/A','Oakville','Ontario','L6M 2V6'),
        (5,'Shipping','1-1 Marunouchi','5F','Chiyoda-ku','Tokyo','100-0005'),
        (6,'Shipping','Friedrichstr. 123','N/A','Berlin','Berlin','10117'),
        (7,'Shipping','350 5th Avenue','Suite 4800','New York','New York','10118'),
        (8,'Shipping','221B Baker Street','N/A','London','England','NW1 6XE'),
        (9,'Shipping','Av. Paulista 1578','Conj. 12','Sao Paulo','SP','01310-200'),
        (10,'Shipping','42 Marine Drive','N/A','Mumbai','Maharashtra','400002'),
        (11,'Shipping','1055 W Georgia St','Unit 803','Vancouver','British Columbia','V6E 3P3'),
        (12,'Shipping','88 Queens Quay W','Unit 510','Toronto','Ontario','M5J 0B8'),
        (13,'Shipping','1-1 Umeda','3F','Kita-ku','Osaka','530-0001'),
        (14,'Shipping','5000 Hwy 7 East','Unit 201','Markham','Ontario','L3R 4M9'),
        (15,'Shipping','33 Bay St','Unit 1605','Toronto','Ontario','M5J 2Z3'),
    ]
    c.executemany(
        "INSERT INTO address (acc_id,address_type,line_1,line_2,city,province,postal_code) VALUES (?,?,?,?,?,?,?)",
        addresses
    )

    billing_addrs = [
        (1,'Billing','150 King St W','Unit 2201','Toronto','Ontario','M5H 1J9'),
        (4,'Billing','481 North Service Rd','N/A','Oakville','Ontario','L6M 2V6'),
        (7,'Billing','350 5th Avenue','Suite 4800','New York','New York','10118'),
        (11,'Billing','1055 W Georgia St','Unit 803','Vancouver','British Columbia','V6E 3P3'),
    ]
    c.executemany(
        "INSERT INTO billing_address (acc_id,address_type,line_1,line_2,city,province,postal_code) VALUES (?,?,?,?,?,?,?)",
        billing_addrs
    )

    cust_themes = [
        (1,1),(1,4),(2,2),(2,6),(3,6),(3,7),(4,3),(4,8),(5,6),
        (6,2),(6,3),(7,4),(7,5),(8,1),(8,8),(9,7),(9,5),(10,6),(10,4),
        (11,3),(11,7),(12,1),(12,2),(13,6),(13,7),(14,4),(14,8),(15,5),(15,1),
    ]
    c.executemany("INSERT INTO customer_theme (customer_id,theme_id) VALUES (?,?)", cust_themes)

    cust_ratings = [
        (1,1),(1,2),(1,3),(2,1),(2,2),(2,3),(3,1),(3,2),(4,1),(4,2),(4,3),
        (5,1),(5,2),(6,1),(6,2),(6,3),(7,1),(7,2),(7,3),(8,1),(8,2),
        (9,1),(9,2),(9,3),(10,1),(11,1),(11,2),(11,3),(12,1),(12,2),
        (13,1),(13,2),(13,3),(14,1),(14,2),(15,1),(15,2),(15,3),
    ]
    c.executemany("INSERT INTO customer_content_rating (customer_id,rating_id) VALUES (?,?)", cust_ratings)

    products = [
        ('Batman Bobblehead','Collectible Batman bobblehead figure',24.99,8.50,4,11500),
        ('Star Wars Lightsaber Replica','Miniature lightsaber desk replica',34.99,12.75,3,6000),
        ('Naruto Kunai Set','Set of 3 replica kunai throwing knives',19.99,6.25,6,8500),
        ('Retro Pac-Man Mug','Ceramic mug with classic Pac-Man art',14.99,5.00,5,5500),
        ('Stranger Things T-Shirt','Upside Down graphic tee',29.99,9.50,2,10700),
        ('D20 Dice Set (Gold)','Premium metal D20 dice set in gold finish',18.99,4.75,8,9000),
        ('Spider-Man Web Shooter Toy','Spring-loaded web shooter replica',27.99,11.00,4,8300),
        ('Minecraft Creeper Plush','Soft plush creeper - 12 inch',22.99,7.25,7,6400),
        ('Classic NerdBlock Enamel Pin','Limited edition NerdBlock logo enamel pin',9.99,2.50,1,15000),
        ('Zelda Hyrule Crest Keychain','Metal keychain with Hyrule crest design',12.99,3.75,7,7600),
        ('Alien Xenomorph Figure','6-inch Xenomorph articulated figure',39.99,14.00,3,2200),
        ('Dragon Ball Z Poster Set','Set of 3 DBZ art posters',16.99,4.50,6,4000),
        ('Elvira Horror Host Vinyl','Vinyl figure of Elvira - discontinued',44.99,16.50,2,0),
        ('TMNT Pizza Box Coasters','Set of 4 cork coasters in pizza box',15.99,5.25,1,5000),
        ('Mortal Kombat Arcade Token','Replica brass arcade token',11.99,3.00,5,3200),
    ]
    c.executemany(
        """INSERT INTO product (product_name,product_desc,product_price,product_cost,
           product_fandom_id,product_stock) VALUES (?,?,?,?,?,?)""",
        products
    )

    inventory_rows = [
        (1,1,8500,2000,45),(2,1,4200,1500,20),(3,1,6000,1800,10),(4,1,3500,800,5),
        (5,1,7200,2500,30),(6,1,9000,1200,0),(7,1,5500,2000,15),(8,1,4800,1600,8),
        (9,1,15000,3000,0),(10,1,6200,1400,12),
        (1,2,3000,800,10),(2,2,1800,600,5),(3,2,2500,700,3),(11,2,2200,500,7),(12,2,4000,1000,0),
        (4,3,2000,400,2),(5,3,3500,1200,18),(7,3,2800,900,6),(14,3,5000,1100,0),(15,3,3200,600,0),
    ]
    c.executemany(
        """INSERT INTO inventory (product_id,warehouse_id,quantity_availability,
           quantity_reserved,quantity_damaged) VALUES (?,?,?,?,?)""",
        inventory_rows
    )

    subscriptions = [
        (1,9,1,'2026-04-15','2025-01-15',1),(2,1,1,'2026-06-01','2025-06-01',1),
        (3,5,2,'2026-09-10','2025-03-10',1),(1,3,3,None,'2025-05-20',0),
        (4,2,4,'2026-01-01','2025-01-01',1),(1,3,5,'2026-04-01','2025-07-01',1),
        (2,5,6,'2026-06-15','2025-09-15',1),(1,7,7,None,'2025-02-01',0),
        (3,9,8,'2026-10-01','2025-04-01',1),(1,8,9,'2026-04-10','2025-08-10',1),
        (2,3,10,'2026-07-01','2025-10-01',1),(4,2,11,'2026-02-15','2025-02-15',1),
        (1,9,12,'2026-04-20','2025-06-20',1),(1,3,13,None,'2025-11-01',0),
        (2,1,14,'2026-06-01','2025-12-01',1),(1,4,15,'2026-04-05','2026-01-05',1),
    ]
    c.executemany(
        "INSERT INTO subscription (plan_id,product_id,cus_id,renewal_date,start_date,auto_renew) VALUES (?,?,?,?,?,?)",
        subscriptions
    )

    sub_events = [
        (1,'Created','2025-01-15'),(1,'Renewed','2025-02-15'),(1,'Renewed','2025-03-15'),
        (2,'Created','2025-06-01'),(2,'Renewed','2025-09-01'),(3,'Created','2025-03-10'),
        (3,'Renewed','2025-09-10'),(4,'Created','2025-05-20'),(4,'Paused','2025-10-01'),
        (8,'Created','2025-02-01'),(8,'Cancelled','2025-10-15'),(14,'Created','2025-11-01'),
        (14,'Cancelled','2026-02-01'),(5,'Created','2025-01-01'),(12,'Created','2025-02-15'),
        (12,'Skipped','2025-08-15'),
    ]
    c.executemany(
        "INSERT INTO subscription_event (subscription_id,event_type,event_date) VALUES (?,?,?)",
        sub_events
    )

    releases = [
        (1,'2026-01-01',1),(2,'2026-01-01',1),(3,'2026-01-01',1),(4,'2026-01-01',1),
        (6,'2026-01-01',1),(7,'2026-01-01',1),(1,'2026-02-01',1),(2,'2026-02-01',1),
        (3,'2026-02-01',1),(4,'2026-02-01',1),(6,'2026-02-01',1),(7,'2026-02-01',1),
        (1,'2026-03-01',0),(2,'2026-03-01',0),(3,'2026-03-01',0),(4,'2026-03-01',0),
        (5,'2026-03-01',0),(6,'2026-03-01',0),(7,'2026-03-01',0),(8,'2026-03-01',0),
    ]
    c.executemany(
        "INSERT INTO box_release (theme_id,release_month,is_spoiler_visible) VALUES (?,?,?)",
        releases
    )

    orders = [
        (1,1,'Delivered','2026-01-02'),(2,4,'Delivered','2026-01-02'),(3,2,'Delivered','2026-01-02'),
        (5,3,'Delivered','2026-01-02'),(6,5,'Delivered','2026-01-02'),(7,2,'Delivered','2026-01-02'),
        (9,1,'Delivered','2026-01-02'),(10,6,'Delivered','2026-01-02'),(11,5,'Delivered','2026-01-02'),
        (12,3,'Delivered','2026-01-02'),(13,1,'Delivered','2026-01-02'),(15,4,'Delivered','2026-01-02'),
        (1,7,'Delivered','2026-02-02'),(2,10,'Delivered','2026-02-02'),(3,8,'Delivered','2026-02-02'),
        (5,9,'Delivered','2026-02-02'),(6,11,'Delivered','2026-02-02'),(9,7,'Delivered','2026-02-02'),
        (10,12,'Delivered','2026-02-02'),(13,7,'Delivered','2026-02-02'),(16,17,'Delivered','2026-02-02'),
        (1,13,'Shipped','2026-03-02'),(2,16,'Shipped','2026-03-02'),(3,14,'Packed','2026-03-02'),
        (5,15,'Shipped','2026-03-02'),(6,18,'Pending','2026-03-02'),(9,13,'Pending','2026-03-02'),
        (10,19,'Pending','2026-03-02'),(13,13,'Packed','2026-03-02'),(15,16,'Pending','2026-03-02'),
        (16,17,'Pending','2026-03-02'),
    ]
    c.executemany(
        "INSERT INTO customer_order (subscription_id,release_id,order_status,created_at) VALUES (?,?,?,?)",
        orders
    )

    shipments = [
        (1,'Delivered',202600001,'2026-01-05','2026-01-10'),
        (2,'Delivered',202600002,'2026-01-05','2026-01-10'),
        (3,'Delivered',202600003,'2026-01-05','2026-01-09'),
        (4,'Delivered',202600004,'2026-01-05','2026-01-11'),
        (5,'Delivered',202600005,'2026-01-06','2026-01-18'),
        (6,'Delivered',202600006,'2026-01-06','2026-01-16'),
        (7,'Delivered',202600007,'2026-01-05','2026-01-10'),
        (8,'Delivered',202600008,'2026-01-05','2026-01-09'),
        (9,'Delivered',202600009,'2026-01-06','2026-01-17'),
        (10,'Delivered',202600010,'2026-01-05','2026-01-11'),
        (11,'Delivered',202600011,'2026-01-05','2026-01-09'),
        (12,'Delivered',202600012,'2026-01-05','2026-01-10'),
        (4,'Delivered',202600040,'2026-01-14','2026-01-18'),
        (13,'Delivered',202600013,'2026-02-05','2026-02-09'),
        (14,'Delivered',202600014,'2026-02-05','2026-02-09'),
        (15,'Delivered',202600015,'2026-02-05','2026-02-10'),
        (16,'Delivered',202600016,'2026-02-05','2026-02-11'),
        (17,'Delivered',202600017,'2026-02-06','2026-02-18'),
        (18,'Delivered',202600018,'2026-02-05','2026-02-10'),
        (19,'Delivered',202600019,'2026-02-05','2026-02-09'),
        (20,'Delivered',202600020,'2026-02-05','2026-02-09'),
        (21,'Delivered',202600021,'2026-02-05','2026-02-10'),
        (22,'In Transit',202600022,'2026-03-05',None),
        (23,'In Transit',202600023,'2026-03-05',None),
        (25,'Shipped',202600025,'2026-03-06',None),
    ]
    c.executemany(
        "INSERT INTO shipment (order_id,shipment_status,tracking_number,shipped_date,delivered_date) VALUES (?,?,?,?,?)",
        shipments
    )

    transactions = [
        (1,1,29.99,'CAD',3.90,None,'Completed','2026-01-02'),
        (2,2,26.66,'CAD',3.47,None,'Completed','2026-01-02'),
        (3,3,25.00,'CAD',3.25,None,'Completed','2026-01-02'),
        (5,4,22.50,'CAD',2.93,None,'Completed','2026-01-02'),
        (6,5,29.99,'JPY',3.00,None,'Completed','2026-01-02'),
        (7,6,26.66,'EUR',5.07,None,'Completed','2026-01-02'),
        (9,7,25.00,'GBP',5.00,None,'Completed','2026-01-02'),
        (10,8,29.99,'CAD',3.90,None,'Completed','2026-01-02'),
        (11,9,26.66,'INR',4.80,None,'Completed','2026-01-02'),
        (12,10,22.50,'CAD',2.93,None,'Completed','2026-01-02'),
        (13,11,29.99,'CAD',3.90,None,'Completed','2026-01-02'),
        (15,12,26.66,'CAD',3.47,None,'Completed','2026-01-02'),
        (1,13,29.99,'CAD',3.90,None,'Completed','2026-02-02'),
        (2,14,26.66,'CAD',3.47,None,'Completed','2026-02-02'),
        (3,15,25.00,'CAD',3.25,None,'Completed','2026-02-02'),
        (5,16,22.50,'CAD',2.93,None,'Completed','2026-02-02'),
        (6,17,29.99,'JPY',3.00,None,'Completed','2026-02-02'),
        (9,18,25.00,'GBP',5.00,None,'Completed','2026-02-02'),
        (10,19,29.99,'CAD',3.90,None,'Completed','2026-02-02'),
        (13,20,29.99,'CAD',3.90,None,'Completed','2026-02-02'),
        (16,21,29.99,'CAD',3.90,None,'Completed','2026-02-02'),
        (1,22,29.99,'CAD',3.90,None,'Completed','2026-03-02'),
        (2,23,26.66,'CAD',3.47,None,'Completed','2026-03-02'),
        (3,24,25.00,'CAD',3.25,None,'Completed','2026-03-02'),
        (5,25,22.50,'CAD',2.93,None,'Completed','2026-03-02'),
        (10,28,29.99,'CAD',3.90,None,'Failed','2026-03-02'),
        (5,4,22.50,'CAD',2.93,None,'Refunded','2026-01-13'),
    ]
    c.executemany(
        """INSERT INTO payment_transaction (subscription_id,order_id,amount,currency_code,
           tax_amount,discount_amount,payment_status,created_at) VALUES (?,?,?,?,?,?,?,?)""",
        transactions
    )

    tax_rates = [
        ('CA','HST Ontario',13.00,'2025-01-01'),
        ('CA','GST',5.00,'2025-01-01'),
        ('CA','PST British Columbia',7.00,'2025-01-01'),
        ('US','Sales Tax (avg)',7.25,'2025-01-01'),
        ('GB','VAT',20.00,'2025-01-01'),
        ('DE','MwSt (VAT)',19.00,'2025-01-01'),
        ('FR','TVA',20.00,'2025-01-01'),
        ('AU','GST',10.00,'2025-01-01'),
        ('JP','Consumption Tax',10.00,'2025-01-01'),
        ('BR','ICMS (avg)',18.00,'2025-01-01'),
        ('MX','IVA',16.00,'2025-01-01'),
        ('IN','GST',18.00,'2025-01-01'),
    ]
    c.executemany(
        "INSERT INTO tax_rate (country_code,tax_name,tax_percentage,effective_from) VALUES (?,?,?,?)",
        tax_rates
    )

    audit_entries = [
        (2,'subscription',4,'UPDATE','status: Active','status: Paused'),
        (2,'address',3,'UPDATE','line_1: 24 Peel Centre','line_1: 25 Peel Centre Dr'),
        (4,'inventory',1,'UPDATE','quantity_damaged: 40','quantity_damaged: 45'),
        (6,'subscription',14,'UPDATE','status: Active','status: Cancelled'),
        (3,'shipment',13,'INSERT','N/A','order_id: 4, replacement'),
    ]
    c.executemany(
        "INSERT INTO audit_log (user_id,entity_name,entity_id,action_type,old_value,new_value) VALUES (?,?,?,?,?,?)",
        audit_entries
    )

    conn.commit()
    conn.close()
    print("✅ NerdBlock database initialized and seeded.")


if __name__ == "__main__":
    init_db()
