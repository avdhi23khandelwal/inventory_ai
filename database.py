import os
import time
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from contextlib import contextmanager
import random

# ---------------------------------------------------------------------------
# Database file location — use a WRITABLE directory.
# On Streamlit Cloud, /mount/src/ (where the code lives) is read-only.
# The home directory (~) is always writable.
# ---------------------------------------------------------------------------
DB_DIR = os.path.expanduser("~")  # /home/adminuser on Streamlit Cloud
DB_FILE = os.path.join(DB_DIR, "inventory.db")

# If an old read-only inventory.db exists in the CWD, ignore it — use the home dir.
# If the home dir DB also exists but is read-only (very rare), use a timestamped name.
if os.path.exists(DB_FILE):
    try:
        # Test if we can write to it
        with open(DB_FILE, "a") as f:
            pass
    except (PermissionError, OSError):
        DB_FILE = os.path.join(DB_DIR, f"inventory_{int(time.time())}.db")
        print(f"Old DB was read-only — using new file: {DB_FILE}")

DATABASE_URL = f"sqlite:///{DB_FILE}"
print(f"Database location: {DB_FILE}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

#from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
#from sqlalchemy.ext.declarative import declarative_base
#from sqlalchemy.orm import sessionmaker
#from datetime import datetime, timedelta
#from contextlib import contextmanager
#import random

#DATABASE_URL = "sqlite:///inventory.db"
#engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True)
#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#Base = declarative_base()


# ---------- Models ----------
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    name = Column(String)
    category = Column(String, default="Electronics")
    price = Column(Float)
    supplier = Column(String)
    lead_time_days = Column(Integer, default=7)
    cost = Column(Float, default=0.0)


class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    amazon_stock = Column(Integer, default=0)
    flipkart_stock = Column(Integer, default=0)
    myntra_stock = Column(Integer, default=0)
    website_stock = Column(Integer, default=0)
    total_stock = Column(Integer, default=0)
    reorder_point = Column(Integer, default=0)
    status = Column(String, default="Healthy")
    warehouse = Column(String, default="Zone-A")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(String, unique=True)
    sku = Column(String, index=True)
    qty = Column(Integer)
    status = Column(String, default="Draft")
    created_at = Column(DateTime)
    approved_at = Column(DateTime, nullable=True)
    rationale = Column(Text, default="")


class AgentLog(Base):
    __tablename__ = "agent_logs"
    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String)
    action = Column(String)
    details = Column(String)
    timestamp = Column(DateTime)


class Returns(Base):
    __tablename__ = "returns"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String)
    sku = Column(String)
    channel = Column(String)
    reason = Column(String)
    status = Column(String, default="Pending")
    created_at = Column(DateTime)


class SalesHistory(Base):
    __tablename__ = "sales_history"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)
    date = Column(String)
    quantity = Column(Integer)
    forecasted_demand = Column(Integer, default=0)


# ---------- NEW tables (D) ----------
class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    contact_email = Column(String, default="")
    phone = Column(String, default="")
    lead_time_days = Column(Integer, default=7)
    on_time_rate = Column(Float, default=0.95)
    quality_rate = Column(Float, default=0.98)
    active = Column(Boolean, default=True)


class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(String, unique=True)
    po_id = Column(String, index=True, nullable=True)
    sku = Column(String, index=True)
    qty = Column(Integer)
    carrier = Column(String, default="FedEx")
    tracking_id = Column(String, default="")
    status = Column(String, default="In Transit")
    eta = Column(DateTime, nullable=True)
    created_at = Column(DateTime)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    severity = Column(String, default="info")
    source = Column(String)
    sku = Column(String, nullable=True)
    message = Column(String)
    created_at = Column(DateTime)
    resolved = Column(Boolean, default=False)


class AuditTrail(Base):
    __tablename__ = "audit_trail"
    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String)
    action = Column(String)
    entity = Column(String)
    entity_id = Column(String, default="")
    before = Column(Text, default="")
    after = Column(Text, default="")
    timestamp = Column(DateTime)


Base.metadata.create_all(bind=engine)
def init_db():
    """
    Initializes the database. If products don't exist (meaning the DB is
    empty OR in a partial state from a failed seed), wipes everything
    and re-seeds fresh. This handles all edge cases:
    - Old schema (no suppliers table)
    - Partial state (suppliers exist but products don't)
    - Completely empty DB
    """
    from sqlalchemy import inspect

    # First, make sure ALL tables exist (creates any missing ones)
    Base.metadata.create_all(bind=engine)

    # Check if DB is already fully seeded (products exist)
    check_db = SessionLocal()
    try:
        products_exist = check_db.query(Product).first() is not None
    except Exception:
        # If the query itself fails (schema mismatch), force a wipe
        products_exist = False
    finally:
        check_db.close()

    # If products exist, DB is seeded — nothing to do.
    if products_exist:
        return

    # Otherwise, wipe EVERYTHING and recreate fresh.
    # This handles: old schema, partial state, empty DB, schema mismatch.
    print("Database not fully seeded — wiping and re-creating fresh...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ---- Suppliers ----
        suppliers = [
            Supplier(name="Sony", contact_email="sales@sony.com", phone="+1-555-0101", lead_time_days=10, on_time_rate=0.97, quality_rate=0.99),
            Supplier(name="Apple", contact_email="b2b@apple.com", phone="+1-555-0102", lead_time_days=14, on_time_rate=0.95, quality_rate=0.99),
            Supplier(name="Logitech", contact_email="wholesale@logi.com", phone="+1-555-0103", lead_time_days=5, on_time_rate=0.98, quality_rate=0.97),
            Supplier(name="Samsung", contact_email="partners@samsung.com", phone="+1-555-0104", lead_time_days=9, on_time_rate=0.93, quality_rate=0.97),
            Supplier(name="Nikon", contact_email="pro@nikon.com", phone="+1-555-0105", lead_time_days=21, on_time_rate=0.89, quality_rate=0.99),
            Supplier(name="Amazon", contact_email="vendor@amazon.com", phone="+1-555-0106", lead_time_days=3, on_time_rate=0.99, quality_rate=0.95),
        ]
        db.add_all(suppliers)
        db.commit()

        # ---- Products ----
        products = [
            Product(sku='WH-1000XM5',  name='Sony Headphones',  category='Electronics', price=348.00,  cost=240.00, supplier='Sony',     lead_time_days=10),
            Product(sku='IPH-15-PRO',  name='iPhone 15 Pro',    category='Mobile',      price=999.00,  cost=720.00, supplier='Apple',    lead_time_days=14),
            Product(sku='GAM-MOUS',    name='Logitech G502',    category='Accessories', price=49.99,   cost=22.00,  supplier='Logitech', lead_time_days=5),
            Product(sku='SAMSUNG-S24', name='Samsung S24',      category='Mobile',      price=799.00,  cost=560.00, supplier='Samsung',  lead_time_days=9),
            Product(sku='MAC-PRO-14',  name='MacBook Pro 14',   category='Electronics', price=1999.00, cost=1450.00, supplier='Apple',   lead_time_days=14),
            Product(sku='NIK-Z9',      name='Nikon Z9 Camera',  category='Electronics', price=5499.00, cost=4100.00, supplier='Nikon',    lead_time_days=21),
            Product(sku='ALEXA-DOT',   name='Alexa Dot 5',      category='Electronics', price=49.00,   cost=22.00,  supplier='Amazon',   lead_time_days=3),
            Product(sku='AIR-PODS',    name='AirPods Pro 2',    category='Accessories', price=249.00,  cost=170.00, supplier='Apple',    lead_time_days=14),
        ]

        # ---- Inventory ----
        inventory = [
            Inventory(sku='WH-1000XM5',  total_stock=150, amazon_stock=50, flipkart_stock=50, myntra_stock=30, website_stock=20, reorder_point=40,  status="Healthy",  warehouse='Zone-A'),
            Inventory(sku='IPH-15-PRO',  total_stock=12,  amazon_stock=4,  flipkart_stock=4,  myntra_stock=2,  website_stock=2,  reorder_point=20,  status="Critical", warehouse='Zone-B'),
            Inventory(sku='GAM-MOUS',    total_stock=300, amazon_stock=100, flipkart_stock=100, myntra_stock=50, website_stock=50, reorder_point=80,  status="Healthy",  warehouse='Zone-A'),
            Inventory(sku='SAMSUNG-S24', total_stock=85,  amazon_stock=30, flipkart_stock=30, myntra_stock=15, website_stock=10, reorder_point=50,  status="Low",      warehouse='Zone-B'),
            Inventory(sku='MAC-PRO-14',  total_stock=45,  amazon_stock=15, flipkart_stock=15, myntra_stock=10, website_stock=5,  reorder_point=20,  status="Low",      warehouse='Zone-A'),
            Inventory(sku='NIK-Z9',      total_stock=5,   amazon_stock=1,  flipkart_stock=2,  myntra_stock=1,  website_stock=1,  reorder_point=10,  status="Critical", warehouse='Zone-B'),
            Inventory(sku='ALEXA-DOT',   total_stock=200, amazon_stock=70, flipkart_stock=70, myntra_stock=30, website_stock=30, reorder_point=100, status="Healthy",  warehouse='Zone-A'),
            Inventory(sku='AIR-PODS',    total_stock=90,  amazon_stock=30, flipkart_stock=30, myntra_stock=15, website_stock=15, reorder_point=40,  status="Healthy",  warehouse='Zone-A'),
        ]

        # ---- Sales history (30 days back) ----
        sales = []
        base_date = datetime.now() - timedelta(days=30)
        for p in products:
            base_demand = random.randint(10, 40)
            for i in range(30):
                d = base_date + timedelta(days=i)
                weekday = d.weekday()
                weekly_bump = 1.15 if weekday >= 5 else 1.0
                trend = 1.0 + (i * 0.005)
                qty = max(1, int(base_demand * weekly_bump * trend * random.uniform(0.85, 1.15)))
                forecast = int(qty * 1.05)
                sales.append(SalesHistory(sku=p.sku, date=d.date().isoformat(), quantity=qty, forecasted_demand=forecast))

        # ---- Returns ----
        returns = [
            Returns(order_id='ORD-991', sku='WH-1000XM5',  channel='Amazon',   reason='Damaged Packaging', status='Processed', created_at=datetime.utcnow()),
            Returns(order_id='ORD-992', sku='IPH-15-PRO',  channel='Flipkart', reason='Wrong Item',        status='Pending',   created_at=datetime.utcnow()),
            Returns(order_id='ORD-993', sku='AIR-PODS',    channel='Myntra',   reason='Late Delivery',     status='Pending',   created_at=datetime.utcnow() - timedelta(days=2)),
            Returns(order_id='ORD-994', sku='SAMSUNG-S24', channel='Website',  reason='Defective Unit',    status='Processed', created_at=datetime.utcnow() - timedelta(days=5)),
        ]

        # ---- Shipments ----
        shipments = [
            Shipment(shipment_id='SHP-5001', po_id=None, sku='WH-1000XM5',  qty=100, carrier='FedEx',  tracking_id='FX-001', status='In Transit', eta=datetime.utcnow() + timedelta(days=3), created_at=datetime.utcnow() - timedelta(days=2)),
            Shipment(shipment_id='SHP-5002', po_id=None, sku='NIK-Z9',      qty=10,  carrier='DHL',    tracking_id='DHL-002', status='Delayed',    eta=datetime.utcnow() + timedelta(days=14), created_at=datetime.utcnow() - timedelta(days=5)),
            Shipment(shipment_id='SHP-5003', po_id=None, sku='AIR-PODS',    qty=60,  carrier='UPS',    tracking_id='UPS-003', status='Delivered',  eta=datetime.utcnow() - timedelta(days=1), created_at=datetime.utcnow() - timedelta(days=6)),
        ]

        # ---- Audit trail ----
        audit = [
            AuditTrail(actor="system", action="INIT", entity="Database", entity_id="-",
                       before="", after="Seeded 8 SKUs, 6 suppliers, 30d sales history",
                       timestamp=datetime.utcnow()),
        ]

        # Add everything in one transaction
        db.add_all(products)
        db.add_all(inventory)
        db.add_all(sales)
        db.add_all(returns)
        db.add_all(shipments)
        db.add_all(audit)
        db.commit()
        print("Database seeded: 8 SKUs, 6 suppliers, 30d sales, 4 returns, 3 shipments.")
    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
        raise
    finally:
        db.close()



# FIX: original `finally: pass` leaked every session.
def get_db():
    db = SessionLocal()
    return db


@contextmanager
def get_db_ctx():
    """Context-managed session: auto-closes. Preferred pattern."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
