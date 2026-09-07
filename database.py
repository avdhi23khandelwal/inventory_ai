from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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
    total_stock = Column(Integer)
    amazon_stock = Column(Integer)
    flipkart_stock = Column(Integer)
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
        Product(sku='MAC-PRO-14', name='MacBook Pro 14', price=1999.00, supplier='Apple'),
        Product(sku='NIK-Z9', name='Nikon Z9 Camera', price=5499.00, supplier='Nikon'),
        Product(sku='ALEXA-DOT', name='Alexa Dot 5', price=49.00, supplier='Amazon'),
        Product(sku='AIR-PODS', name='AirPods Pro 2', price=249.00, supplier='Apple'),
    ]
    inventory = [
        Inventory(sku='WH-1000XM5', total_stock=150, amazon_stock=50, flipkart_stock=50, warehouse='Zone-A'),
        Inventory(sku='IPH-15-PRO', total_stock=12, amazon_stock=4, flipkart_stock=4, warehouse='Zone-B'), # Low Stock
        Inventory(sku='GAM-MOUS', total_stock=300, amazon_stock=100, flipkart_stock=100, warehouse='Zone-A'),
        Inventory(sku='SAMSUNG-S24', total_stock=85, amazon_stock=30, flipkart_stock=30, warehouse='Zone-B'),
        Inventory(sku='MAC-PRO-14', total_stock=45, amazon_stock=15, flipkart_stock=15, shopify_stock=15, warehouse='Zone-A'),
        Inventory(sku='NIK-Z9', total_stock=5, amazon_stock=1, flipkart_stock=2, shopify_stock=2, warehouse='Zone-B'),
        Inventory(sku='ALEXA-DOT', total_stock=200, amazon_stock=70, flipkart_stock=70, shopify_stock=60, warehouse='Zone-A'),
        Inventory(sku='AIR-PODS', total_stock=90, amazon_stock=30, flipkart_stock=30, shopify_stock=30, warehouse='Zone-A'),
    ]
    db.add_all(products)
    db.add_all(inventory)
    db.commit()
    print("Database seeded!")
    db.close()

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass # Streamlit manages lifecycle differently, be careful with closing
