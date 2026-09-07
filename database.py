from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import random

DATABASE_URL = "sqlite:///inventory.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    name = Column(String)
    category = Column(String)
    price = Column(Float)
    supplier = Column(String)

class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    amazon_stock = Column(Integer)
    flipkart_stock = Column(Integer)
    myntra_stock = Column(Integer)
    website_stock = Column(Integer)
    total_stock = Column(Integer)
    reorder_point = Column(Integer)
    status = Column(String) # Healthy, Low, Critical
    warehouse = Column(String)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(String, unique=True)
    sku = Column(String)
    qty = Column(Integer)
    status = Column(String)
    created_at = Column(DateTime)

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
    reason = Column(String) # Damaged, Wrong Item, etc.
    status = Column(String) # Pending, Processed
    created_at = Column(DateTime)

class SalesHistory(Base):
    __tablename__ = "sales_history"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String)
    date = Column(String)
    quantity = Column(Integer)
    forecasted_demand = Column(Integer)

Base.metadata.create_all(bind=engine)

def init_db():
    db = SessionLocal()
    if db.query(Product).first():
        return
    
    products = [
        Product(sku='WH-1000XM5', name='Sony Headphones', price=348.00, supplier='Sony'),
        Product(sku='IPH-15-PRO', name='iPhone 15 Pro', price=999.00, supplier='Apple'),
        Product(sku='GAM-MOUS', name='Logitech G502', price=49.99, supplier='Logitech'),
        Product(sku='SAMSUNG-S24', name='Samsung S24', price=799.00, supplier='Samsung'),
    ]
    
    inventory = [
        Inventory(sku='WH-1000XM5', total_stock=150, amazon_stock=50, flipkart_stock=50, myntra_stock=30, website_stock=20, reorder_point=40, status="Healthy", warehouse='Zone-A'),
        Inventory(sku='IPH-15-PRO', total_stock=12, amazon_stock=4, flipkart_stock=4, myntra_stock=2, website_stock=2, reorder_point=20, status="Critical", warehouse='Zone-B'),
        Inventory(sku='GAM-MOUS', total_stock=300, amazon_stock=100, flipkart_stock=100, myntra_stock=50, website_stock=50, reorder_point=80, status="Healthy", warehouse='Zone-A'),
        Inventory(sku='SAMSUNG-S24', total_stock=85, amazon_stock=30, flipkart_stock=30, myntra_stock=15, website_stock=10, reorder_point=50, status="Low", warehouse='Zone-B'),
    ]
    
    # Seed some returns
    returns = [
        Returns(order_id='ORD-991', sku='WH-1000XM5', channel='Amazon', reason='Damaged Packaging', status='Processed', created_at=datetime.utcnow()),
        Returns(order_id='ORD-992', sku='IPH-15-PRO', channel='Flipkart', reason='Wrong Item', status='Pending', created_at=datetime.utcnow()),
    ]

    db.add_all(products)
    db.add_all(inventory)
    db.add_all(returns)
    db.commit()
    print("Database seeded!")
    db.close()

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass
